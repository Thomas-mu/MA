#!/usr/bin/env python3
"""Check package, refreshed indexes and PDF bounds; build page contact sheets."""
from pathlib import Path
from zipfile import ZipFile
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/phone_vibration_word_revision_20260919'
NAME='Akz_Masterarbeit_Bericht(3)'


def main():
    path=OUT/(NAME+'.docx');temporary=OUT/'normalized_package.tmp'
    changes=[]
    with ZipFile(path) as zi, ZipFile(temporary,'w') as zo:
        assert zi.testzip() is None
        for item in zi.infolist():
            data=zi.read(item)
            if item.filename=='_rels/.rels':
                tree=ET.fromstring(data)
                for rel in tree:
                    old=rel.get('Type','');correct='http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties'
                    if old.endswith('/metadata/core-properties') and old!=correct:
                        rel.set('Type',correct);changes.append({'before':old,'after':correct})
                if changes:data=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
            zo.writestr(item,data)
    temporary.replace(path)
    with ZipFile(path) as z:
        w={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        tree=ET.fromstring(z.read('word/document.xml'))
        txt='\n'.join(''.join(p.itertext()) for p in tree.findall('.//w:p',w))
        assert 'Laborversuch' not in txt and not re.search(r'\bim Labor\b',txt,re.I)
        assert '615,659' in txt and '19,061' in txt and '0,477202599144' in txt
        assert '0,544357966' not in txt
        assert len(tree.findall('.//w:sectPr',w))==3
        captions=[''.join(p.itertext()) for p in tree.findall('.//w:body/w:p',w) if ''.join(p.itertext()).startswith(('Abbildung ','Tabelle '))]
        assert len([c for c in captions if c.startswith('Abbildung 6-') or c.startswith('Abbildung 7-')])==9
        assert len(captions)==len(set(captions))
    layout=json.loads((OUT/(NAME+'_layout_audit.json')).read_text())
    assert layout['indexes_count']==3
    assert [h['list_label'] for h in layout['headings'] if h['style']=='Heading 1' and h['list_label']]==[str(i) for i in range(1,11)]
    ns={'h':'http://www.w3.org/1999/xhtml'}
    pages=ET.parse(OUT/'pdf_bounds.html').findall('.//h:page',ns)
    audit={'package_normalizations':changes,'pages':len(pages),'page_checks':[],'new_figures':9,'indexes_refreshed':3}
    for i,page in enumerate(pages,1):
        words=page.findall('h:word',ns);width=float(page.get('width'));height=float(page.get('height'))
        overflow=[x.text for x in words if float(x.get('xMin'))<0 or float(x.get('yMin'))<0 or float(x.get('xMax'))>width+1 or float(x.get('yMax'))>height+1]
        # Most text should stay within the 2.5 cm body margin; image text may not.
        edge_words=[x.text for x in words if float(x.get('xMax'))>width-38 or float(x.get('xMin'))<38]
        audit['page_checks'].append({'page':i,'words':len(words),'overflow':overflow,'near_edge':edge_words})
        assert not overflow,(i,overflow)
    for p in (OUT/'previews').glob('page-*.png'):
        if int(p.stem.split('-')[-1])>len(pages):
            archive=OUT/'previews/superseded';archive.mkdir(exist_ok=True)
            p.replace(archive/p.name)
    previews=sorted((OUT/'previews').glob('page-*.png'))
    assert len(previews)==len(pages)
    for n in range(0,len(previews),12):
        sheet=Image.new('RGB',(4*390,3*570),'#dfe4e8');draw=ImageDraw.Draw(sheet)
        for i,p in enumerate(previews[n:n+12]):
            im=Image.open(p).convert('RGB');im.thumbnail((368,520))
            x=(i%4)*390+(390-im.width)//2;y=(i//4)*570+28
            sheet.paste(im,(x,y));draw.text(((i%4)*390+12,(i//4)*570+8),p.stem,fill='#172c3d')
        sheet.save(OUT/'previews'/f'contact-{n//12+1:02}.png')
    audit['docx_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    audit['pdf_sha256']=hashlib.sha256((OUT/(NAME+'.pdf')).read_bytes()).hexdigest()
    audit['automated_status']='passed'
    (OUT/'document_checks.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:v for k,v in audit.items() if k!='page_checks'},indent=2))


if __name__=='__main__':main()
