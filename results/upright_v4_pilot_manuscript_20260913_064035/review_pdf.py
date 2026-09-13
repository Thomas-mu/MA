"""Create contact sheets and text-bound audit for the final PDF, for human inspection."""
from pathlib import Path
import subprocess,json,xml.etree.ElementTree as ET
from PIL import Image,ImageDraw
B=Path(__file__).resolve().parent;D=B/'layout_review';D.mkdir(exist_ok=True)
pdf=B/'thesis_pilot.pdf'
# Only this script's generated page images/contact sheets are replaced. A
# shorter re-export must not retain pages from an earlier layout iteration.
for pattern in ('page-*.png','contact_*.png'):
 for old in D.glob(pattern):old.unlink()
subprocess.run(['pdftotext','-layout',str(pdf),str(D/'pages.txt')],check=True)
subprocess.run(['pdftotext','-bbox-layout',str(pdf),str(D/'bounds.xml')],check=True)
subprocess.run(['pdftoppm','-r','42','-png',str(pdf),str(D/'page')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
ns={'x':'http://www.w3.org/1999/xhtml'}
r=ET.parse(D/'bounds.xml');audit=[]
for i,p in enumerate(r.findall('.//x:page',ns),1):
 w,h=float(p.attrib['width']),float(p.attrib['height']);words=p.findall('.//x:word',ns)
 outside=[dict(text=x.text,**x.attrib) for x in words if float(x.attrib['xMin'])<24 or float(x.attrib['xMax'])>w-24 or float(x.attrib['yMin'])<15 or float(x.attrib['yMax'])>h-15]
 audit.append(dict(pdf_page=i,words=len(words),outside_24pt_horizontal_15pt_vertical=outside))
images=sorted(D.glob('page-*.png'),key=lambda p:int(p.stem.split('-')[-1]))
for start in range(0,len(images),12):
 group=images[start:start+12];thumbs=[]
 for p in group:
  im=Image.open(p).convert('RGB');im.thumbnail((300,425));thumbs.append(im)
 sheet=Image.new('RGB',(3*320,4*455),'#d8d8d8');draw=ImageDraw.Draw(sheet)
 for j,im in enumerate(thumbs):
  x=(j%3)*320+10;y=(j//3)*455+22;sheet.paste(im,(x,y));draw.text((x,y-16),'PDF-Seite '+str(start+j+1),fill='black')
 sheet.save(D/f'contact_{start+1:03d}_{start+len(group):03d}.png')
(D/'text_bounds_audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'pages':len(audit),'pages_outside_bounds':[v['pdf_page'] for v in audit if v['outside_24pt_horizontal_15pt_vertical']],'contact_sheets':len(list(D.glob('contact_*.png')))},indent=2))
