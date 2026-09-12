#!/usr/bin/env python3
"""Update indexes and layout with installed LibreOffice, then export PDF.
Start a dedicated local UNO listener first; no macros are executed.
"""
from pathlib import Path
import argparse,json,time
import uno
from com.sun.star.beans import PropertyValue


def props(**values):
 out=[]
 for name,value in values.items():
  p=PropertyValue();p.Name=name;p.Value=value;out.append(p)
 return tuple(out)


def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--port',type=int,default=2012);a=p.parse_args()
 local=uno.getComponentContext();resolver=local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',local)
 context=resolver.resolve(f'uno:socket,host=127.0.0.1,port={a.port};urp;StarOffice.ComponentContext')
 desktop=context.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',context)
 doc=desktop.loadComponentFromURL(uno.systemPathToFileUrl(str(a.input.resolve())),'_blank',0,props(Hidden=True,ReadOnly=False,MacroExecutionMode=uno.getConstantByName('com.sun.star.document.MacroExecMode.NEVER_EXECUTE'),UpdateDocMode=uno.getConstantByName('com.sun.star.document.UpdateDocMode.FULL_UPDATE')))
 if doc is None:raise RuntimeError('Document could not be loaded')
 audit={'input':str(a.input),'output':str(a.output)}
 try:
  # Imported Word TOC fields are real Writer indexes. Repeat after layout,
  # because additional captions/TOC pages can shift later page references.
  doc.refresh()
  indices=doc.getDocumentIndexes();audit['indexes_count']=indices.getCount();audit['indexes']=[]
  assert indices.getCount()==3,indices.getCount()
  for _ in range(3):
   for i in range(indices.getCount()):indices.getByIndex(i).update()
   doc.refresh()
  for i in range(indices.getCount()):
   x=indices.getByIndex(i)
   audit['indexes'].append({'name':x.getName(),'service':list(x.getSupportedServiceNames()),'text':x.getAnchor().getString()})
  doc.getTextFields().refresh()
  audit['tables']=doc.getTextTables().getCount()
  enumeration=doc.getText().createEnumeration();headings=[];paragraphs=[]
  while enumeration.hasMoreElements():
   e=enumeration.nextElement()
   if not e.supportsService('com.sun.star.text.Paragraph'):continue
   text=e.getString();paragraphs.append(text)
   if e.ParaStyleName in ('Heading 1','Heading 2','Heading 3'):
    try:label=e.ListLabelString
    except Exception:label=None
    headings.append({'text':text,'style':e.ParaStyleName,'list_label':label})
  audit['headings']=headings
  (a.output.parent/(a.output.stem+'_text.txt')).write_text('\n'.join(paragraphs))
  a.output.parent.mkdir(parents=True,exist_ok=True)
  doc.storeAsURL(uno.systemPathToFileUrl(str(a.output.resolve())),props(FilterName='Office Open XML Text',Overwrite=True))
  pdf=a.output.with_suffix('.pdf')
  doc.storeToURL(uno.systemPathToFileUrl(str(pdf.resolve())),props(FilterName='writer_pdf_Export',Overwrite=True,FilterData=props(UseTaggedPDF=True,ExportBookmarks=True)))
  audit['pdf']=str(pdf)
 finally:doc.close(True)
 (a.output.parent/(a.output.stem+'_layout_audit.json')).write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps({k:v for k,v in audit.items() if k not in ['headings','indexes']},indent=2))


if __name__=='__main__':main()
