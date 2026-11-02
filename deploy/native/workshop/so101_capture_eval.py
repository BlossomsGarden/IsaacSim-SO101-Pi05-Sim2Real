"""Bounded headless evaluation using the Workshop task and existing GR00T client.

Uses the tutorial's seed, initial actions, camera mapping and action horizon.
Adds finite episode limits, observation recordings and JSON evidence.
"""
import argparse
import json
import random
import subprocess
import time
from pathlib import Path
from isaaclab.app import AppLauncher

parser=argparse.ArgumentParser()
parser.add_argument('--mode',choices=['smoke','inference'],default='smoke')
parser.add_argument('--task',default='Lerobot-So101-Teleop-Vials-To-Rack-Eval')
parser.add_argument('--num_envs',type=int,default=1)
parser.add_argument('--num_episodes',type=int,default=3)
parser.add_argument('--seed',type=int,default=1984)
parser.add_argument('--policy_host',default='127.0.0.1')
parser.add_argument('--policy_port',type=int,default=5555)
AppLauncher.add_app_launcher_args(parser)
args=parser.parse_args()
assert args.num_envs==1,'This evidence harness records one environment.'
args.enable_cameras=True
app=AppLauncher(args).app
env=None;writer=None;video_stderr=None;trace=None
root=Path('/root/autodl-tmp/workshop')
out=root/'results'/args.mode
out.mkdir(parents=True,exist_ok=True)
result={'status':'running','mode':args.mode,'task':args.task,'seed':args.seed,'episodes':[],'policy_queries':0,'query_latency_ms':[],'total_steps':0,'policy_inference':args.mode=='inference'}
start=time.monotonic()
try:
    import gymnasium as gym
    import numpy as np
    import torch
    from PIL import Image
    import isaaclab_tasks
    from isaaclab_tasks.utils import parse_env_cfg
    import sim_to_real_so101.tasks

    random.seed(args.seed);np.random.seed(args.seed);torch.manual_seed(args.seed);torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.deterministic=True;torch.backends.cudnn.benchmark=False
    cfg=parse_env_cfg(args.task,device=args.device,num_envs=1,use_fabric=True)
    cfg.seed=args.seed
    env=gym.make(args.task,cfg=cfg)
    print('SCENE_CREATED',env.observation_space,env.action_space,flush=True)
    cameras={}
    for name in env.unwrapped.scene.keys():
        if name.startswith('camera_'):
            c=getattr(env.unwrapped.scene.cfg,name)
            cameras[name.replace('camera_','')]={'height':c.height,'width':c.width}
    result['cameras']=cameras
    policy=None
    if args.mode=='inference':
        from sim_to_real_so101.utils.lerobot_interface import LeRobotSO101Interface,GR00TRemotePolicy
        interface=LeRobotSO101Interface(device=env.unwrapped.device,port=None,id='leader_arm_1',cameras=cameras,fps=30,kind='follower',rename_map={'external_D455':'front','ego':'wrist'})
        interface.init_device(visualize=False)
        policy=GR00TRemotePolicy(robot_iface=interface,host=args.policy_host,port=args.policy_port,action_horizon=16,lang_instruction='Pick up the vial and place it in the yellow rack')
        policy.connect()
        print('POLICY_CONNECTED',args.policy_host,args.policy_port,flush=True)
    obs,_=env.reset()
    if policy:policy.reset()
    initial=torch.tensor([-0.2736,-0.6109,-0.0745,1.5148,-1.6034,-0.1465],device=env.unwrapped.device)
    actions=torch.zeros(env.action_space.shape,device=env.unwrapped.device)
    trace=(out/'actions.jsonl').open('w')
    episode=0;step=0
    max_steps=40 if args.mode=='smoke' else args.num_episodes*(env.unwrapped.max_episode_length+20)
    while app.is_running() and result['total_steps']<max_steps:
        with torch.inference_mode():
            if args.mode=='smoke' or step<10:actions[:]=initial
            else:
                query=len(policy._action_queue)==0
                before=time.monotonic()
                actions[:]=policy.get_action(obs['policy']['joint_pos_obs'][0].clone(),obs['visual'],log=False)
                assert torch.isfinite(actions).all(),'Non-finite policy action'
                if query:
                    latency=(time.monotonic()-before)*1000
                    result['policy_queries']+=1;result['query_latency_ms'].append(round(latency,3))
                    print('POLICY_QUERY',result['policy_queries'],'latency_ms',round(latency,1),flush=True)
            obs,rewards,terminated,truncated,info=env.step(actions)
            step+=1;result['total_steps']+=1
            views=[]
            for key in ['rgb_external_D455','rgb_ego']:
                frame=obs['visual'][key][0].detach().cpu().numpy()
                frame=frame[...,:3]
                assert np.isfinite(frame).all(),key
                if frame.dtype!=np.uint8:
                    if frame.max()<=1.0:frame=frame*255
                    frame=np.clip(frame,0,255).astype(np.uint8)
                views.append(frame)
            combined=np.concatenate(views,axis=1)
            if writer is None:
                h,w=combined.shape[:2]
                video_stderr=(out/'ffmpeg.log').open('wb')
                writer=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{w}x{h}','-framerate','30','-i','-','-an','-c:v','libx264','-crf','22','-pix_fmt','yuv420p',str(out/'front-wrist.mp4')],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=video_stderr)
            writer.stdin.write(combined.tobytes())
            if step in (1,100,250):Image.fromarray(combined).save(out/f'episode-{episode+1:02d}-step-{step:03d}.png')
            trace.write(json.dumps({'episode':episode+1,'step':step,'action':actions[0].detach().cpu().tolist(),'terminated':bool(terminated.item()),'truncated':bool(truncated.item())})+chr(10))
            if terminated.item() or truncated.item():
                success=bool(terminated.item() and not truncated.item())
                result['episodes'].append({'episode':episode+1,'steps':step,'success':success,'terminated':bool(terminated.item()),'truncated':bool(truncated.item())})
                Image.fromarray(combined).save(out/f'episode-{episode+1:02d}-final.png')
                print('EPISODE_RESULT',json.dumps(result['episodes'][-1]),flush=True)
                episode+=1
                (out/'result.json').write_text(json.dumps(result,indent=2))
                if args.mode=='inference' and episode>=args.num_episodes:break
                obs,_=env.reset()
                if policy:policy.reset()
                step=0
    if args.mode=='inference':assert len(result['episodes'])==args.num_episodes,'Requested episodes did not complete'
    result['status']='pass'
    result['successes']=sum(x['success'] for x in result['episodes'])
    result['success_rate']=result['successes']/len(result['episodes']) if result['episodes'] else None
    result['elapsed_seconds']=round(time.monotonic()-start,2)
    Image.fromarray(combined).save(out/'last-frame.png')
    print('SO101_TEST_PASS',json.dumps(result),flush=True)
except Exception as e:
    result['status']='failed';result['error_type']=type(e).__name__;result['error']=str(e)
    import traceback
    traceback.print_exc()
    print('SO101_TEST_FAILED',json.dumps(result),flush=True)
    raise
finally:
    if trace:trace.close()
    if writer:
        writer.stdin.close()
        result['video_exit']=writer.wait(timeout=30)
    if video_stderr:video_stderr.close()
    (out/'result.json').write_text(json.dumps(result,indent=2)+chr(10))
    if env:env.close()
    app.close(skip_cleanup=False)
