"""Verify permitted manuscript edits and protected evidence; optionally install Word."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, re, runpy, shutil, zipfile
import xml.etree.ElementTree as ET
B=Path(__file__).resolve().parent
ROOT=B.parents[1]
OLD=ROOT/'results/upright_v4_finalization_20260912_103145'
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
M='{http://schemas.openxmlformats.org/officeDocument/2006/math}'
TARGET=ROOT/'docs/Akz_Masterarbeit_Bericht(3).docx'
def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def txt(e):return ''.join(x.text or '' for x in e.iter(W+'t'))
def norm(t):return re.sub(r'\s+','',t).replace('\u00ad','')
def document(p):
    with zipfile.ZipFile(p) as z:
        assert len(z.namelist())==len(set(z.namelist())), 'Duplicate ZIP members'
        return ET.fromstring(z.read('word/document.xml'))
def main_blocks(root):
    elements=list(root.find(W+'body'))
    start=next(i for i,e in enumerate(elements) if txt(e)=='Einleitung, Problemstellung und Zielsetzung')
    return [txt(e) for e in elements[start:] if txt(e)]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--install',action='store_true');args=parser.parse_args()
    state=json.loads((B/'review_initial_state.json').read_text())
    baseline=json.loads((B/'preservation_before_review.json').read_text())
    manifest=json.loads((B/'word_revision_changes.json').read_text())
    backup=Path(state['backup']);assert sha(backup)==state['word_sha256']
    protected=[]
    for name, expected in baseline.items():
        if name==str(TARGET.relative_to(ROOT)):continue
        assert (ROOT/name).is_file(), ('missing',name)
        assert sha(ROOT/name)==expected, ('changed',name)
        protected.append(name)
    old=document(backup);draft=document(B/'thesis_reviewed_unformatted.docx');final=document(B/'thesis_reviewed.docx')
    expected=main_blocks(old)
    for c in manifest['changes']:
        before=c['before'];after=c['after']
        if isinstance(before,list):before=''.join(before);after=''.join(after)
        matches=[i for i,v in enumerate(expected) if before in v]
        assert len(matches)==1, ('ambiguous permitted edit',before,matches)
        i=matches[0];expected[i]=expected[i].replace(before,after,1)
    actual=main_blocks(draft)
    anchor=actual.index('Lesen der Messdateien')
    added=actual[anchor-4:anchor]
    assert added[0].startswith('Die folgenden Verwechslungszahlen')
    assert added[1]=='Tabelle A-4: Verwechslungszahlen je vollständiger Aufnahme und Methode'
    assert added[2].startswith('Aufnahme / Methodegültig / ungültig')
    assert added[3].startswith('Die nachträgliche Aufschlüsselung')
    del actual[anchor-4:anchor]
    assert list(map(norm,expected))==list(map(norm,actual)), 'Unregistered body edit'
    assert list(map(norm,main_blocks(draft)))==list(map(norm,main_blocks(final))), 'Body altered by export'
    canonical=runpy.run_path(str(OLD/'verify_completion.py'))['canonical_math']
    equations=[[canonical(e) for e in doc.iter(M+'oMath')] for doc in (old,draft,final)]
    assert equations[0]==equations[1]==equations[2] and len(equations[0])==3
    with zipfile.ZipFile(B/'thesis_reviewed.docx') as z:
        styles=ET.fromstring(z.read('word/styles.xml'))
        names={s.attrib.get(W+'styleId'):s.find(W+'name').attrib.get(W+'val') for s in styles if s.tag==W+'style' and s.find(W+'name') is not None}
        rels=ET.fromstring(z.read('_rels/.rels'))
        assert sum(r.get('Type')=='http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties' for r in rels)==1
    caps=[]
    for p in final.iter(W+'p'):
        st=p.find('./'+W+'pPr/'+W+'pStyle')
        if st is not None and names.get(st.get(W+'val')) in ('Tabellenbeschriftung','Abbildungsbeschriftung'):caps.append(txt(p))
    previous=json.loads((OLD/'word_build_manifest.json').read_text())
    expected_caps=[x['title'] for x in previous['tables']+previous['figures']]+[added[1]]
    assert sorted(caps)==sorted(expected_caps)
    numbers=[re.match(r'^(Tabelle|Abbildung) ([A\d]+-\d+):',c).group(0) for c in caps]
    assert len(numbers)==len(set(numbers))==40
    layout=json.loads((B/'thesis_reviewed_layout_audit.json').read_text());assert layout['indexes_count']==3 and layout['tables']==35
    top=[h['list_label'] for h in layout['headings'] if h['style']=='Heading 1' and h['list_label']]
    assert top==list(map(str,range(1,11))),top
    pages=(B/'layout_review/pages.txt').read_text().split('\f')
    if not pages[-1].strip():pages.pop()
    for i,page in enumerate(pages[1:],1):
        expected_footer=['i','ii','iii','iv','v','vi'][i-1] if i<=6 else str(i-6)
        assert page.strip().splitlines()[-1].strip()==expected_footer, ('page footer',i+1)
    for index in layout['indexes'][1:]:
        for entry in index['text'].splitlines():
            title,page=entry.rsplit('\t',1);key=title.split(':',1)[0]+':'
            assert norm(key) in norm(pages[int(page)+6]), ('caption index page',key,page)
    a4=next(i for i,page in enumerate(pages) if 'Tabelle A-4:' in page and i>6)
    assert 'Aufnahme / Methode' in pages[a4] and 'Normal vorher' in pages[a4], 'Caption separated from table'
    bounds=json.loads((B/'layout_review/text_bounds_audit.json').read_text())
    assert len(bounds)==len(pages) and all(not row['outside_24pt_horizontal_15pt_vertical'] for row in bounds)
    alltext=txt(final)
    for forbidden in ('{{','XXXXX','Es konnten keine Einträge','Fehler! Textmarke'):
        assert forbidden not in alltext,forbidden
    if args.install:
        assert sha(TARGET)==state['word_sha256'], 'Concurrent Word edit; target left untouched'
        shutil.copy2(B/'thesis_reviewed.docx',TARGET)
    else:
        assert sha(TARGET) in (state['word_sha256'],sha(B/'thesis_reviewed.docx'))
    result={'utc':datetime.now(timezone.utc).isoformat(),'protected_unchanged_files':len(protected),'changed_or_missing_protected_files':[],
            'authorized_word_updated':sha(TARGET)==sha(B/'thesis_reviewed.docx'),'word_sha256':sha(B/'thesis_reviewed.docx'),'backup_sha256':sha(backup),
            'documented_existing_text_changes':len(manifest['changes']),'only_documented_body_changes':True,'new_per_record_table':'A-4',
            'original_equations_preserved':len(equations[0]),'tables':35,'figures':6,'unique_captions':len(caps),'updated_indexes':3,
            'main_chapters':'1–10','pdf_pages':len(pages),'footer_numbering_contiguous':True,'caption_index_pages_verified':True,
            'new_caption_and_table_same_page':True,'no_text_outside_checked_page_bounds':True,
            'pdf_sha256':sha(B/'thesis_reviewed.pdf'),'hardware_measurements_started':False,'pwm_commands_issued':False,
            'frozen_models_data_sources_historical_reports_unchanged':True,'physical_rpm_or_sensor_clock_proven':False,
            'personal_author_review_or_signature_completed':False}
    (B/'review_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
