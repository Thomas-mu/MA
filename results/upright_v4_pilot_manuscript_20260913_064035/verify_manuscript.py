"""Verify documented manuscript edits and preserve the original evidence.

This performs file and document checks only, with no hardware or inference.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, re, runpy, shutil, zipfile
import xml.etree.ElementTree as ET

B=Path(__file__).resolve().parent
ROOT=B.parents[1]
OLD=ROOT/'results/upright_v4_finalization_20260912_103145'
TARGET=ROOT/'docs/Akz_Masterarbeit_Bericht(3).docx'
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
M='{http://schemas.openxmlformats.org/officeDocument/2006/math}'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def txt(e):return ''.join(x.text or '' for x in e.iter(W+'t'))
def norm(t):return re.sub(r'\s+','',t).replace('\u00ad','')
def flat(value):return ''.join(map(flat,value)) if isinstance(value,list) else value
def document(p):
    with zipfile.ZipFile(p) as z:
        assert len(z.namelist())==len(set(z.namelist())), 'Duplicate ZIP members'
        return ET.fromstring(z.read('word/document.xml'))
def main_blocks(root):
    elements=list(root.find(W+'body'))
    start=next(i for i,e in enumerate(elements) if txt(e)=='Einleitung, Problemstellung und Zielsetzung')
    return [txt(e) for e in elements[start:] if txt(e)]
def captions(path):
    with zipfile.ZipFile(path) as z:
        styles=ET.fromstring(z.read('word/styles.xml'))
        names={s.get(W+'styleId'):s.find(W+'name').get(W+'val') for s in styles if s.tag==W+'style' and s.find(W+'name') is not None}
    out=[]
    for p in document(path).iter(W+'p'):
        st=p.find('./'+W+'pPr/'+W+'pStyle')
        if st is not None and names.get(st.get(W+'val')) in ('Tabellenbeschriftung','Abbildungsbeschriftung'):out.append(txt(p))
    return out
def media(path):
    with zipfile.ZipFile(path) as z:
        return sorted(hashlib.sha256(z.read(name)).hexdigest() for name in z.namelist() if name.startswith('word/media/'))
def roman(n):
    pairs=[(100,'c'),(90,'xc'),(50,'l'),(40,'xl'),(10,'x'),(9,'ix'),(5,'v'),(4,'iv'),(1,'i')]
    out=''
    for value,symbol in pairs:
        while n>=value:out+=symbol;n-=value
    return out

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--install',action='store_true');args=parser.parse_args()
    state=json.loads((B/'initial_state.json').read_text())
    baseline=json.loads((B/'preservation_before.json').read_text())
    manifest=json.loads((B/'word_changes.json').read_text())
    backup=Path(state['backup']);assert sha(backup)==state['input_word_sha256']
    protected=[]
    for name,expected in baseline.items():
        if name==str(TARGET.relative_to(ROOT)):continue
        assert (ROOT/name).is_file(),('missing',name)
        assert sha(ROOT/name)==expected,('changed',name)
        protected.append(name)
    old=document(backup);draft=document(B/'thesis_pilot_unformatted.docx');final=document(B/'thesis_pilot.docx')
    expected=main_blocks(old)
    for change in manifest['changes']:
        before=flat(change['before']);after=flat(change['after'])
        matches=[i for i,v in enumerate(expected) if before in v]
        assert len(matches)==1,('ambiguous edit',before,matches)
        i=matches[0];expected[i]=expected[i].replace(before,after,1)
    actual=main_blocks(draft)
    for addition in manifest['additions']:
        text=addition['text'] if addition['kind']=='paragraph' else flat(addition['rows'])
        matches=[i for i,v in enumerate(actual) if v==text]
        assert len(matches)<=1,('ambiguous addition',text)
        if matches:actual.pop(matches[0])
        else:
            # Only the abstract is outside the compared main matter.
            assert text=='Zusammenfassung' or text.startswith(('Diese Arbeit untersucht einen lokalen Methodenvergleich','Die kontrollierte Testfolge umfasst','In der getrennten Laufzeitprüfung liegt')),('unmatched addition',text)
            assert text in txt(draft)
    assert list(map(norm,expected))==list(map(norm,actual)),'Unregistered body edit'
    assert list(map(norm,main_blocks(draft)))==list(map(norm,main_blocks(final))),'Body altered by export'
    # Title and unsigned declaration precede the new abstract and are preserved.
    def prefix(doc,anchor):
        out=[]
        for e in doc.find(W+'body'):
            if txt(e)==anchor:break
            if txt(e):out.append(norm(txt(e)))
        return out
    assert prefix(old,'Inhaltsverzeichnis')==prefix(draft,'Zusammenfassung')==prefix(final,'Zusammenfassung')
    canonical=runpy.run_path(str(OLD/'verify_completion.py'))['canonical_math']
    equations=[[canonical(e) for e in doc.iter(M+'oMath')] for doc in (old,draft,final)]
    assert equations[0]==equations[1]==equations[2] and len(equations[0])==3
    assert media(backup)==media(B/'thesis_pilot_unformatted.docx')==media(B/'thesis_pilot.docx')
    with zipfile.ZipFile(B/'thesis_pilot.docx') as z:
        rels=ET.fromstring(z.read('_rels/.rels'))
        assert sum(r.get('Type')=='http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties' for r in rels)==1
    caps=captions(B/'thesis_pilot.docx');expected_caps=captions(backup)
    expected_caps=[s.replace('Tabelle A-4: Verwechslungszahlen je vollständiger Aufnahme und Methode','Tabelle A-4: Verwechslungszahlen je Aufnahme und Methode im Abschnitt [180,300) s') for s in expected_caps]
    expected_caps+=['Tabelle 7-10: Forschungsfragen, Hypothesen und Gültigkeitsgrenzen']
    assert sorted(caps)==sorted(expected_caps)
    numbers=[re.match(r'^(Tabelle|Abbildung) ([A\d]+-\d+):',c).group(0) for c in caps]
    assert len(numbers)==len(set(numbers))==41
    layout=json.loads((B/'thesis_pilot_layout_audit.json').read_text())
    assert layout['indexes_count']==3 and layout['tables']==36
    top=[h['list_label'] for h in layout['headings'] if h['style']=='Heading 1' and h['list_label']]
    assert top==list(map(str,range(1,11))),top
    pages=(B/'layout_review/pages.txt').read_text().split('\f')
    if not pages[-1].strip():pages.pop()
    footer=lambda page:page.strip().splitlines()[-1].strip()
    main_start=next(i for i,p in enumerate(pages) if footer(p)=='1' and 'Einleitung, Problemstellung und Zielsetzung' in p)
    for i,page in enumerate(pages[1:],1):
        expected_footer=roman(i) if i<main_start else str(i-main_start+1)
        assert footer(page)==expected_footer,('page footer',i+1,footer(page),expected_footer)
    for index in layout['indexes'][1:]:
        for entry in index['text'].splitlines():
            title,page=entry.rsplit('\t',1);key=title.split(':',1)[0]+':'
            assert norm(key) in norm(pages[int(page)+main_start-1]),('caption index page',key,page)
    for key,first_row in [('Tabelle A-4:','Normal vorher'),('Tabelle 7-10:','FF1')]:
        page=next(p for p in pages[main_start:] if key in p)
        assert first_row in page,('caption detached from table',key)
    bounds=json.loads((B/'layout_review/text_bounds_audit.json').read_text())
    assert len(bounds)==len(pages) and all(not r['outside_24pt_horizontal_15pt_vertical'] for r in bounds)
    for forbidden in ('{{','XXXXX','Es konnten keine Einträge','Fehler! Textmarke'):
        assert forbidden not in txt(final),forbidden
    if args.install:
        assert sha(TARGET)==state['input_word_sha256'],'Concurrent Word edit; target left untouched'
        shutil.copy2(B/'thesis_pilot.docx',TARGET)
    else:
        assert sha(TARGET) in (state['input_word_sha256'],sha(B/'thesis_pilot.docx'))
    result={'utc':datetime.now(timezone.utc).isoformat(),'protected_unchanged_files':len(protected),
        'changed_or_missing_protected_files':[], 'authorized_word_updated':sha(TARGET)==sha(B/'thesis_pilot.docx'),
        'word_sha256':sha(B/'thesis_pilot.docx'),'backup_sha256':sha(backup),'pdf_sha256':sha(B/'thesis_pilot.pdf'),
        'documented_existing_changes':len(manifest['changes']),'documented_additions':len(manifest['additions']),
        'only_documented_body_changes':True,'original_equations_preserved':len(equations[0]),
        'original_figures_preserved':6,'tables':36,'unique_captions':len(caps),'updated_indexes':3,
        'main_chapters':'1–10','pdf_pages':len(pages),'roman_numbered_front_pages':main_start-1,
        'arabic_numbered_main_pages':len(pages)-main_start,'footer_numbering_contiguous':True,
        'caption_index_pages_verified':True,'new_caption_and_table_same_page':True,
        'no_text_outside_checked_page_bounds':True,'personal_declaration_unchanged':True,
        'original_requirements_and_hypotheses_preserved':True,'hardware_measurements_started':False,
        'pwm_commands_issued':False,'new_model_decisions_or_training':False,
        'frozen_models_data_sources_historical_reports_unchanged':True,'physical_rpm_or_sensor_clock_proven':False,
        'personal_author_review_or_signature_completed':False}
    (B/'manuscript_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
