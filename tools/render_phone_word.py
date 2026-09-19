#!/usr/bin/python3
"""Own an isolated Writer process for one native DOCX/PDF render."""
from pathlib import Path
import subprocess
import tempfile
import time
import uno

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/phone_vibration_word_revision_20260919'


def main():
    port=2107
    with tempfile.TemporaryDirectory(prefix='phone-word-render-') as profile:
        server=subprocess.Popen(['libreoffice','-env:UserInstallation='+Path(profile).as_uri(),'--headless','--nologo','--nodefault','--norestore',f'--accept=socket,host=127.0.0.1,port={port};urp;StarOffice.ServiceManager'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            local=uno.getComponentContext()
            resolver=local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',local)
            for _ in range(60):
                try:
                    resolver.resolve(f'uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext')
                    break
                except Exception:time.sleep(.25)
            else:raise RuntimeError('Isolated Writer did not become ready')
            subprocess.run(['/usr/bin/python3',str(ROOT/'results/upright_v4_finalization_20260912_103145/refresh_word.py'),'--input',str(OUT/'Akz_Masterarbeit_Bericht(3)_staged.docx'),'--output',str(OUT/'Akz_Masterarbeit_Bericht(3).docx'),'--port',str(port)],check=True,timeout=120)
        finally:
            server.terminate()
            try:server.wait(timeout=8)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=8)


if __name__=='__main__':main()
