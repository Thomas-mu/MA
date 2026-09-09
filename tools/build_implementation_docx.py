"""Insert the reviewed chapter into a COPY of the thesis; preserve other ZIP parts.

Uses system Python/lxml. Rendering and field-cache refresh are separate steps.
"""
import argparse
from copy import deepcopy
from pathlib import Path
import re
from zipfile import ZipFile

from lxml import etree as E

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}


def el(tag, **attrs):
    return E.Element(f'{{{W}}}{tag}', {f'{{{W}}}{k}': str(v) for k, v in attrs.items()})


def text(node):
    return ''.join(node.xpath('.//w:t/text()', namespaces=NS))


def run(value, size=None, bold=False):
    r = el('r')
    if size or bold:
        pr = el('rPr')
        if bold:
            pr.append(el('b'))
        if size:
            pr.append(el('sz', val=size))
        r.append(pr)
    t = el('t')
    t.text = value
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    r.append(t)
    return r


def paragraph(value, style=None, size=None):
    p, pr = el('p'), el('pPr')
    if style:
        pr.append(el('pStyle', val=style))
    if style == 'berschrift2':
        num = el('numPr')
        num.extend([el('ilvl', val=1), el('numId', val=1)])
        pr.append(num)
        pr.append(el('ind', left=576, hanging=576))
    if not style:
        pr.append(el('spacing', after=120, line=300, lineRule='auto'))
        pr.append(el('widowControl'))
    if style == 'Beschriftung':
        pr.append(el('keepNext'))
    p.append(pr)
    p.append(run(value, size=size))
    return p


def table(rows, widths):
    t, pr = el('tbl'), el('tblPr')
    pr.append(el('tblW', w=sum(widths), type='dxa'))
    borders = el('tblBorders')
    for side in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        borders.append(el(side, val='single', sz=4, color='C5C5C5'))
    pr.append(borders)
    pr.append(el('tblLayout', type='fixed'))
    margins = el('tblCellMar')
    for side in ['top', 'left', 'bottom', 'right']:
        margins.append(el(side, w=80, type='dxa'))
    pr.append(margins)
    t.append(pr)
    grid = el('tblGrid')
    grid.extend(el('gridCol', w=w) for w in widths)
    t.append(grid)
    for i, row in enumerate(rows):
        assert len(row) == len(widths)
        tr, trpr = el('tr'), el('trPr')
        trpr.append(el('cantSplit'))
        if i == 0:
            trpr.append(el('tblHeader'))
        tr.append(trpr)
        for value, width in zip(row, widths):
            tc, tcpr = el('tc'), el('tcPr')
            tcpr.append(el('tcW', w=width, type='dxa'))
            if i == 0:
                tcpr.append(el('shd', fill='E7E6E6', val='clear'))
            tc.append(tcpr)
            p, pp = el('p'), el('pPr')
            if i < len(rows) - 1:
                pp.append(el('keepNext'))
            pp.append(el('spacing', before=20, after=20, line=252, lineRule='auto'))
            p.append(pp)
            p.append(run(value, size=21, bold=i == 0))
            tc.append(p)
            tr.append(tc)
        t.append(tr)
    return t


def pageref(p, name):
    r = el('r'); r.append(el('tab')); p.append(r)
    for kind in ['begin', 'instruction', 'separate', 'result', 'end']:
        r = el('r')
        if kind == 'instruction':
            child = el('instrText'); child.text = f' PAGEREF {name} \\h '
            child.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        elif kind == 'result':
            child = el('t'); child.text = '?'
        else:
            child = el('fldChar', fldCharType=kind)
        r.append(child); p.append(r)


def entry(title, name, level=0):
    p, pp = el('p'), el('pPr')
    pp.append(el('pStyle', val=f'Verzeichnis{min(level + 1, 3)}'))
    tabs = el('tabs'); tabs.append(el('tab', val='right', leader='dot', pos=9070)); pp.append(tabs)
    pp.append(el('spacing', after=70, line=240, lineRule='auto'))
    pp.append(el('ind', left=level*220))
    p.append(pp)
    link = el('hyperlink', anchor=name)
    link.append(run(title, size=22)); p.append(link)
    pageref(p, name)
    return p


def build(source, chapter, output):
    with ZipFile(source) as z:
        root = E.fromstring(z.read('word/document.xml'))
        body = root.find('w:body', NS)
        impl = next(p for p in body if p.tag == el('p').tag and text(p) == 'Implementierung')
        following = body[body.index(impl) + 1]
        assert text(following) == 'Evaluation und Ergebnisse', 'Source chapter is not empty'
        max_id = max(int(x) for x in root.xpath('.//w:bookmarkStart/@w:id', namespaces=NS))

        def bookmark(p, name):
            nonlocal max_id
            max_id += 1
            p.insert(1 if p.find('w:pPr', NS) is not None else 0,
                     el('bookmarkStart', id=max_id, name=name))
            p.append(el('bookmarkEnd', id=max_id))
            return name

        lines = chapter.read_text().splitlines()
        blocks, captions = [], []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line == '# Implementierung':
                i += 1; continue
            if line.startswith('|'):
                rows = []
                while i < len(lines) and lines[i].strip().startswith('|'):
                    row = [v.strip() for v in lines[i].strip().strip('|').split('|')]
                    if not all(re.fullmatch(r':?-+:?', v) for v in row):
                        rows.append(row)
                    i += 1
                widths = [2450, 3200, 3420] if rows[0][0] == 'Komponente' else [2150, 3350, 3570]
                blocks.append(table(rows, widths))
                continue
            if line.startswith('## '):
                p = paragraph(line[3:], 'berschrift2')
                bookmark(p, f'Implementation_{len(blocks)}')
            elif line.startswith('Tabelle 6-'):
                p = paragraph(line, 'Beschriftung', size=22)
                name = 'Table_' + line.split(':')[0].split()[1].replace('-', '_')
                bookmark(p, name); captions.append((line, name))
            else:
                p = paragraph(line)
                if blocks and blocks[-1].tag == el('tbl').tag:
                    p.find('w:pPr/w:spacing', NS).set(f'{{{W}}}before', '120')
            blocks.append(p); i += 1
        insert_at = body.index(impl) + 1
        for block in blocks:
            body.insert(insert_at, block); insert_at += 1

        # Remove only the adjacent empty duplicate chapter in the original.
        duplicates = [p for p in body if p.tag == el('p').tag and text(p) == 'Ausblick']
        assert len(duplicates) == 2 and body.index(duplicates[1]) == body.index(duplicates[0]) + 1
        body.remove(duplicates[1])

        toc = next(s for s in body.findall('w:sdt', NS)
                   if s.xpath('.//w:docPartGallery[@w:val="Table of Contents"]', namespaces=NS))
        content = toc.find('w:sdtContent', NS)
        toc_heading = deepcopy(content[0])
        content.clear(); content.append(toc_heading)
        # Keep a real TOC field with a complete cache and live PAGEREF fields.
        headers = []
        chapter_number = 0; counters = [0, 0, 0]
        for p in body.xpath('.//w:p', namespaces=NS):
            if toc in p.iterancestors() and p is not toc_heading:
                continue
            style = p.xpath('./w:pPr/w:pStyle/@w:val', namespaces=NS)
            if not style or style[0] not in ('berschrift1', 'berschrift2', 'berschrift3'):
                continue
            title = text(p); level = int(style[0][-1]) - 1
            no_num = p.xpath('./w:pPr/w:numPr/w:numId[@w:val="0"]', namespaces=NS)
            if level == 0 and not no_num:
                chapter_number += 1; counters = [chapter_number, 0, 0]
            elif level:
                counters[level] += 1
                if level == 1: counters[2] = 0
            prefix = '' if no_num else '.'.join(map(str, counters[:level+1])) + ' '
            names = p.xpath('./w:bookmarkStart/@w:name', namespaces=NS)
            name = next((n for n in names if n.startswith(('_MA_TOC_', 'Implementation_'))), None)
            if not name:
                # Some original bookmarks sit outside the bibliography SDT.
                name = next(iter(names), None) or bookmark(p, f'ChapterRef_{max_id+1}')
            headers.append((prefix + title, name, level))
        for i, (title, name, level) in enumerate(headers):
            p = entry(title, name, level)
            if i == 0:
                for node in reversed([el('fldChar', fldCharType='begin'), el('instrText'), el('fldChar', fldCharType='separate')]):
                    if node.tag == el('instrText').tag: node.text = ' TOC \\o "1-3" \\h \\z \\u '
                    r = el('r'); r.append(node); p.insert(1, r)
            if i == len(headers)-1:
                r = el('r'); r.append(el('fldChar', fldCharType='end')); p.append(r)
            content.append(p)

        # Append matching table-list entries, preserving the existing list.
        last = next(p for p in body if p.xpath('./w:hyperlink[@w:anchor="Table_5_13"]', namespaces=NS))
        index = body.index(last) + 1
        for title, name in captions:
            body.insert(index, entry(title, name)); index += 1
        # Use one font/spacing for the entire table list, including old entries.
        for p in list(body):
            links = p.xpath('./w:hyperlink[starts-with(@w:anchor,"Table_")]', namespaces=NS)
            if links:
                replacement = entry(text(links[0]), links[0].get(f'{{{W}}}anchor'))
                body.replace(p, replacement)

        settings = E.fromstring(z.read('word/settings.xml'))
        update = settings.find('w:updateFields', NS)
        if update is None: update = el('updateFields'); settings.append(update)
        update.set(f'{{{W}}}val', 'true')
        replacements = {'word/document.xml': E.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True),
                        'word/settings.xml': E.tostring(settings, xml_declaration=True, encoding='UTF-8', standalone=True)}
        with ZipFile(output, 'x') as out:
            for info in z.infolist():
                out.writestr(info, replacements.get(info.filename, z.read(info.filename)))
    print(f'{output}: {len(blocks)} chapter blocks, {len(captions)} new tables, {len(headers)} TOC entries')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--chapter', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); build(a.source, a.chapter, a.output)
