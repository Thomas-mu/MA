"""Cache PAGEREF results using the rendered bookmark pages, without a DOCX roundtrip.

The thesis has three numbering sections: front matter (Roman), main text
(Arabic, starting at 1), bibliography/appendix (Roman, starting at 1).
Native Word fields remain refreshable when Word lays out the document.
"""
import argparse
import json
from pathlib import Path
import re
from zipfile import ZipFile

from lxml import etree as E

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W = '{' + NS['w'] + '}'


def roman(value):
    result = ''
    for number, symbol in [(1000, 'm'), (900, 'cm'), (500, 'd'), (400, 'cd'),
                           (100, 'c'), (90, 'xc'), (50, 'l'), (40, 'xl'),
                           (10, 'x'), (9, 'ix'), (5, 'v'), (4, 'iv'), (1, 'i')]:
        count, value = divmod(value, number); result += symbol * count
    return result


def cache(source, layout, output):
    pages = json.loads(layout.read_text())['bookmark_physical_pages']
    with ZipFile(source) as z:
        root = E.fromstring(z.read('word/document.xml'))

        def heading_page(title):
            p = next(p for p in root.xpath('.//w:p', namespaces=NS)
                     if ''.join(p.xpath('.//w:t/text()', namespaces=NS)) == title
                     and p.xpath('./w:pPr/w:pStyle[@w:val="berschrift1"]', namespaces=NS))
            names = p.xpath('./w:bookmarkStart/@w:name', namespaces=NS)
            return next(pages[n] for n in names if n in pages)

        front = heading_page('Erklärung')
        main = heading_page('Einleitung, Problemstellung und Zielsetzung')
        bibliography = heading_page('Literaturverzeichnis')
        assert front < main < bibliography
        cache_values = {name: roman(page - bibliography + 1) if page >= bibliography
                        else str(page - main + 1) if page >= main
                        else roman(page - front + 1) for name, page in pages.items()}
        # Cross-check the numeric section calculation against live non-TOC refs.
        fields = json.loads(layout.read_text())['fields']
        for field in fields:
            if field['source'].startswith('Table_'):
                assert cache_values[field['source']] == field['presentation'], field
        stack = []; changed = 0
        for node in root.iter():
            if node.tag == W+'fldChar':
                kind = node.get(W+'fldCharType')
                if kind == 'begin': stack.append({'instruction': '', 'result': False, 'done': False})
                elif kind == 'separate' and stack: stack[-1]['result'] = True
                elif kind == 'end' and stack: stack.pop()
            elif node.tag == W+'instrText' and stack:
                stack[-1]['instruction'] += node.text or ''
            elif node.tag == W+'t' and stack and stack[-1]['result']:
                match = re.match(r'\s*PAGEREF\s+(\S+)', stack[-1]['instruction'])
                if match:
                    name = match[1]
                    assert name in cache_values, f'Unresolved page reference: {name}'
                    node.text = '' if stack[-1]['done'] else cache_values[name]
                    if not stack[-1]['done']: changed += 1
                    stack[-1]['done'] = True
        assert not stack, 'Unbalanced fields'
        with ZipFile(output, 'x') as out:
            for info in z.infolist():
                out.writestr(info, E.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
                             if info.filename == 'word/document.xml' else z.read(info.filename))
    output.with_suffix('.pages.json').write_text(json.dumps({'updated_page_fields': changed,
        'section_starts_physical': {'front': front, 'main': main, 'bibliography': bibliography},
        'cached_pages': cache_values}, indent=2))
    print(f'{output}: updated {changed} page fields')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--layout', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); cache(a.source, a.layout, a.output)
