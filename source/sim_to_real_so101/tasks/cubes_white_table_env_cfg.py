# SPDX-License-Identifier: Apache-2.0
"""SO-101 cube task with an external side camera and wrist camera."""

import numpy as np
import torch
import isaaclab.sim as sim_utils
from isaaclab.assets import ArticulationCfg, AssetBaseCfg, RigidObjectCfg
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationGroupCfg as ObsGroup
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils import configclass
from isaacsim.core.utils.rotations import euler_angles_to_quat
from pxr import Sdf

from sim_to_real_so101.assets.so101 import SO101_CFG, here as so101_assets_dir
from sim_to_real_so101.mdp import image

from .so101_env_cfg import EventCfg, LerobotSo101BaseSceneCfg, ObservationsCfg
from .task_env_cfg import SO101TaskEnvCfg, camera_object


# Extend the tabletop leftward and behind the robot so its edges stay outside
# the external side camera while the tabletop height and objects stay fixed.
TABLE_CENTER = (0.205, 0.10, -0.0125)
TABLE_SIZE = (1.21, 1.00, 0.025)
TABLE_TOP_Z = TABLE_CENTER[2] + TABLE_SIZE[2] / 2
CUBE_SIZE = 0.035
CUBE_CENTER_Z = TABLE_TOP_Z + CUBE_SIZE / 2
# Reference: real pick-and-place-v3 side video, green cube top, RGB 27/74/47.
REAL_GREEN_RGB = (27, 74, 47)
# One fixed PBR diffuse material binds to the entire cube, not only its top face.
# These linear material values render close to REAL_GREEN_RGB under this scene's light.
GREEN_CUBE_DIFFUSE = (0.031, 0.130, 0.071)
# The real wrist view is slightly brighter than the external camera.
# Apply a small gain to this camera's RGB observation only; keep scene lighting fixed.
WRIST_RGB_GAIN = 1.11
# Median frame-15 observation.state from real pick-and-place-v3 episodes 0-29,
# converted with LeRobotSO101Interface.SO101_USD_MAPPING (raw -100..100 to USD
# degrees, then radians). The recorded shoulder lift (-103.4 raw) exceeds the
# physical USD range, so its reset target is limited to -100 degrees. Wrist
# pitch includes a 0.0435 rad adjustment to align the rendered jaw tip. The
# Rotation target advances 0.4456 rad from the real-data median (-0.0456) so the
# jaws point toward the green cube in the accepted external-camera framing.
REAL_START_JOINT_POS = {
    "Rotation": 0.4000,
    "Pitch": -1.7453,
    "Elbow": 1.4535,
    "Wrist_Pitch": 0.9450,
    "Wrist_Roll": 0.0405,
    "Jaw": -0.1705,
}
# Keep the image-aligned base, camera, cube positions and jaw opening fixed.
# The arm still enters from the upper right; only its base rotation joint is
# turned clockwise in the side image to aim its two jaws toward the green cube.
REAL_ROBOT_BASE_POS = (0.450, 0.148, 0.0)
REAL_ROBOT_BASE_YAW_DEG = -55.0


def side_camera_quat(tilt_degrees: float, yaw_degrees: float, roll_degrees: float):
    """Add an optical-axis roll to a world-yaw/tilt camera (wxyz quaternion)."""
    w, x, y, z = euler_angles_to_quat(np.array([tilt_degrees, 0, yaw_degrees]), degrees=True)
    half_roll = np.deg2rad(roll_degrees) / 2
    c, s = np.cos(half_roll), np.sin(half_roll)
    return (w * c - z * s, x * c + y * s, y * c - x * s, z * c + w * s)


def set_robot_black(env, env_ids) -> None:
    """Keep the printed shell black; jaw meshes use a separate USD material."""
    material_path = env.scene["robot"].cfg.prim_path + "/Looks/material_a_3d_printed/Shader"
    material = sim_utils.find_matching_prims(material_path)[0]
    with Sdf.ChangeBlock():
        material.GetAttribute("inputs:diffuse_color_constant").Set((0.025, 0.025, 0.025))


def wrist_rgb_with_gain(env, sensor_cfg: SceneEntityCfg, data_type: str = "rgb", normalize: bool = False):
    """Brighten only the wrist camera stream while preserving its alpha channel."""
    frame = image(env, sensor_cfg=sensor_cfg, data_type=data_type, normalize=normalize)
    bright_rgb = (frame[..., :3].to(torch.float32) * WRIST_RGB_GAIN).clamp_(0, 255).to(frame.dtype)
    if frame.shape[-1] == 4:
        return torch.cat((bright_rgb, frame[..., 3:]), dim=-1)
    return bright_rgb


def cube(color: tuple[float, float, float], position: tuple[float, float, float]) -> RigidObjectCfg:
    """Create a graspable, independently simulated cube."""
    return RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/Cube",
        spawn=sim_utils.CuboidCfg(
            size=(CUBE_SIZE, CUBE_SIZE, CUBE_SIZE),
            mass_props=sim_utils.MassPropertiesCfg(mass=0.025),
            rigid_props=sim_utils.RigidBodyPropertiesCfg(),
            collision_props=sim_utils.CollisionPropertiesCfg(),
            physics_material=sim_utils.RigidBodyMaterialCfg(static_friction=1.0, dynamic_friction=0.8),
            visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=color, roughness=0.8),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(pos=position),
    )


@configclass
class CubesWhiteTableSceneCfg(LerobotSo101BaseSceneCfg):
    """Reuse SO-101 with external side and on-wrist cameras."""

    # A tiny USD layer overrides visuals only; joints, collision and cameras
    # remain those of the existing SO-101 asset.
    robot: ArticulationCfg = SO101_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")
    robot.spawn.usd_path = f"{so101_assets_dir}/usd/SO-ARM101-BLACK-WHITE.usda"
    robot.init_state.joint_pos = REAL_START_JOINT_POS.copy()
    robot.init_state.pos = REAL_ROBOT_BASE_POS
    robot.init_state.rot = euler_angles_to_quat(np.array([0, 0, REAL_ROBOT_BASE_YAW_DEG]), degrees=True)

    sky_light = AssetBaseCfg(
        prim_path="/World/sky_light",
        spawn=sim_utils.DomeLightCfg(intensity=130.0, color=(1.0, 1.0, 1.0)),
    )
    key_light = AssetBaseCfg(
        prim_path="/World/key_light",
        spawn=sim_utils.DistantLightCfg(intensity=320.0, angle=40.0, color=(1.0, 0.98, 0.95)),
        init_state=AssetBaseCfg.InitialStateCfg(
            rot=euler_angles_to_quat(np.array([20, -25, 0]), degrees=True),
        ),
    )

    # Neutral background defines the tabletop edge without enclosing walls.
    background = AssetBaseCfg(
        prim_path="{ENV_REGEX_NS}/Background",
        spawn=sim_utils.CuboidCfg(
            size=(2.0, 2.0, 0.005),
            visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.32, 0.32, 0.32), roughness=0.9),
        ),
        init_state=AssetBaseCfg.InitialStateCfg(pos=(0.20, 0.0, -0.065)),
    )

    mat = AssetBaseCfg(
        prim_path="{ENV_REGEX_NS}/Mat",
        spawn=sim_utils.CuboidCfg(
            size=TABLE_SIZE,
            collision_props=sim_utils.CollisionPropertiesCfg(),
            visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.55, 0.55, 0.54), roughness=0.94),
        ),
        init_state=AssetBaseCfg.InitialStateCfg(pos=TABLE_CENTER),
    )

    cube_green = cube(GREEN_CUBE_DIFFUSE, (0.16, 0.075, CUBE_CENTER_Z))
    cube_green.prim_path = "{ENV_REGEX_NS}/CubeGreen"

    cube_red = cube((0.73, 0.065, 0.055), (0.27, 0.055, CUBE_CENTER_Z))
    cube_red.prim_path = "{ENV_REGEX_NS}/CubeRed"

    camera_ego = camera_object.replace()
    camera_ego.prim_path = "{ENV_REGEX_NS}/Robot/gripper/gripper_cam"
    camera_ego.offset.pos = (-0.005, 0.06, -0.062)
    camera_ego.offset.rot = euler_angles_to_quat(np.array([-45, 0, 0]), degrees=True)
    camera_ego.data_types = ["rgb"]

    # Angle the external camera toward the real side-camera view; the legacy
    # observation key remains unchanged for teleop/recording compatibility.
    camera_external_D455 = camera_object.replace()
    camera_external_D455.prim_path = "{ENV_REGEX_NS}/TopCamera"
    camera_external_D455.offset.pos = (0.31, -0.06, 0.30)
    camera_external_D455.offset.rot = side_camera_quat(25, 14.5, -12.3)
    camera_external_D455.offset.convention = "opengl"
    camera_external_D455.spawn.focal_length = 11.0
    # Keep the arm in frame from the lower viewpoint, and disable depth-of-field
    # blur (the upstream camera focuses only 5 cm in front of its lens).
    camera_external_D455.spawn.focus_distance = 0.68
    camera_external_D455.spawn.f_stop = 0.0
    camera_external_D455.data_types = ["rgb"]


@configclass
class CubesWhiteTableObservationsCfg(ObservationsCfg):
    """The cube recorder only needs RGB, not depth or segmentation passes."""

    @configclass
    class VisualCfg(ObsGroup):
        rgb_ego = ObsTerm(
            func=wrist_rgb_with_gain,
            params={"sensor_cfg": SceneEntityCfg("camera_ego"), "data_type": "rgb", "normalize": False},
        )
        rgb_external_D455 = ObsTerm(
            func=image,
            params={"sensor_cfg": SceneEntityCfg("camera_external_D455"), "data_type": "rgb", "normalize": False},
        )

        def __post_init__(self) -> None:
            self.enable_corruption = False
            self.concatenate_terms = False

    visual: VisualCfg = VisualCfg()


@configclass
class CubesWhiteTableEventCfg(EventCfg):
    reset_set_robot_visual_material = EventTerm(
        func=set_robot_black,
        mode="reset",
    )


@configclass
class CubesWhiteTableEnvCfg(SO101TaskEnvCfg):
    """Separate cube task; do not modify the vial task."""

    scene: CubesWhiteTableSceneCfg = CubesWhiteTableSceneCfg()
    events: CubesWhiteTableEventCfg = CubesWhiteTableEventCfg()
    observations: CubesWhiteTableObservationsCfg = CubesWhiteTableObservationsCfg()

    def __post_init__(self) -> None:
        super().__post_init__()
        self.episode_length_s = 60.0
        self.viewer.eye = (0.28, -0.5, 0.52)
        self.viewer.lookat = (0.28, 0.0, TABLE_TOP_Z)
