"""Open a LeRobot v3 dataset for recording with the installed LeRobot 0.4.3 API.

This environment has no LeRobotDataset.resume(). A normal constructor reopens a
finalized dataset for reading; add_frame() creates its recording buffer on demand.
"""

import json
from pathlib import Path


def open_recording_dataset(repo_id, root, fps, features):
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    root = Path(root)
    root.parent.mkdir(parents=True, exist_ok=True)
    info_path = root / "meta" / "info.json"
    if root.exists():
        files = {path.relative_to(root).as_posix() for path in root.rglob("*")
                 if path.is_file() or path.is_symlink()}
        if not files:
            for directory in sorted((path for path in root.rglob("*") if path.is_dir()),
                                    key=lambda path: len(path.parts), reverse=True):
                directory.rmdir()
            root.rmdir()  # LeRobotDataset.create() requires a path that does not exist.
        else:
            if not info_path.is_file():
                raise ValueError(f"Dataset directory has files but no meta/info.json: {root}")
            info = json.loads(info_path.read_text(encoding="utf-8"))
            if info["fps"] != fps:
                raise ValueError("Existing dataset has a different FPS; choose a new --dataset-root")
            for name, expected in features.items():
                actual = info["features"].get(name)
                if (actual is None or actual.get("dtype") != expected["dtype"]
                        or tuple(actual.get("shape", ())) != tuple(expected["shape"])
                        or actual.get("names") != expected["names"]
                        or actual.get("fps") != expected.get("fps")):
                    raise ValueError(f"Existing dataset feature {name} is incompatible: {root}")

            # A previous session can end after create(), before saving a frame.
            # Only this exact empty metadata-only skeleton is safe to recreate.
            if info["total_episodes"] == 0 and info["total_frames"] == 0 and files == {"meta/info.json"}:
                info_path.unlink()
                for directory in sorted((path for path in root.rglob("*") if path.is_dir()),
                                        key=lambda path: len(path.parts), reverse=True):
                    directory.rmdir()  # Empty image folders can remain after discard().
                root.rmdir()
            else:
                if info["total_episodes"] == 0:
                    raise ValueError(f"Incomplete zero-episode dataset contains other files: {root}")
                if not (root / "meta" / "episodes").exists():
                    raise ValueError(f"Dataset lacks finalized meta/episodes; inspect before resuming: {root}")
                return LeRobotDataset(repo_id, root=root)

    return LeRobotDataset.create(
        repo_id, root=root, fps=fps, features=features, robot_type="so101_follower"
    )
