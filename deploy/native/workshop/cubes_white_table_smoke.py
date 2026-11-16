"""Bounded physics and external-side/wrist visual check for the cube task."""

import argparse
import json
from pathlib import Path
import traceback

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--out", type=Path, default=Path("/root/autodl-tmp/workshop/results/cubes-white-table"))
parser.add_argument("--steps", type=int, default=40)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
args.enable_cameras = True
if not 1 <= args.steps <= 120:
    parser.error("--steps must be in [1, 120]")
app = AppLauncher(args).app

env = None
result = {"status": "running", "steps": 0}
args.out.mkdir(parents=True, exist_ok=True)
try:
    import gymnasium as gym
    import numpy as np
    import torch
    from PIL import Image

    import isaaclab_tasks  # noqa: F401
    from isaaclab_tasks.utils import parse_env_cfg
    import sim_to_real_so101.tasks  # noqa: F401
    from sim_to_real_so101.tasks.cubes_white_table_env_cfg import (
        CUBE_CENTER_Z,
        REAL_GREEN_RGB,
        TABLE_CENTER,
        TABLE_SIZE,
        TABLE_TOP_Z,
    )

    task = "Lerobot-So101-Teleop-Cubes-White-Table"
    cfg = parse_env_cfg(task, device=args.device, num_envs=1, use_fabric=True)
    env = gym.make(task, cfg=cfg)
    obs, _ = env.reset()
    joint_names = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll", "Jaw")
    action = torch.tensor(
        [[cfg.scene.robot.init_state.joint_pos[name] for name in joint_names]],
        device=env.unwrapped.device,
    )
    for step in range(args.steps):
        with torch.inference_mode():
            obs, _, _, _, _ = env.step(action)
        result["steps"] = step + 1
        if (step + 1) % 10 == 0:
            print("CUBE_SCENE_STEP", step + 1, flush=True)

    scene = env.unwrapped.scene
    result["robot_base_xyz"] = [round(float(v), 5) for v in scene["robot"].data.root_pos_w[0].tolist()]
    result["robot_joint_pos_rad"] = [round(float(v), 5) for v in scene["robot"].data.joint_pos[0].tolist()]
    for name in ("cube_green", "cube_red"):
        xyz = scene[name].data.root_pos_w[0].detach().cpu().tolist()
        result[name + "_xyz"] = [round(float(v), 5) for v in xyz]
        x, y, z = xyz
        assert TABLE_CENTER[0] - TABLE_SIZE[0] / 2 < x < TABLE_CENTER[0] + TABLE_SIZE[0] / 2, (name, xyz)
        assert abs(y - TABLE_CENTER[1]) < TABLE_SIZE[1] / 2, (name, xyz)
        assert abs(z - CUBE_CENTER_Z) < 0.012, (name, xyz, TABLE_TOP_Z)

    frames = []
    for key, filename in (("rgb_external_D455", "top.png"), ("rgb_ego", "wrist.png")):
        frame = obs["visual"][key][0].detach().cpu().numpy()[..., :3]
        assert np.isfinite(frame).all(), key
        if frame.dtype != np.uint8:
            if frame.max() <= 1.0:
                frame = frame * 255
            frame = np.clip(frame, 0, 255).astype(np.uint8)
        Image.fromarray(frame).save(args.out / filename)
        frames.append(frame)
        result[key + "_size"] = list(frame.shape)

    top = frames[0].astype(np.float32)
    red, green, blue = top.transpose(2, 0, 1)
    result["red_pixels"] = int(((red > 95) & (red > green * 1.45) & (red > blue * 1.4)).sum())
    result["green_pixels"] = int(((green > 55) & (green > red * 1.35) & (green > blue * 1.12)).sum())
    result["white_table_pixels"] = int(((top.min(axis=2) > 135) & ((top.max(axis=2) - top.min(axis=2)) < 28)).sum())
    table_sample = top[400, 320]
    # The enlarged tabletop covers the full left and upper image edges.
    # Check bare-table samples on every border without sampling the robot.
    result["table_frame_edge_rgb"] = {
        "top": top[20, 320].astype(int).tolist(),
        "top_left": top[10, 10].astype(int).tolist(),
        "left": top[300, 6].astype(int).tolist(),
        "right": top[300, 620].astype(int).tolist(),
        "bottom": top[460, 320].astype(int).tolist(),
    }
    result["table_sample_rgb"] = table_sample.astype(int).tolist()
    result["clipped_fraction"] = round(float((top.min(axis=2) >= 248).mean()), 5)
    def median_patch(frame, x, y, radius=5):
        return np.median(frame[y - radius : y + radius + 1, x - radius : x + radius + 1], axis=(0, 1))

    # Check both white inner finger faces, the black outside rims and mount.
    # The fixed finger shares a mesh with its bracket, so whole-mesh color is wrong.
    shell = median_patch(top, 510, 115)
    top_jaw = median_patch(top, 340, 180)
    top_other_jaw = median_patch(top, 364, 175)
    top_outer_rim = median_patch(top, 320, 153)
    gripper_mount = median_patch(top, 350, 90)
    green_top = median_patch(top, 188, 215)
    wrist_jaw = median_patch(frames[1], 250, 400)
    wrist_other_jaw = median_patch(frames[1], 400, 400)
    wrist_left_outer_rim = median_patch(frames[1], 230, 380, radius=2)
    wrist_right_outer_rim = median_patch(frames[1], 468, 440, radius=2)
    wrist_left_inner_rim = median_patch(frames[1], 298, 340, radius=2)
    wrist_right_inner_rim = median_patch(frames[1], 346, 360, radius=2)
    result["shell_rgb"] = shell.astype(int).tolist()
    result["top_jaw_rgb"] = top_jaw.astype(int).tolist()
    result["top_other_jaw_rgb"] = top_other_jaw.astype(int).tolist()
    result["top_outer_rim_rgb"] = top_outer_rim.astype(int).tolist()
    result["gripper_mount_rgb"] = gripper_mount.astype(int).tolist()
    result["green_top_rgb"] = green_top.astype(int).tolist()
    result["wrist_jaw_rgb"] = wrist_jaw.astype(int).tolist()
    result["wrist_other_jaw_rgb"] = wrist_other_jaw.astype(int).tolist()
    result["wrist_left_outer_rim_rgb"] = wrist_left_outer_rim.astype(int).tolist()
    result["wrist_right_outer_rim_rgb"] = wrist_right_outer_rim.astype(int).tolist()
    result["wrist_left_inner_rim_rgb"] = wrist_left_inner_rim.astype(int).tolist()
    result["wrist_right_inner_rim_rgb"] = wrist_right_inner_rim.astype(int).tolist()
    result["dark_robot_pixels"] = int((top[30:270, 380:620].max(axis=2) < 85).sum())
    Image.fromarray(np.concatenate(frames, axis=1)).save(args.out / "top-and-wrist.png")
    assert np.allclose(result["robot_base_xyz"][:2], cfg.scene.robot.init_state.pos[:2], atol=0.003), result
    assert np.max(np.abs(np.asarray(result["robot_joint_pos_rad"]) - action[0].cpu().numpy())) < 0.04, result
    assert result["dark_robot_pixels"] > 1000, result
    assert min(result[c + "_pixels"] for c in ("red", "green")) > 75, result
    assert result["white_table_pixels"] > 10000, result
    assert 130 < table_sample.mean() < 210, result  # avoid the previous washed-out tabletop
    assert all(145 < np.mean(rgb) < 220 for rgb in result["table_frame_edge_rgb"].values()), result
    assert all(
        abs(np.mean(rgb) - table_sample.mean()) < 18
        for rgb in result["table_frame_edge_rgb"].values()
    ), result
    assert result["clipped_fraction"] < 0.02, result
    assert shell.max() < 85 and gripper_mount.max() < 85, result
    assert all(rim.max() < 85 for rim in (
        top_outer_rim, wrist_left_outer_rim, wrist_right_outer_rim,
        wrist_left_inner_rim, wrist_right_inner_rim,
    )), result
    assert all(110 < jaw.mean() < 210 for jaw in (top_jaw, top_other_jaw)), result
    assert all(115 < jaw.mean() < 195 for jaw in (wrist_jaw, wrist_other_jaw)), result
    assert np.max(np.abs(green_top - REAL_GREEN_RGB)) <= 8, result
    result["status"] = "pass"
    print("CUBE_SCENE_PASS", json.dumps(result), flush=True)
except Exception as error:
    result.update(status="failed", error_type=type(error).__name__, error=str(error))
    traceback.print_exc()
    print("CUBE_SCENE_FAILED", json.dumps(result), flush=True)
    raise
finally:
    (args.out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    if env is not None:
        env.close()
    app.close(skip_cleanup=False)
