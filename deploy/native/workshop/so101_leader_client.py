"""Read a local SO-101 leader and send its calibrated actions over the SSH viewer tunnel.

Use --mock for transport checks without hardware. Mock actions are marked as such and
cannot be recorded unless the remote server explicitly enables test recording.
"""

import argparse
import http.client
import json
import math
import os
from pathlib import Path
import time
from urllib.parse import urlsplit


JOINTS = (
    "shoulder_pan.pos", "shoulder_lift.pos", "elbow_flex.pos",
    "wrist_flex.pos", "wrist_roll.pos", "gripper.pos",
)


def lelab_cache_home():
    home = (Path(__file__).resolve().parents[4] / "lelab-main" / ".cache"
            / "huggingface" / "lerobot")
    if not home.is_dir():
        raise SystemExit(f"Existing LeLab calibration cache not found: {home}")
    os.environ["HF_HOME"] = str(home.parent)
    os.environ["HF_LEROBOT_HOME"] = str(home)
    return home


def read_ports(cache_home=None):
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise SystemExit("Run this client using the existing ../lelab-main/.venv/Scripts/python.exe") from exc
    for port in list_ports.comports():
        print(f"{port.device}: {port.description}")
    if cache_home is not None:
        directory = cache_home / "calibration" / "teleoperators" / "so_leader"
        names = sorted(path.stem for path in directory.glob("*.json"))
        print("Existing LeLab leader calibration IDs:", ", ".join(names) or "none")
        previous = cache_home / "ports" / "leader_port.txt"
        if previous.is_file():
            print("LeLab's last recorded leader port (recheck USB):", previous.read_text().strip())


def open_leader(port, robot_id, cache_home=None):
    try:
        # LeLab's LeRobot 0.6.0 exposes so_leader; older workshop checkouts
        # may still expose the original so101_leader location.
        from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig
    except ImportError as exc:
        try:
            from lerobot.teleoperators.so101_leader import SO101Leader, SO101LeaderConfig
        except ImportError:
            raise SystemExit(
                "Run this client using the existing ../lelab-main/.venv/Scripts/python.exe"
            ) from exc
    # The workshop mapping expects [-100, 100] for the arm and [0, 100] for grip.
    leader = SO101Leader(SO101LeaderConfig(port=port, id=robot_id, use_degrees=False))
    if cache_home is None:
        leader.connect()  # Generic LeRobot connection, including first-time calibration.
        return leader

    calibration = cache_home / "calibration" / "teleoperators" / "so_leader" / f"{robot_id}.json"
    expected = {joint.split(".")[0] for joint in JOINTS}
    if not calibration.is_file() or set(leader.calibration) != expected:
        raise SystemExit(f"LeLab leader calibration missing/incomplete: {calibration}. "
                         "Calibrate this leader in LeLab first, then retry with its ID.")
    # Mirror LeLab's leader connection sequence; no follower or camera is opened.
    try:
        leader.bus.connect()
        leader.bus.write_calibration(leader.calibration)
        leader.configure()
    except BaseException:
        if leader.is_connected:
            try:
                leader.disconnect()
            except Exception:
                pass
        raise
    return leader


def validate_action(raw):
    if set(raw) != set(JOINTS):
        raise ValueError("Leader returned unexpected joint names")
    action = {name: float(raw[name]) for name in JOINTS}
    if any(not math.isfinite(value) for value in action.values()):
        raise ValueError("Leader returned a non-finite joint value")
    return action


def run(args):
    target = urlsplit(args.server)
    if target.scheme != "http" or target.hostname not in ("127.0.0.1", "localhost"):
        raise SystemExit("--server must be a loopback HTTP URL forwarded over SSH")
    if target.path not in ("", "/") or target.query or target.fragment:
        raise SystemExit("--server must contain only the host and port")

    leader = None
    connection = http.client.HTTPConnection(target.hostname, target.port or 8765, timeout=4)
    source = "mock" if args.mock else "leader"
    try:
        connection.request("GET", "/health")
        reply = connection.getresponse()
        if reply.status != 200:
            raise ConnectionError(f"Remote health check returned {reply.status}")
        try:
            health = json.loads(reply.read())
        except ValueError as exc:
            raise ConnectionError("Remote /health did not return teleoperation status") from exc
        if "leader_online" not in health or not health.get("ready"):
            raise ConnectionError("The remote teleoperation scene is not ready")

        if not args.mock:
            if not args.port:
                raise SystemExit("Pass --port COMx (Windows) or --port /dev/ttyACM0 (Linux)")
            print("Connecting leader with its existing LeLab calibration.", flush=True)
            leader = open_leader(args.port, args.robot_id, lelab_cache_home() if args.lelab_cache else None)

        print(f"Sending {source} actions to {args.server} at up to {args.fps:g} Hz; Ctrl+C to stop.", flush=True)
        deadline = time.monotonic()
        # A fresh client can reconnect immediately without reusing sequence 0.
        seq = time.monotonic_ns()
        sent = 0
        while True:
            if args.mock:
                t = time.monotonic()
                raw = dict.fromkeys(JOINTS, 0.0)
                raw["shoulder_pan.pos"] = 8.0 * math.sin(t)
                raw["gripper.pos"] = 50.0
            else:
                raw = leader.get_action()
            action = validate_action(raw)
            packet = {"source": source, "seq": seq, "action": action}
            data = json.dumps(packet, allow_nan=False).encode("utf-8")
            connection.request("POST", "/action", data, {"Content-Type": "application/json"})
            reply = connection.getresponse()
            response = reply.read()
            if reply.status != 202:
                raise ConnectionError(f"Remote rejected action ({reply.status}): {response[:200]!r}")
            seq += 1
            sent += 1
            if sent == 1 or sent % int(max(1, args.fps * 5)) == 0:
                print(f"Sent {sent} actions. Open {args.server}/ to see the cameras and recording buttons.", flush=True)
            if args.max_actions and sent >= args.max_actions:
                break
            deadline += 1.0 / args.fps
            time.sleep(max(0, deadline - time.monotonic()))
    except KeyboardInterrupt:
        print("Stopped sending leader actions.", flush=True)
    finally:
        connection.close()
        if leader is not None:
            leader.disconnect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-ports", action="store_true", help="List local serial devices and exit")
    parser.add_argument("--lelab-cache", action="store_true",
                        help="Reuse the existing LeLab leader calibration files")
    parser.add_argument("--port", help="Local USB port connected to the SO-101 leader")
    parser.add_argument("--robot-id", default="leader_arm_1")
    parser.add_argument("--server", default="http://127.0.0.1:8765")
    parser.add_argument("--fps", type=float, default=20.0)
    parser.add_argument("--mock", action="store_true", help="Exercise transport without a physical leader")
    parser.add_argument("--max-actions", type=int, default=0, help="Exit after N actions (diagnostics)")
    args = parser.parse_args()
    if not 0 < args.fps <= 60 or args.max_actions < 0:
        parser.error("--fps must be in (0, 60] and --max-actions must be nonnegative")
    cache_home = lelab_cache_home() if args.lelab_cache else None
    if args.list_ports:
        read_ports(cache_home)
        return
    try:
        run(args)
    except (ConnectionError, OSError, TimeoutError) as exc:
        raise SystemExit(f"Action link unavailable: {exc}. The remote simulation will hold its last pose.") from exc


if __name__ == "__main__":
    main()
