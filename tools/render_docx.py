"""Render a DOCX with a dedicated local LibreOffice UNO session (no sensor access)."""
import argparse
import json
from pathlib import Path
import time
import uno
from com.sun.star.beans import PropertyValue


def prop(name, value):
    p = PropertyValue(); p.Name = name; p.Value = value
    return p


def render(source, output):
    if not source.is_file():
        raise FileNotFoundError(source)
    output.mkdir(parents=True, exist_ok=False)
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)
    for attempt in range(40):
        try:
            context = resolver.resolve('uno:pipe,name=edgeai_docx_20260909;urp;StarOffice.ComponentContext')
            break
        except Exception:
            if attempt == 39: raise
            time.sleep(.25)
    desktop = context.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', context)
    doc = desktop.loadComponentFromURL(source.resolve().as_uri(), '_blank', 0,
                                     (prop('Hidden', True), prop('ReadOnly', True), prop('UpdateDocMode', 1)))
    try:
        doc.getTextFields().refresh()
        # Exporting lays out every page before field presentations are read.
        doc.storeToURL((output/'report.pdf').resolve().as_uri(), (prop('FilterName', 'writer_pdf_Export'),))
        fields = []; enumeration = doc.getTextFields().createEnumeration()
        while enumeration.hasMoreElements():
            field = enumeration.nextElement()
            if hasattr(field, 'SourceName'):
                fields.append({'source': field.SourceName, 'presentation': field.getPresentation(False)})
        pages = {}
        view = doc.getCurrentController().getViewCursor()
        bookmarks = doc.getBookmarks()
        for name in bookmarks.getElementNames():
            view.gotoRange(bookmarks.getByName(name).getAnchor(), False)
            pages[name] = view.getPage()
        (output/'layout.json').write_text(json.dumps({'fields': fields, 'bookmark_physical_pages': pages,
                                                    'renderer': 'LibreOffice '+str(doc.getPropertyValue('BuildId')) if doc.getPropertySetInfo().hasPropertyByName('BuildId') else 'LibreOffice'}, indent=2))
        print(json.dumps({'output': str(output), 'reference_fields': len(fields), 'bookmarks': len(pages)}))
    finally:
        doc.close(True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); render(a.source, a.output)
