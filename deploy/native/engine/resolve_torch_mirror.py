import urllib.request, urllib.parse, json
from html.parser import HTMLParser
from pathlib import Path
class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            for k,v in attrs:
                if k=='href': self.links.append(v)
def exact(index,filename):
    with urllib.request.urlopen(index,timeout=20) as r: html=r.read().decode()
    p=Links();p.feed(html)
    urls=[urllib.parse.urljoin(index,h) for h in p.links if urllib.parse.unquote(urllib.parse.urlsplit(h).path).split('/')[-1]==filename]
    assert len(urls)==1,(index,filename,len(urls))
    return urls[0]
result=[]
for pkg,filename in [('torch','torch-2.7.0+cu128-cp311-cp311-manylinux_2_28_x86_64.whl'),('torchvision','torchvision-0.22.0+cu128-cp311-cp311-manylinux_2_28_x86_64.whl')]:
    official=exact('https://download.pytorch.org/whl/cu128/'+pkg+'/',filename)
    mirror=exact('https://mirrors.nju.edu.cn/pytorch/whl/cu128/'+pkg+'/',filename)
    digest=urllib.parse.urlsplit(official).fragment
    assert digest.startswith('sha256=') and digest==urllib.parse.urlsplit(mirror).fragment
    result.append({'package':pkg,'official':official,'mirror':mirror,'sha256':digest[7:]})
base=Path('/root/autodl-tmp/isaac')
(base/'logs/torch-download-sources.json').write_text(json.dumps(result,indent=2))
(base/'scripts/torch-mirror-requirements.txt').write_text('\n'.join(r['mirror'] for r in result)+'\n')
print(json.dumps(result,indent=2),flush=True)
