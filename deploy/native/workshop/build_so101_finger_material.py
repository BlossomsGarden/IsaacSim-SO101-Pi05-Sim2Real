"""Generate a visual-only SO-101 USD layer with white sides and black finger rims.

Run with the installed Isaac Sim / Isaac Lab Python on a machine holding the
real SO-ARM101-USD.usd asset. The source mesh joins the fixed finger and its
black mounting bracket, so coloring the whole mesh colors too much plastic.
"""

import argparse
import os
from pathlib import Path

from isaaclab.app import AppLauncher


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--asset-dir", type=Path, required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()

app = AppLauncher(args).app
try:
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

    asset_dir = args.asset_dir.resolve()
    source = asset_dir / "SO-ARM101-USD.usd"
    output = asset_dir / "SO-ARM101-BLACK-WHITE.usda"
    temporary = asset_dir / "SO-ARM101-BLACK-WHITE.generated.usda"
    if not source.is_file() or source.read_bytes()[:8] == b"version ":
        raise FileNotFoundError(f"Real USD asset required: {source}")

    stage = Usd.Stage.CreateNew(str(temporary))
    stage.GetRootLayer().subLayerPaths.append("SO-ARM101-USD.usd")
    stage.SetDefaultPrim(stage.OverridePrim("/so101_new_calib"))

    # Match the accepted black body and white printed finger colors.
    shader_prim = stage.OverridePrim("/so101_new_calib/Looks/material_a_3d_printed/Shader")
    shader_prim.CreateAttribute("inputs:diffuse_color_constant", Sdf.ValueTypeNames.Color3f).Set(
        Gf.Vec3f(0.025, 0.025, 0.025)
    )
    white = UsdShade.Material.Define(stage, "/so101_new_calib/Looks/FingerWhite")
    shader = UsdShade.Shader.Define(stage, "/so101_new_calib/Looks/FingerWhite/Shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.78, 0.78, 0.77))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.92)
    white.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    black = UsdShade.Material(stage.GetPrimAtPath("/so101_new_calib/Looks/material_a_3d_printed"))

    fingers = (
        ("/visuals/gripper/wrist_roll_follower_so101_v1/mesh", 2, 0.040, True),
        ("/visuals/jaw/moving_jaw_so101_v1/mesh", 1, -0.035, False),
    )
    # The two fingers are bent along their length. Find the outside of each
    # finger in short axial slices instead of using one global x cutoff.
    # Expose the black plastic around both the outward and inward edges of
    # each finger, preserving the wide white side face between the rims.
    outer_edge_width_m = 0.0015
    inner_edge_width_m = 0.0010
    axial_slice_m = 0.002
    for path, axis, boundary, above in fingers:
        mesh = UsdGeom.Mesh(stage.GetPrimAtPath(path))
        if not mesh or not mesh.GetPrim().IsValid():
            raise RuntimeError(f"Missing finger mesh: {path}")
        # The upstream printed-plastic parent explicitly uses
        # strongerThanDescendants. Its authored binding otherwise overrides
        # every white face subset, even if USD lists the subset as valid.
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim().GetParent()).Bind(
            black, UsdShade.Tokens.weakerThanDescendants
        )
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(
            black, UsdShade.Tokens.weakerThanDescendants
        )
        points = mesh.GetPointsAttr().Get()
        counts = mesh.GetFaceVertexCountsAttr().Get()
        indices = mesh.GetFaceVertexIndicesAttr().Get()
        tip_faces = []
        start = 0
        for face, size in enumerate(counts):
            vertices = [points[i] for i in indices[start : start + size]]
            start += size
            coords = [p[axis] for p in vertices]
            if all(c >= boundary for c in coords) if above else all(c <= boundary for c in coords):
                axial_distance = (sum(coords) / size - boundary) * (1 if above else -1)
                axial_slice = int(axial_distance / axial_slice_m)
                tip_faces.append((face, axial_slice, sum(p[0] for p in vertices) / size))
        outer_x = {}
        inner_x = {}
        for _, axial_slice, x in tip_faces:
            if axial_slice not in outer_x:
                outer_x[axial_slice] = x
                inner_x[axial_slice] = x
            elif above:
                outer_x[axial_slice] = min(outer_x[axial_slice], x)
                inner_x[axial_slice] = max(inner_x[axial_slice], x)
            else:
                outer_x[axial_slice] = max(outer_x[axial_slice], x)
                inner_x[axial_slice] = min(inner_x[axial_slice], x)
        white_faces = [
            face for face, axial_slice, x in tip_faces
            if ((x - outer_x[axial_slice]) if above else (outer_x[axial_slice] - x)) >= outer_edge_width_m
            and ((inner_x[axial_slice] - x) if above else (x - inner_x[axial_slice])) >= inner_edge_width_m
        ]
        if not 1000 < len(white_faces) < len(counts) - 1000:
            raise RuntimeError(f"Unexpected white finger face count: {path} {len(white_faces)}")

        # Only these faces override the original black printed-plastic material.
        subset = UsdGeom.Subset.Define(stage, path + "/FingerWhiteFaces")
        subset.CreateElementTypeAttr(UsdGeom.Tokens.face)
        subset.CreateFamilyNameAttr(UsdShade.Tokens.materialBind)
        subset.CreateIndicesAttr(white_faces)
        UsdGeom.Subset.SetFamilyType(mesh, UsdShade.Tokens.materialBind, UsdGeom.Tokens.nonOverlapping)
        UsdShade.MaterialBindingAPI.Apply(subset.GetPrim()).Bind(white)
        if UsdShade.MaterialBindingAPI(subset.GetPrim()).ComputeBoundMaterial()[0].GetPath() != white.GetPath():
            raise RuntimeError(f"Finger material is still overridden by its parent: {path}")
        print(
            f"WHITE_FINGER {path} {len(white_faces)}/{len(counts)} faces "
            f"({len(tip_faces) - len(white_faces)} inner/outer rim faces remain black)",
            flush=True,
        )

    stage.GetRootLayer().Save()
    stage = None
    os.replace(temporary, output)
    print(f"FINGER_MATERIAL_WRITTEN {output}", flush=True)
finally:
    app.close()
