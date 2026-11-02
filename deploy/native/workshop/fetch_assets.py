from pathlib import Path
import urllib.request,json,re,hashlib,concurrent.futures,time
root=Path('/root/autodl-tmp/workshop/Sim-to-Real-SO-101-Workshop-main')
files=[]
for p in root.rglob('*'):
 if not p.is_file() or p.stat().st_size>1024:continue
 text=p.read_text(errors='ignore')
 if not text.startswith('version https://git-lfs.github.com/spec/v1'):continue
 files.append({'path':p,'oid':re.search(r'oid sha256:([a-f0-9]+)',text)[1],'size':int(re.search(r'size (\d+)',text)[1])})
print('LFS_OBJECTS',len(files),'BYTES',sum(x['size'] for x in files),flush=True)
payload={'operation':'download','transfers':['basic'],'objects':[{'oid':x['oid'],'size':x['size']} for x in files]}
req=urllib.request.Request('https://github.com/isaac-sim/Sim-to-Real-SO-101-Workshop.git/info/lfs/objects/batch',data=json.dumps(payload).encode(),headers={'Accept':'application/vnd.git-lfs+json','Content-Type':'application/vnd.git-lfs+json','User-Agent':'git-lfs/3.7'})
reply=json.load(urllib.request.urlopen(req,timeout=30))
objects={o['oid']:o for o in reply['objects']}
def fetch(item):
 obj=objects[item['oid']]
 if 'error' in obj:raise RuntimeError('LFS object unavailable: '+str(item['path'].relative_to(root)))
 action=obj['actions']['download'];request=urllib.request.Request(action['href'],headers=action.get('header',{}))
 tmp=item['path'].with_suffix(item['path'].suffix+'.part');h=hashlib.sha256();size=0
 with urllib.request.urlopen(request,timeout=60) as src,tmp.open('wb') as out:
  while True:
   block=src.read(1024*1024)
   if not block:break
   out.write(block);h.update(block);size+=len(block)
 assert size==item['size'] and h.hexdigest()==item['oid'],str(item['path'])
 tmp.replace(item['path'])
 print('ASSET_OK',item['path'].relative_to(root),size,flush=True)
 return {'path':str(item['path'].relative_to(root)),'size':size,'sha256':h.hexdigest()}
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:results=list(ex.map(fetch,files))
Path('/root/autodl-tmp/workshop/logs/assets-manifest.json').write_text(json.dumps(results,indent=2))
