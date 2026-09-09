"""Check preservation and document structure after inserting implementation text."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E

N = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
     'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
     'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def txt(p):
    return ''.join(p.xpath('.//w:t/text()', namespaces=N))


def audit(source, target, output):
    with ZipFile(source) as a, ZipFile(target) as b:
        assert b.testzip() is None
        ra = E.fromstring(a.read('word/document.xml'))
        rb = E.fromstring(b.read('word/document.xml'))

        def chapters(r):
            body = r.find('w:body', N)
            start = next(i for i, p in enumerate(body) if txt(p) == 'Einleitung, Problemstellung und Zielsetzung')
            end = next(i for i, p in enumerate(body) if txt(p) == 'Implementierung')
            return [E.tostring(p, method='c14n') for p in list(body)[start:end]]

        ca, cb = chapters(ra), chapters(rb)
        assert ca == cb, 'Chapter 1–5 changed'
        changed = [n for n in a.namelist() if a.read(n) != b.read(n)]
        assert set(changed) == {'word/document.xml', 'word/settings.xml'}
        assert [E.tostring(e) for e in ra.xpath('.//m:oMath', namespaces=N)] == [
            E.tostring(e) for e in rb.xpath('.//m:oMath', namespaces=N)]
        tables = rb.xpath('.//w:tbl', namespaces=N)
        assert len(tables) == 22
        captions = [txt(p) for p in rb.xpath('./w:body/w:p[w:pPr/w:pStyle[@w:val="Beschriftung"]]', namespaces=N)
                    if txt(p).startswith('Tabelle 6-')]
        assert len(captions) == 5
        for i, caption in enumerate(captions, 1):
            assert caption.startswith(f'Tabelle 6-{i}:')
        headings = [txt(p) for p in rb.xpath('./w:body/w:p[w:pPr/w:pStyle[@w:val="berschrift1"]]', namespaces=N)]
        assert headings.count('Ausblick') == 1
        anchors = rb.xpath('.//w:hyperlink[not(@r:id)]/@w:anchor', namespaces=N)
        names = rb.xpath('.//w:bookmarkStart/@w:name', namespaces=N)
        unresolved = sorted(set(anchors) - set(names))
        assert not unresolved, unresolved
        for t in tables[-5:]:
            assert t.xpath('./w:tr[1]/w:trPr/w:tblHeader', namespaces=N)
            for row in t.findall('w:tr', N):
                assert row.find('w:trPr/w:cantSplit', N) is not None
                assert len(row.findall('w:tc', N)) == 3
            assert sum(int(x) for x in t.xpath('./w:tblGrid/w:gridCol/@w:w', namespaces=N)) <= 9072
        # No unresolved page placeholders in the rebuilt contents/list.
        assert not rb.xpath('.//w:t[text()="?"]', namespaces=N)
        report = {'chapter_1_to_5_xml_unchanged': True, 'preserved_chapter_blocks': len(ca),
                  'math_objects_unchanged': len(ra.xpath('.//m:oMath', namespaces=N)),
                  'only_changed_zip_parts': changed, 'tables_total': len(tables),
                  'new_table_captions': captions, 'unresolved_internal_hyperlinks': unresolved,
                  'single_outlook_heading': True, 'new_tables_repeat_header_and_preserve_rows': True,
                  'new_tables_within_text_width': True,
                  'docx_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
        with output.open('x') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--target', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); audit(a.source, a.target, a.output)
