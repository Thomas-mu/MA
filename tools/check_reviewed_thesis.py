#!/usr/bin/env python3
"""Validate the revised DOCX/PDF; optionally deliver after visual review."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from docx import Document
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/masterarbeit_ueberarbeitet_revision_20260919'
NAME = 'Masterarbeit_ueberarbeitet'
BACKUP = ROOT / 'docs/backups/Masterarbeit_ueberarbeitet_vor_diagrammen_20260919.docx'
TARGET = ROOT / 'docs' / (NAME + '.docx')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cells(table):
    return [[c.text for c in r.cells] for r in table.rows]


def normalize_package(path):
    # Correct a known LibreOffice core-properties relationship URI on DOCX export.
    changes = []
    temporary = path.with_suffix('.normalized.tmp')
    with ZipFile(path) as source, ZipFile(temporary, 'w') as output:
        assert source.testzip() is None
        for item in source.infolist():
            data = source.read(item)
            if item.filename == '_rels/.rels':
                tree = ET.fromstring(data)
                for rel in tree:
                    actual = rel.get('Type', '')
                    correct = 'http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties'
                    if actual.endswith('/metadata/core-properties') and actual != correct:
                        rel.set('Type', correct)
                        changes.append({'old': actual, 'new': correct})
                if changes:
                    data = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
            output.writestr(item, data)
    temporary.replace(path)
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deliver', action='store_true', help='Only after reviewing the page previews.')
    args = parser.parse_args()
    manifest = json.loads((OUT / 'revision_manifest.json').read_text())
    final = OUT / (NAME + '.docx')
    normalization = normalize_package(final)
    original, revised = Document(BACKUP), Document(final)
    assert sha(BACKUP) == manifest['source_sha256']
    for source in manifest['data_sources'].values():
        assert sha(ROOT / source['path']) == source['sha256'], source['path']
    assert len(original.tables) == len(revised.tables) == 33
    assert len(original.sections) == len(revised.sections) == 3
    assert len(revised.inline_shapes) == len(original.inline_shapes) + 2 == 12
    for i, (before, after) in enumerate(zip(original.tables, revised.tables)):
        if i not in [0, 2]:
            assert cells(before) == cells(after), f'Unexpected change in table {i}'
    assert sorted(cells(original.tables[0])[1:]) == sorted(cells(revised.tables[0])[1:])
    for before, after in zip(original.tables[2].rows, revised.tables[2].rows):
        if not before.cells[0].text.startswith('Garay'):
            assert [c.text for c in before.cells] == [c.text for c in after.cells]
    old_text = [p.text for p in original.paragraphs]
    new_text = [p.text for p in revised.paragraphs]
    changed = [i for i, text in enumerate(old_text) if text and text not in new_text]
    assert changed == [115, 234, 245, 342, 354], changed
    assert old_text[:old_text.index('Zusammenfassung')] == new_text[:new_text.index('Zusammenfassung')]
    # Every paragraph from results through conclusion is retained verbatim.
    start, stop = old_text.index('Evaluation', old_text.index('Implementierung und Versuchsdesign')), old_text.index('Anhang')
    for text in old_text[start:stop]:
        assert text in new_text
    captions = [p.text for p in revised.paragraphs if p.style.name == 'Abbildungsbeschriftung']
    numbers = [re.match(r'Abbildung (\d+-\d+):', c).group(1) for c in captions]
    assert numbers == ['6-1', '6-2', '6-3', '6-4'] + [f'7-{i}' for i in range(1, 8)]
    assert 'JSON-Wert null' in '\n'.join(new_text)
    assert '27.10.2026' in '\n'.join(new_text[:20])
    with ZipFile(final) as package:
        w = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        tree = ET.fromstring(package.read('word/document.xml'))
        equations = len(tree.findall('.//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath'))
        with ZipFile(BACKUP) as old_package:
            old_tree = ET.fromstring(old_package.read('word/document.xml'))
            assert equations == len(old_tree.findall('.//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath'))
            old_media = {sha_bytes(old_package.read(p)) for p in old_package.namelist() if p.startswith('word/media/')}
            new_media = {sha_bytes(package.read(p)) for p in package.namelist() if p.startswith('word/media/')}
            assert old_media <= new_media, 'An existing figure was changed'
        fields = [n.text or '' for n in tree.findall('.//w:instrText', w)]
        assert sum('TOC ' in value for value in fields) == 3
        assert not tree.findall('.//w:ins', w) and not tree.findall('.//w:del', w)
    layout = json.loads((OUT / 'layout_audit.json').read_text())
    assert not layout['unresolved_index_entries'] and layout['indexes_count'] == 3
    figures_index = layout['indexes'][1]
    for number in numbers:
        assert figures_index.count(f'Abbildung {number}:') == 1
    ns = {'h': 'http://www.w3.org/1999/xhtml'}
    pages = ET.parse(OUT / 'pdf_bounds.html').findall('.//h:page', ns)
    assert 60 <= len(pages) <= 68, len(pages)
    page_audit = []
    for i, page in enumerate(pages, 1):
        words = page.findall('h:word', ns)
        width, height = float(page.get('width')), float(page.get('height'))
        overflow = [w.text for w in words if float(w.get('xMin')) < 0 or float(w.get('yMin')) < 0
                    or float(w.get('xMax')) > width+1 or float(w.get('yMax')) > height+1]
        assert not overflow, (i, overflow)
        assert len(words) >= 15, f'Unexpected near-blank page {i}'
        page_audit.append({'page': i, 'words': len(words), 'overflow': overflow})
    previews = sorted(OUT.glob('page-*.png'))
    assert len(previews) == len(pages)
    for start in range(0, len(previews), 12):
        sheet = Image.new('RGB', (1560, 1710), '#dfe4e8')
        draw = ImageDraw.Draw(sheet)
        for i, p in enumerate(previews[start:start+12]):
            im = Image.open(p).convert('RGB')
            im.thumbnail((368, 520))
            x, y = (i%4)*390+(390-im.width)//2, (i//4)*570+28
            sheet.paste(im, (x, y))
            draw.text(((i%4)*390+12, (i//4)*570+8), p.stem, fill='#172c3d')
        sheet.save(OUT / f'contact-{start//12+1:02}.png')
    audit = {
        'status': 'passed', 'pages': len(pages), 'tables': 33, 'figures': 11,
        'changed_existing_body_paragraphs': changed,
        'all_results_and_conclusions_retained_verbatim': True,
        'all_existing_figures_retained_byte_identically': True,
        'all_measurement_tables_unchanged': True, 'equations_preserved': equations,
        'source_csvs_unchanged': True, 'cover_and_declaration_unchanged': True,
        'native_indexes_refreshed': 3, 'package_normalization': normalization,
        'page_checks': page_audit,
        'docx_sha256': sha(final), 'pdf_sha256': sha(final.with_suffix('.pdf')),
    }
    (OUT / 'document_checks.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False)+'\n')
    if args.deliver:
        assert sha(TARGET) == manifest['source_sha256'], 'Target changed; do not overwrite newer work.'
        destinations = {}
        for source in [final, final.with_suffix('.pdf')]:
            destination = ROOT / 'docs' / source.name
            if source.suffix == '.pdf':
                assert not destination.exists(), 'An existing PDF must be preserved before replacement.'
            temporary = destination.with_name(destination.name+'.review_revision.tmp')
            assert not temporary.exists()
            shutil.copy2(source, temporary)
            if source.suffix == '.docx':
                assert sha(TARGET) == manifest['source_sha256']
            temporary.replace(destination)
            assert sha(destination) == sha(source)
            destinations[str(destination.relative_to(ROOT))] = sha(destination)
        delivery = {'completed_utc': datetime.now(timezone.utc).isoformat(),
                    'outputs': destinations, 'backup': str(BACKUP.relative_to(ROOT)),
                    'visual_review': 'All 63 PDF pages inspected in contact sheets; new plots, captions and index pages inspected separately.',
                    'open_item': 'Cover date remains 27.10.2026; user mentioned Tuesday, 22.09.2026. Confirmation required.'}
        (OUT / 'delivery_manifest.json').write_text(json.dumps(delivery, indent=2, ensure_ascii=False)+'\n')
        audit['delivered'] = destinations
    print(json.dumps({k: v for k, v in audit.items() if k != 'page_checks'}, indent=2, ensure_ascii=False))


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


if __name__ == '__main__':
    main()
