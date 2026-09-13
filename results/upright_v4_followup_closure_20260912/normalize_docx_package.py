"""Normalize the core-properties relationship after Writer export; no body edits."""
from pathlib import Path
from zipfile import ZipFile
from datetime import datetime, timezone
import hashlib, json
from lxml import etree
B=Path(__file__).resolve().parent
p=B/'thesis_reviewed.docx'
before=hashlib.sha256(p.read_bytes()).hexdigest()
temporary=B/'thesis_reviewed_package.tmp'
changes=[]
with ZipFile(p) as zi, ZipFile(temporary,'w') as zo:
    assert len(zi.namelist())==len(set(zi.namelist()))
    for item in zi.infolist():
        data=zi.read(item)
        if item.filename=='_rels/.rels':
            tree=etree.fromstring(data)
            for rel in tree:
                old=rel.get('Type','')
                correct='http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties'
                if old.endswith('/metadata/core-properties') and old!=correct:
                    rel.set('Type',correct); changes.append({'before':old,'after':correct})
            data=etree.tostring(tree,xml_declaration=True,encoding='UTF-8',standalone=True)
        zo.writestr(item,data)
temporary.replace(p)
result={'utc':datetime.now(timezone.utc).isoformat(),'before_sha256':before,'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'changes':changes,'body_and_layout_unchanged':True}
(B/'docx_package_normalization.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
