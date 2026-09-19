#!/usr/bin/python3
"""Refresh the staged thesis in an isolated LibreOffice process and export PDF.

Native index fields are retained. Caption indexes use their short titles;
cached page labels are checked against the final Writer layout.
"""
from pathlib import Path
import json
import re
import subprocess
import tempfile
import time

import uno
from com.sun.star.beans import PropertyValue

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/masterarbeit_ueberarbeitet_revision_20260919'
STAGED = OUT / 'Masterarbeit_ueberarbeitet_staged.docx'
FINAL = OUT / 'Masterarbeit_ueberarbeitet.docx'


def props(**kwargs):
    result = []
    for name, value in kwargs.items():
        prop = PropertyValue()
        prop.Name, prop.Value = name, value
        result.append(prop)
    return tuple(result)


def paragraphs(text_range):
    result = []
    elements = text_range.createEnumeration()
    while elements.hasMoreElements():
        item = elements.nextElement()
        if item.supportsService('com.sun.star.text.Paragraph'):
            result.append(item)
    return result


def replace_span(paragraph, start, count, replacement):
    cursor = paragraph.getText().createTextCursorByRange(paragraph.getStart())
    cursor.goRight(start, False)
    cursor.goRight(count, True)
    cursor.setString(replacement)


def roman(value):
    result = ''
    for n, s in [(100, 'c'), (90, 'xc'), (50, 'l'), (40, 'xl'),
                 (10, 'x'), (9, 'ix'), (5, 'v'), (4, 'iv'), (1, 'i')]:
        k, value = divmod(value, n)
        result += s*k
    return result


def finalize(doc):
    indexes = doc.getDocumentIndexes()
    assert indexes.getCount() == 3
    doc.refresh()
    for _ in range(2):
        for i in range(3):
            indexes.getByIndex(i).update()
        doc.refresh()
    # Preserve concise caption lists instead of copying multi-sentence explanations.
    shortened = 0
    for index_number in [1, 2]:
        index = indexes.getByIndex(index_number)
        index.IsProtected = False
        for paragraph in paragraphs(index.getAnchor()):
            text = paragraph.getString()
            if not text.startswith(('Abbildung ', 'Tabelle ')) or '\t' not in text:
                continue
            title = text.rsplit('\t', 1)[0]
            short = re.split(r'\.\s', title, maxsplit=1)[0]
            if title != short:
                replace_span(paragraph, 0, len(title), short)
                shortened += 1
    doc.refresh()
    doc.getTextFields().refresh()
    view = doc.getCurrentController().getViewCursor()
    body = paragraphs(doc.getText())
    front = next(p for p in body if p.getString() == 'Erklärung' and p.ParaStyleName == 'Heading 1')
    main = next(p for p in body if p.getString() == 'Einleitung, Problemstellung und Zielsetzung'
                and p.ParaStyleName == 'Heading 1')
    view.gotoRange(front.getStart(), False)
    front_page = view.getPage()
    view.gotoRange(main.getStart(), False)
    main_page = view.getPage()
    assert front_page < main_page
    entries, headings, figure_pages = {}, [], {}
    for p in body:
        text, style = p.getString(), p.ParaStyleName
        if style not in ('Heading 1', 'Heading 2', 'Heading 3', 'Abbildungsbeschriftung',
                         'Tabellenbeschriftung') and text not in (
                             'Abbildungsverzeichnis', 'Tabellenverzeichnis', 'Abkürzungsverzeichnis'):
            continue
        view.gotoRange(p.getStart(), False)
        physical = view.getPage()
        printed = str(physical - main_page + 1) if physical >= main_page else roman(physical-front_page+1)
        label = p.ListLabelString
        key = (label + ' ' + text).strip() if label else text
        entries[key] = printed
        if text.startswith(('Abbildung ', 'Tabelle ')):
            entries[re.split(r'\.\s', text, maxsplit=1)[0]] = printed
        if style.startswith('Heading'):
            headings.append({'text': text, 'style': style, 'label': label, 'page': printed})
        if text.startswith('Abbildung '):
            figure_pages[text.split(':', 1)[0]] = {'printed': printed, 'writer_physical': physical}
    assert [h['label'] for h in headings if h['style']=='Heading 1' and h['label']] == [str(i) for i in range(1, 11)]
    corrected, unresolved, index_texts = [], [], []
    for i in range(3):
        index = indexes.getByIndex(i)
        index.IsProtected = False
        for p in paragraphs(index.getAnchor()):
            text = p.getString()
            if '\t' not in text:
                continue
            title, old_page = text.rsplit('\t', 1)
            expected = entries.get(title)
            if expected is None:
                unresolved.append(title)
            elif old_page != expected:
                replace_span(p, len(text)-len(old_page), len(old_page), expected)
                corrected.append({'title': title, 'old': old_page, 'new': expected})
        index_texts.append(index.getAnchor().getString())
        index.IsProtected = True
    assert not unresolved, unresolved
    assert len(figure_pages) == 11
    doc.storeAsURL(FINAL.as_uri(), props(FilterName='Office Open XML Text', Overwrite=True))
    doc.storeToURL(FINAL.with_suffix('.pdf').as_uri(), props(
        FilterName='writer_pdf_Export', Overwrite=True,
        FilterData=props(UseTaggedPDF=True, ExportBookmarks=True)))
    audit = {'indexes': index_texts, 'indexes_count': 3, 'shortened_captions': shortened,
             'corrected_cached_pages': corrected, 'unresolved_index_entries': unresolved,
             'headings': headings, 'figure_pages': figure_pages,
             'tables': doc.getTextTables().getCount(),
             'main_start_writer_physical': main_page, 'front_start_writer_physical': front_page}
    (OUT / 'layout_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: v for k, v in audit.items() if k not in ('headings', 'indexes')}, indent=2))


def main():
    with tempfile.TemporaryDirectory(prefix='reviewed-thesis-writer-') as profile:
        port = 2119
        server = subprocess.Popen([
            'libreoffice', '-env:UserInstallation='+Path(profile).as_uri(),
            '--headless', '--nologo', '--nodefault', '--norestore',
            f'--accept=socket,host=127.0.0.1,port={port};urp;StarOffice.ServiceManager',
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        doc = None
        try:
            local = uno.getComponentContext()
            resolver = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)
            for _ in range(80):
                try:
                    context = resolver.resolve(f'uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext')
                    break
                except Exception:
                    time.sleep(.25)
            else:
                raise RuntimeError('Isolated Writer unavailable')
            desktop = context.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', context)
            doc = desktop.loadComponentFromURL(STAGED.as_uri(), '_blank', 0, props(
                Hidden=True, ReadOnly=False, UpdateDocMode=0,
                MacroExecutionMode=uno.getConstantByName('com.sun.star.document.MacroExecMode.NEVER_EXECUTE')))
            assert doc is not None
            finalize(doc)
        finally:
            if doc is not None:
                doc.close(True)
            server.terminate()
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=8)


if __name__ == '__main__':
    main()
