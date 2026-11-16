"""Headless SO-101 simulation with local-leader teleop, MJPEG and LeRobot recording.

The HTTP service listens only on 127.0.0.1. Forward it with the existing SSH
tunnel, then send real calibrated leader actions from so101_leader_client.py.
"""

import argparse
import faulthandler
from io import BytesIO
from pathlib import Path
import time
import traceback

from isaaclab.app import AppLauncher

faulthandler.enable()

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--http-port", type=int, default=8765)
parser.add_argument("--fps", type=int, default=10, help="Target simulation and dataset FPS")
parser.add_argument("--duration-seconds", type=float, default=0, help="Optional test timeout")
parser.add_argument("--max-episode-seconds", type=int, default=60)
parser.add_argument("--task", default="Lerobot-So101-Teleop-Vials-To-Rack")
parser.add_argument("--task-name", default="Pick up the vial and place it in the yellow rack")
parser.add_argument("--dataset-root", type=Path,
                    default=Path("/root/autodl-tmp/workshop/datasets/so101-remote-vials"))
parser.add_argument("--repo-id", default="local/so101-remote-vials")
parser.add_argument("--seed", type=int, default=1984)
parser.add_argument("--allow-mock-recording", action="store_true",
                    help="Diagnostics only; never mix mock episodes into a real dataset")
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if not 1 <= args.http_port <= 65535 or not 1 <= args.fps <= 30:
    parser.error("--http-port must be valid; --fps must be in [1, 30]")
if not 1 <= args.max_episode_seconds <= 120:
    parser.error("--max-episode-seconds must be in [1, 120]")
CUBE_TASK = "Lerobot-So101-Teleop-Cubes-White-Table"
if args.task == CUBE_TASK and args.fps != 30:
    parser.error("The cube recording task requires --fps 30")
args.enable_cameras = True
app = AppLauncher(args).app


import gymnasium as gym
import numpy as np
import torch
from PIL import Image, ImageDraw

import isaaclab_tasks  # noqa: F401
from isaaclab_tasks.utils import parse_env_cfg
import sim_to_real_so101.tasks  # noqa: F401
from sim_to_real_so101.utils.lerobot_interface import LeRobotSO101Interface

from so101_dataset import open_recording_dataset
from so101_teleop_http import JOINTS, TeleopState, start_server


def rgb_array(tensor):
    array = tensor[0].detach().cpu().numpy()[..., :3]
    if not np.isfinite(array).all():
        raise ValueError("Camera produced non-finite pixel values")
    if array.dtype != np.uint8:
        if array.max() <= 1:
            array = array * 255
        array = np.clip(array, 0, 255).astype(np.uint8)
    return array


class DatasetSink:
    """Keep one LeRobot v3 episode in memory and encode it on Save."""

    def __init__(self, state, cameras):
        self.state = state
        self.cameras = cameras
        self.dataset = None
        self.recording = False
        self.failed = False
        self.features = {
            "action": {"dtype": "float32", "shape": (6,), "names": list(JOINTS), "fps": args.fps},
            "observation.state": {"dtype": "float32", "shape": (6,),
                                  "names": list(JOINTS), "fps": args.fps},
        }
        for name, cfg in cameras.items():
            self.features[f"observation.images.{name}"] = {
                "dtype": "video", "shape": (cfg["height"], cfg["width"], 3),
                "names": ["height", "width", "channels"],
            }

    def load(self):
        if self.failed:
            raise RuntimeError("Previous dataset save failed; inspect the recording before resuming")
        if self.dataset is not None:
            return
        root = args.dataset_root
        print(f"DATASET_LOAD_BEGIN root={root}", flush=True)
        self.dataset = open_recording_dataset(args.repo_id, root, args.fps, self.features)
        with self.state.cond:
            self.state.episodes = self.dataset.meta.total_episodes
        print(f"DATASET_READY root={root} episodes={self.dataset.meta.total_episodes}", flush=True)

    def start(self):
        if self.recording:
            return
        self.load()
        self.recording = True
        with self.state.cond:
            self.state.error = None
            self.state.recording = True
            self.state.frames = 0
        print("EPISODE_STARTED", flush=True)

    def add(self, raw_action, joint_positions, visuals):
        rgb = {name: rgb_array(visuals[f"rgb_{name}"]) for name in self.cameras}
        frame = {
            "action": raw_action.detach().cpu().numpy().astype(np.float32),
            "observation.state": joint_positions.detach().cpu().numpy().astype(np.float32),
            "task": args.task_name,
        }
        for name, image in rgb.items():
            frame[f"observation.images.{name}"] = image
        self.dataset.add_frame(frame)
        with self.state.cond:
            self.state.frames += 1

    def save(self):
        if not self.recording:
            return
        self.recording = False
        with self.state.cond:
            self.state.recording = False
            count = self.state.frames
            self.state.saving = True
        try:
            if count:
                print(f"EPISODE_ENCODING frames={count}", flush=True)
                self.dataset.save_episode(parallel_encoding=False)
                self.dataset.finalize()
                with self.state.cond:
                    self.state.episodes = self.dataset.meta.total_episodes
                print(f"EPISODE_SAVED frames={count} total={self.state.episodes}", flush=True)
                self.dataset = None  # Reopen on next start, following the workshop recorder.
            else:
                print("EPISODE_EMPTY_NOT_SAVED", flush=True)
        except Exception:
            self.failed = True
            raise
        finally:
            with self.state.cond:
                self.state.saving = False
                self.state.frames = 0

    def discard(self):
        if not self.recording:
            return
        self.recording = False
        self.dataset.clear_episode_buffer(delete_images=True)
        with self.state.cond:
            self.state.recording = False
            self.state.frames = 0
        print("EPISODE_DISCARDED", flush=True)


def main():
    env = None
    server = None
    state = TeleopState(args.dataset_root, args.allow_mock_recording)
    sink = None
    try:
        cfg = parse_env_cfg(args.task, device=args.device, num_envs=1, use_fabric=True)
        cfg.seed = args.seed
        if args.task == CUBE_TASK:
            # Four physics ticks at 120 Hz per recorded 30 Hz camera frame.
            cfg.decimation = 4
            cfg.sim.render_interval = 4
        cfg.episode_length_s = 1900  # Beyond the 1800 s launcher lifetime; avoid unsafe auto reset.
        env = gym.make(args.task, cfg=cfg)
        obs, _ = env.reset()
        cameras = {}
        for name in env.unwrapped.scene.keys():
            if name.startswith("camera_"):
                cam = getattr(env.unwrapped.scene.cfg, name)
                cameras[name.removeprefix("camera_")] = {"width": cam.width, "height": cam.height}
        if set(cameras) != {"ego", "external_D455"}:
            raise RuntimeError(f"SO-101 task cameras changed: {list(cameras)}")
        if args.task == CUBE_TASK and any(c != {"width": 640, "height": 480} for c in cameras.values()):
            raise RuntimeError(f"Cube recording requires two 640x480 cameras: {cameras}")
        print(f"RECORDING_CONFIG task={args.task} fps={args.fps} cameras={cameras}", flush=True)
        sink = DatasetSink(state, cameras)
        def save_automatically(reason):
            try:
                sink.save()
            except Exception as exc:
                traceback.print_exc()
                with state.cond:
                    state.error = f"{reason} 自动保存失败: {exc}"

        iface = LeRobotSO101Interface(
            device=env.unwrapped.device, port="/dev/null", id="network_leader",
            cameras=cameras, fps=args.fps, kind="leader",
        )
        action = torch.tensor([[-0.2736, -0.6109, -0.0745, 1.5148,
                                -1.6034, -0.1465]], device=env.unwrapped.device)
        if args.task == CUBE_TASK:
            joint_names = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll", "Jaw")
            action = torch.tensor(
                [[cfg.scene.robot.init_state.joint_pos[name] for name in joint_names]],
                device=env.unwrapped.device,
            )
        if action.shape != env.action_space.shape:
            raise RuntimeError(f"Unexpected action space: {env.action_space.shape}")
        server = start_server(state, args.http_port)
        print(f"REMOTE_TELEOP_READY http://127.0.0.1:{args.http_port}", flush=True)

        started = time.monotonic()
        warmup_from = action.clone()
        warmup_step = 0
        connected = False
        step = 0
        while app.is_running() and (not args.duration_seconds
                                    or time.monotonic() - started < args.duration_seconds):
            tick = time.monotonic()
            for control_id, command in state.drain_controls():
                print(f"CONTROL_REQUEST command={command}", flush=True)
                try:
                    if command == "start":
                        live, source = state.latest_action()
                        if live is None or (source != "leader" and not args.allow_mock_recording):
                            raise RuntimeError("Leader action expired before recording started")
                        sink.start()
                        result = "录制已开始"
                    elif command == "stop":
                        count = state.frames
                        sink.save()
                        result = f"本回合已保存 {count} 帧；累计 {state.episodes} 回合" if count else "本回合无帧，未保存"
                    elif command == "discard":
                        sink.discard()
                        result = "本回合已丢弃"
                    else:
                        raise ValueError(f"Unsupported control command: {command}")
                    state.finish_control(control_id, result)
                except Exception as exc:
                    traceback.print_exc()
                    state.finish_control(control_id, f"{command} 执行失败: {exc}", error=True)

            latest, source = state.latest_action()
            if latest is None:
                if sink.recording:
                    print("ACTION_TIMEOUT; saving current episode and holding pose", flush=True)
                    save_automatically("主臂超时")
                connected = False
                with state.cond:
                    state.armed = False
                raw_action = None
            else:
                if not connected:
                    warmup_from = action.clone()
                    warmup_step = 0
                    connected = True
                raw_action, target = iface.real_to_sim_obs_processor(latest)
                warmup_step += 1
                progress = min(1.0, warmup_step / max(1, round(args.fps * 1.5)))
                action[:] = warmup_from * (1 - progress) + target.reshape_as(action) * progress
                with state.cond:
                    state.armed = progress >= 1

            with torch.inference_mode():
                obs, _, terminated, truncated, _ = env.step(action)
                if bool(terminated.any()) or bool(truncated.any()):
                    save_automatically("场景结束")
                    print("SCENE_ENDED; no automatic env.reset() after reset failure", flush=True)
                    break
                if sink.recording and raw_action is not None:
                    joint = obs["policy"]["joint_pos_obs"][0]
                    raw_obs = iface.get_raw_actions_from_radians(joint)
                    sink.add(raw_action, raw_obs, obs["visual"])
                    if state.frames >= args.max_episode_seconds * args.fps:
                        save_automatically("回合时间上限")
                rgb = np.concatenate(
                    [rgb_array(obs["visual"][k]) for k in
                     ("rgb_external_D455", "rgb_ego")], axis=1)

            step += 1
            picture = Image.fromarray(rgb)
            ImageDraw.Draw(picture).text(
                (10, 10), f"SIM | step {step} | {source or 'waiting'} | "
                          f"{'REC' if sink.recording else 'READY'}",
                fill="white", stroke_width=2, stroke_fill="black",
            )
            buf = BytesIO()
            picture.save(buf, "JPEG", quality=72)
            state.publish(buf.getvalue())
            if step == 1 or step % 100 == 0:
                print(f"TELEOP_FRAME step={step} source={source} bytes={buf.tell()}", flush=True)
            time.sleep(max(0, 1 / args.fps - (time.monotonic() - tick)))
        elapsed = time.monotonic() - started
        print(f"TELEOP_RATE steps={step} elapsed={elapsed:.2f}s actual_fps={step / elapsed:.2f}", flush=True)
    finally:
        try:
            if sink and sink.recording:
                print("SHUTDOWN_SAVING_EPISODE", flush=True)
                sink.save()
        except Exception:
            traceback.print_exc()
        state.close()
        if server:
            server.shutdown()
            server.server_close()
        if env:
            env.close()
        app.close(skip_cleanup=False)


if __name__ == "__main__":
    main()
