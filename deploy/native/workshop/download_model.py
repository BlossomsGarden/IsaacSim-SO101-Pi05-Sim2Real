import urllib.request,json,concurrent.futures,subprocess,hashlib,time
from pathlib import Path
root=Path('/root/autodl-tmp/workshop');repo='aravindhs-NV/grootn16-finetune_sreetz-so101_teleop_vials_rack_left';revision='7efab50dfd58cd8f1831035fd86b65410b98c448'
url='https://huggingface.co/api/models/'+repo+'/tree/'+revision+'/checkpoint-10000?recursive=true&expand=false'
data=json.load(urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30))
exclude={'optimizer.pt','rng_state.pth','scheduler.pt','training_args.bin','trainer_state.json','wandb_config.json'}
files=[x for x in data if x['type']=='file' and Path(x['path']).name not in exclude]
dest=root/'models/groot-so101';dest.mkdir(parents=True,exist_ok=True)
small=[x for x in files if x['size']<10*1024*1024];large=[x for x in files if x['size']>=10*1024*1024]
print('MODEL_MANIFEST',repo,revision,'files',len(files),'bytes',sum(x['size'] for x in files),flush=True)
def fetch_small(x):
 target=dest/x['path'];target.parent.mkdir(parents=True,exist_ok=True)
 source='https://huggingface.co/'+repo+'/resolve/'+revision+'/'+x['path']
 content=urllib.request.urlopen(source,timeout=60).read();assert len(content)==x['size']
 target.write_bytes(content);print('MODEL_CONFIG_OK',x['path'],flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:list(ex.map(fetch_small,small))
lines=[]
for x in large:
 target=dest/x['path'];target.parent.mkdir(parents=True,exist_ok=True)
 lines+=['https://huggingface.co/'+repo+'/resolve/'+revision+'/'+x['path'],'  dir='+str(target.parent),'  out='+target.name,'  checksum=sha-256='+x['lfs']['oid']]
input_path=root/'logs/model-public-downloads.txt';input_path.write_text(chr(10).join(lines)+chr(10))
subprocess.run(['aria2c','--input-file='+str(input_path),'--continue=true','--check-integrity=true','--auto-file-renaming=false','--allow-overwrite=false','--file-allocation=none','--max-concurrent-downloads=2','--split=16','--max-connection-per-server=16','--min-split-size=4M','--max-tries=3','--retry-wait=3','--connect-timeout=20','--timeout=60','--console-log-level=warn','--summary-interval=30','--download-result=hide'],check=True)
result={'repo':repo,'revision':revision,'checkpoint':'checkpoint-10000','excluded_training_files':sorted(exclude),'files':[]}
for x in files:
 p=dest/x['path'];assert p.stat().st_size==x['size']
 result['files'].append({'path':str(p),'bytes':x['size'],'lfs_sha256':x.get('lfs',{}).get('oid')})
(root/'logs/model-download-manifest.json').write_text(json.dumps(result,indent=2))
print('MODEL_DOWNLOAD_PASS',flush=True)
