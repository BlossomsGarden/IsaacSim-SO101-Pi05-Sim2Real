import json
import os
from pathlib import Path
import time

os.environ['OMNI_KIT_ACCEPT_EULA'] = 'YES'
start = time.monotonic()
print('SMOKE_START', flush=True)
from isaacsim import SimulationApp
app = SimulationApp({'headless': True, 'renderer': 'RaytracedLighting',
                     'width': 128, 'height': 128, 'multi_gpu': False})
print('ENGINE_STARTED', flush=True)
try:
    import numpy as np
    import omni.usd
    from pxr import UsdLux
    from isaacsim.core.api import World
    from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid
    from isaacsim.sensors.camera import Camera
    from isaacsim.core.utils.viewports import set_camera_view
    from PIL import Image

    world = World(stage_units_in_meters=1.0, physics_dt=1.0/60.0,
                  rendering_dt=1.0/60.0, backend='torch', device='cuda:0')
    world.scene.add(FixedCuboid(prim_path='/World/Ground', name='ground',
        position=np.array([0.0, 0.0, -0.05]), scale=np.array([2.0, 2.0, 0.1]),
        color=np.array([0.15, 0.18, 0.2])))
    cube = world.scene.add(DynamicCuboid(prim_path='/World/Cube', name='cube',
        position=np.array([0.0, 0.0, 0.6]), size=0.1, mass=0.05,
        color=np.array([0.85, 0.15, 0.05])))
    stage = omni.usd.get_context().get_stage()
    light = UsdLux.DomeLight.Define(stage, '/World/Light')
    light.CreateIntensityAttr(1200.0)
    camera = Camera(prim_path='/World/Camera', name='camera', frequency=30,
                    resolution=(128,128), position=np.array([1.0,1.0,0.8]))
    set_camera_view(eye=np.array([1.0,1.0,0.8]), target=np.array([0.0,0.0,0.1]),
                    camera_prim_path='/World/Camera')
    world.reset()
    camera.initialize()
    z_initial = float(cube.get_world_pose()[0][2])
    for step in range(120):
        world.step(render=True)
        if step in (0,59,119):
            print('STEP',step,'CUBE_Z',float(cube.get_world_pose()[0][2]),flush=True)
    z_final = float(cube.get_world_pose()[0][2])
    rgba = np.asarray(camera.get_rgba())
    assert z_initial > 0.4 and 0.02 < z_final < 0.15, (z_initial,z_final)
    assert rgba.shape == (128,128,4), rgba.shape
    assert np.isfinite(rgba).all() and float(np.ptp(rgba[:,:,:3])) > 1
    out = Path('/root/autodl-tmp/isaac/logs')
    Image.fromarray(rgba.astype(np.uint8)).save(out/'smoke-camera.png')
    result={'engine_start':True,'physics_fall_and_contact':True,
            'rgb_camera':True,'image_shape':list(rgba.shape),
            'z_initial':z_initial,'z_final':z_final,
            'elapsed_seconds':round(time.monotonic()-start,2)}
    (out/'smoke-result.json').write_text(json.dumps(result,indent=2))
    print('SMOKE_PASS',json.dumps(result),flush=True)
except Exception:
    import traceback
    traceback.print_exc()
    print('SMOKE_FAILED', flush=True)
    raise
finally:
    app.close(skip_cleanup=False)
    print('ENGINE_CLOSED',flush=True)
