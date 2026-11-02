from pathlib import Path
from urllib.parse import urlsplit,unquote,urljoin
from urllib.request import urlopen
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor
from packaging.utils import parse_wheel_filename
from packaging.tags import sys_tags
import json,subprocess,hashlib,os

b=Path('/root/autodl-tmp/isaac'); supported=set(sys_tags())
versions=[('isaacsim-extscache-kit','5.1.0.0'),('isaacsim-extscache-kit-sdk','5.1.0.0'),
 ('nvidia-cudnn-cu12','9.7.1.26'),('nvidia-cublas-cu12','12.8.3.14'),
 ('nvidia-cufft-cu12','11.3.3.41'),('nvidia-cusolver-cu12','11.7.2.55'),
 ('nvidia-cusparse-cu12','12.5.7.53'),('nvidia-nccl-cu12','2.26.2'),
 ('nvidia-cusparselt-cu12','0.6.3'),('triton','3.3.0'),
 ('nvidia-cuda-nvrtc-cu12','12.8.61'),('nvidia-curand-cu12','10.3.9.55'),
 ('nvidia-nvjitlink-cu12','12.8.61'),('isaacsim-kernel','5.1.0.0'),('isaacsim-ros2','5.1.0.0')]
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.links.extend(v for k,v in attrs if k=='href')
def resolve(item):
    name,version=item
    index=('https://pypi.nvidia.com/' if name.startswith('isaacsim') else 'https://pypi.tuna.tsinghua.edu.cn/simple/')+name+'/'
    with urlopen(index,timeout=20) as r:html=r.read().decode()
    parser=Links();parser.feed(html); candidates=[]
    for href in parser.links:
        url=urljoin(index,href);filename=unquote(urlsplit(url).path).split('/')[-1]
        if not filename.endswith('.whl'):continue
        try:_,v,_,tags=parse_wheel_filename(filename)
        except Exception:continue
        if str(v)==version and tags&supported:candidates.append((filename,url))
    assert len(candidates)==1,(name,len(candidates))
    filename,url=candidates[0];fragment=urlsplit(url).fragment
    assert fragment.startswith('sha256='),(name,'missing hash')
    digest=fragment.split('=',1)[1]
    if not name.startswith('isaacsim'):
        with urlopen('https://pypi.org/pypi/'+name+'/'+version+'/json',timeout=20) as r:official=json.load(r)
        match=[x for x in official['urls'] if x['filename']==filename]
        assert len(match)==1 and match[0]['digests']['sha256']==digest,(name,'official hash mismatch')
    return {'package':name,'filename':filename,'url':url.split('#')[0],'sha256':digest}
with ThreadPoolExecutor(max_workers=6) as pool:items=list(pool.map(resolve,versions))
(b/'logs/large-wheel-sources.json').write_text(json.dumps(items,indent=2))
def download(item):
    filename=item['filename']; tmp=b/'prefetch'/filename; dst=b/'wheels'/filename
    if dst.exists():return
    with (b/'logs'/('download-'+item['package']+'.log')).open('w') as log:
        subprocess.run(['aria2c','--allow-overwrite=false','--auto-file-renaming=false','--continue=true','--file-allocation=none','--max-connection-per-server=16','--split=16','--min-split-size=1M','--connect-timeout=15','--timeout=30','--max-tries=2','--summary-interval=30','--console-log-level=warn','--checksum=sha-256='+item['sha256'],'--dir='+str(b/'prefetch'),'--out='+filename,item['url']],stdout=log,stderr=subprocess.STDOUT,check=True)
    with tmp.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
    assert actual==item['sha256'],filename
    os.replace(tmp,dst)
    print('VERIFIED',filename,dst.stat().st_size,flush=True)
with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(download,items))
print('PREFETCH_COMPLETE',len(items),flush=True)
