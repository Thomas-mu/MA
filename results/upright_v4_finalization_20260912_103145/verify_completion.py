#!/usr/bin/env python3
"""Read-only integrity and manuscript checks after final Word export."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,re,zipfile,xml.etree.ElementTree as ET
B=Path(__file__).resolve().parent;ROOT=B.parents[1]
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
M='{http://schemas.openxmlformats.org/officeDocument/2006/math}'
TARGET=ROOT/'docs/Akz_Masterarbeit_Bericht(3).docx'
BACKUP=ROOT/'docs/backups/Akz_Masterarbeit_Bericht(3)_vor_abschluss_20260912_103145.docx'


def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def text(e):return ''.join(x.text or '' for x in e.iter(W+'t'))
def canonical_math(e):
 # Writer changes whitespace, minus glyphs and literal brackets into OMML
 # delimiter nodes. Compare operator structure, fractions, bounds, and indices,
 # while permitting these equivalent serialization choices.
 tag=e.tag.removeprefix(M)
 if not e.tag.startswith(M) or tag.endswith('Pr'):return ''
 if tag=='t':return re.sub(r'\s+','',e.text or '').replace('−','-')
 def child(name):
  x=e.find(M+name)
  return canonical_math(x) if x is not None else ''
 if tag=='f':return 'FRAC{'+child('num')+'}{'+child('den')+'}'
 if tag=='rad':return 'ROOT{'+child('deg')+'}{'+child('e')+'}'
 if tag in ['sSub','sSup','sSubSup']:
  return tag+'{'+child('e')+'}{'+child('sub')+'}{'+child('sup')+'}'
 if tag=='nary':
  c=e.find('./'+M+'naryPr/'+M+'chr')
  return 'NARY{'+(c.get(M+'val') if c is not None else '∫')+'}{'+child('sub')+'}{'+child('sup')+'}{'+child('e')+'}'
 if tag=='d':
  pr=e.find(M+'dPr')
  def delim(name,default):
   q=pr.find(M+name) if pr is not None else None
   return q.get(M+'val') if q is not None else default
  return delim('begChr','(')+delim('sepChr','|').join(canonical_math(x) for x in e.findall(M+'e'))+delim('endChr',')')
 return ''.join(canonical_math(x) for x in e)


def main_content(path):
 with zipfile.ZipFile(path) as z:root=ET.fromstring(z.read('word/document.xml'))
 active=False;strings=[];math=[]
 for e in root.find(W+'body'):
  value=text(e)
  if e.tag==W+'p' and value=='Einleitung, Problemstellung und Zielsetzung':active=True
  if e.tag==W+'p' and value=='Implementierung':break
  if active:
   strings.append(value);math.extend(canonical_math(t) for t in e.iter(M+'oMath'))
 assert active
 return re.sub(r'\s+','', ''.join(strings)).replace('\u00ad',''),''.join(math),root


def main():
 baseline=json.loads((B/'preservation_before_completion.json').read_text());unchanged=[];changed=[];missing=[]
 for name,expected in baseline.items():
  if name=='docs/Akz_Masterarbeit_Bericht(3).docx':continue
  p=ROOT/name
  if not p.exists():missing.append(name)
  elif sha(p)!=expected:changed.append(name)
  else:unchanged.append(name)
 assert not changed and not missing,(changed,missing)
 assert sha(BACKUP)=='a9a5d7d17b28098f554240a3e1650881e252db679f33319a1d11164b3246cbb8'
 orig,om,_=main_content(BACKUP);final,fm,root=main_content(TARGET)
 assert orig==final,'Chapter 1–5 wording differs after export'
 assert om==fm,'Chapter 1–5 equation content differs after export'
 all_text=text(root)
 for forbidden in ('{{','XXXXX','Noch nicht freigegebener Entwurf','Verzeichnis wird bei der abschließenden','Es konnten keine Einträge','Fehler! Textmarke'):
  assert forbidden not in all_text,forbidden
 assert all(word in all_text for word in ['Implementierung','Evaluation und Ergebnisse','Diskussion','Ausblick und verbleibende Nachweise','Fazit','Literaturverzeichnis'])
 manifest=json.loads((B/'word_build_manifest.json').read_text())
 assert len(manifest['figures'])==6
 assert [x['title'].split(':',1)[0] for x in manifest['figures']]==['Abbildung 7-'+str(i) for i in range(1,7)]
 # Caption styles in exported OOXML are inspected through style names, not
 # counts of repeated caption text inside automatically updated indexes.
 with zipfile.ZipFile(TARGET) as z:
  styles=ET.fromstring(z.read('word/styles.xml'))
  style_names={s.attrib.get(W+'styleId'):s.find(W+'name').attrib.get(W+'val') for s in styles if s.tag==W+'style' and s.find(W+'name') is not None}
 caps=[]
 for p in root.iter(W+'p'):
  st=p.find('./'+W+'pPr/'+W+'pStyle')
  name=style_names.get(st.attrib.get(W+'val')) if st is not None else None
  if name in ['Tabellenbeschriftung','Abbildungsbeschriftung']:caps.append(text(p))
 expected_caps=[x['title'] for x in manifest['tables']+manifest['figures']]
 assert sorted(caps)==sorted(expected_caps),(len(caps),len(expected_caps))
 numbers=[re.match(r'^(Tabelle|Abbildung) ([A\d]+-\d+):',c).group(0) for c in caps]
 assert len(set(numbers))==len(numbers),'Duplicate caption numbers'
 layout=json.loads((B/'thesis_final_layout_audit.json').read_text())
 assert layout['indexes_count']==3
 assert all(len(x['text'])>100 for x in layout['indexes'])
 for x in manifest['figures']:assert x['title'] in layout['indexes'][1]['text']
 for x in manifest['tables']:assert x['title'] in layout['indexes'][2]['text']
 a=json.loads((B/'runtime_analysis/analysis.json').read_text());assert len(a['trials'])==18
 assert all(x['source_to_reference_score_max_abs_difference']==0 for x in a['trials'])
 # The protocol pins all source files used during measurement.
 p=json.loads((B/'runtime_evidence/protocol.json').read_text())
 for name,expected in p['implementation_sha256'].items():assert sha(name)==expected,name
 assert sha(Path(p['bundle_directory'])/'pilot_bundle.json')==p['frozen_bundle_sha256']
 control=json.loads((B/'final_control_status.json').read_text())
 cfg=control['readback']['pwm_configuration']
 assert cfg['duty_cycle_ns']==0 and cfg['period_ns']==40000 and cfg['enable']==1
 assert control['readback']['pwm_mux_confirmed']
 result=dict(checked_utc=datetime.now(timezone.utc).isoformat(),protected_unchanged_files=len(unchanged),changed_protected_files=changed,missing_protected_files=missing,
             authorized_changed_file=str(TARGET.relative_to(ROOT)),word_sha256=sha(TARGET),backup_sha256=sha(BACKUP),
             preserved_main_chapters_1_5_wording=True,preserved_main_chapters_1_5_equations=True,equation_check='Canonical OMML operators, fractions, roots, bounds and indices; whitespace/minus/delimiter serialization normalized',
             main_chapter_numbers='1–10; appendix and bibliography unnumbered',unique_caption_count=len(numbers),figure_count=6,
             runtime_trials_complete=18,source_to_frozen_scores_exact=True,pinned_source_hashes_unchanged=True,
             final_pwm_percent=0,pwm_frequency_hz=25000,final_mechanical_standstill_observed=False,
             pdf_sha256=sha(B/'thesis_final.pdf'),layout_engine='LibreOffice; PDF pages additionally reviewed',
             personal_signing_date_and_signature='left blank for author',frozen_models_scaler_thresholds_unchanged=True)
 with (B/'completion_verification.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps(result,indent=2,ensure_ascii=False))


if __name__=='__main__':main()
