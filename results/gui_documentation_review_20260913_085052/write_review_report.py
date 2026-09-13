"""Create the concise GUI documentation handoff after the Word checks."""
from pathlib import Path
import json

B=Path(__file__).resolve().parent
v=json.loads((B/'manuscript_verification.json').read_text())
assert v['authorized_word_updated']
text=f'''# GUI-Dokumentation: Abschluss und Belegstellen

Stand: 13.09.2026. Der lokale HEAD und der zu Beginn abgefragte GitHub-Standardbranch `Thomas-mu/MA:main` stehen weiterhin auf `62e93abc6a919f9b7f525fbb1522445b09779f2d`. Neuere Änderungen auf diesem Branch oder lokale Nutzeränderungen wurden nicht gefunden. Abfragen und Ausgangshash sind in [initial_state.json](initial_state.json) dokumentiert.

## Lieferung

- [Überarbeitete Hauptfassung DOCX](../../docs/Akz_Masterarbeit_Bericht(3).docx).
- [Gerenderte und geprüfte PDF](thesis_gui.pdf), {v['pdf_pages']} Seiten.
- [Gesicherte Ausgangsfassung](../../docs/backups/Akz_Masterarbeit_Bericht(3)_vor_gui_dokumentation_20260913_085052.docx).
- [Exakter Änderungsnachweis](word_changes.json) und [Erhaltungs-/Layoutprüfung](manuscript_verification.json).

## Eindeutiger GUI-Stand

**Umgesetzt:** profilgebundene Tkinter-/Matplotlib-Oberfläche mit Start, Stop und Exit, Status-/MSE-/Schwellenanzeige, Verlauf der letzten 100 Fenster, ERROR-/STALE-Kennzeichnung, entkoppelter Verarbeitung, begrenzten Queues und Protokollierung. Die Knöpfe steuern die Messung; eine Lüftersteuerung ist nicht eingebunden. Der Plot zeigt Rekonstruktionsfehler, keine XYZ-Rohkurve und keinen physischen RMS.

**Konkrete Abweichung vom finalen Paket:** Die GUI verwendet `live_tflite_monitor` mit Altprofilen und dessen Rohachsen → Float32 → Scaler-Verarbeitung. Die v4-Fensterzentrierung in Float64 fehlt. Bundle-Vertrag, an den Stellbefehl gebundener Fenster-/Abschnittsbezug und die gemeinsame Drei-Methoden-Auswertung sind nicht eingebunden. Alle vier vorhandenen Altprofile führen 500 Hz, während die aktuelle FIFO-Erfassung standardmäßig 200 Hz verwendet und diesen Konfigurationskonflikt zurückweist. Die GUI kann das finale Paket daher nicht allein durch einen anderen Profilnamen oder Dateiaustausch korrekt und unverändert verwenden. Eine neue Integration wurde nicht vorgenommen.

**Geprüft:** 16 historische GUI-CSV-Dateien vom 23.–26.08. mit 30.075 Entscheidungszeilen dokumentieren damalige Ausgaben. Drei aktuelle hardwarefreie GUI-Mocktests bestanden; geprüft sind Queue/Kontrollmeldungen, Journalanlage und STALE auf alten Fenstern. Ein rein synthetischer Funktionstest mit demselben gespeicherten Scaler bestätigt die unterschiedliche Vorverarbeitung. Er erzeugt keine Sensormessung und führt keine Modellinferenz aus.

**Für v4 nicht nachgewiesen:** sichtbarer GUI-Betrieb, Anzeige-/CSV-Parität, GUI-Anbindung an die finale Pipeline und vergleichbarer Latenz-/CPU-/RAM-Versuch mit und ohne GUI. Alle 18 abschließenden Sensor-/Replay-Laufzeitprozesse schließen die GUI aus. Ihre Werte sind keine GUI-Werte; historische siebenfeldrige GUI-Logs liefern den fehlenden Vergleich ebenfalls nicht. Matplotlib-Zeichenabschlüsse sind zudem keine physikalische Messung des Monitor-Anzeigezeitpunkts.

## Geänderte Stellen und Belege

Die Seitenangaben bezeichnen die gedruckte arabische Nummer, nicht den PDF-Blattindex.

| Stelle | Gezielte Änderung | Wichtigste Belege |
|---|---|---|
| 6.6, S. 31 | Gemessenen Weg ohne GUI von der vorhandenen Oberfläche getrennt; Verweis auf 6.8. | `runtime_evidence/protocol.json:189` unter B7: `GUI_included=false`; zugehöriger `runtime_analysis/runtime_report.md:9–17`. |
| Neue 6.8 / Tabelle 6-7, S. 32 | Funktionen, Profilweg, Vorverarbeitung, 500-/200-Hz-Konflikt und Integrationslücken dokumentiert. | `src/live_tflite_gui.py:263–348,394–457,583–720,739–801`; `src/live_tflite_monitor.py:206–286,393–408,479–509`; `src/pilot_method_comparison.py:39–52`; [Codeaudit](code_audit.md). |
| 7.7, S. 46 | Historische Logs und neue reine Softwaretests eingeordnet; fehlenden Vergleich mit/ohne GUI ausdrücklich benannt. | [Nachweisaudit](evidence_audit.md), [Log-Inventar](historical_gui_log_inventory.json), [Testprotokoll](gui_hardware_free_tests.log), [synthetischer Gegencheck](gui_contract_check.json). |
| 7.8 / A12, S. 48 | „GUI umgesetzt; Nachweis unvollständig“. Die ursprüngliche Anforderung und ihr bedingter Vergleich bleiben erhalten. | Unveränderte Abschnitte 4.2–4.4 und Tabelle 4-1; beide Audits. |
| 8.3, S. 50 | Umsetzung, Teilprüfung und noch fehlende A12-Nachweise voneinander getrennt. | Code-/Nachweisaudit; keine neue Erfolgsbehauptung. |
| 9, S. 53 | Konkrete zukünftige Anbindung, Paritätsprüfung und getrennte Replay-/Sensor-Vergleiche mit GUI beschrieben. | Fehlende Bundle-/Vorverarbeitungsschnittstelle; bestehender Messvertrag; keine Integration implementiert. |
| Anhang / B11, S. 55 | Separaten GUI-Prüfordner als digitalen Beleg zugeordnet. | Dieser Ordner mit Quellenhashes, Tests und Änderungsnachweis. |

Kapitel 1–5, Forschungsfragen, Hypothesen und das Fazit sind textgleich erhalten. Die Aussagen zu A1/A11, Drehzahl und negativen Erkennungsergebnissen wurden nicht pauschal überarbeitet. Die ursprünglichen Anforderungen wurden nicht abgeschwächt. Historische Protokolle und Versuchsergebnisse bleiben erhalten.

## Abschlussprüfung und verbleibende Nutzungsfrage

Die {v['tables']} Tabellen einschließlich Abkürzungsverzeichnis, sechs vorhandenen Abbildungen, drei Formeln und Literaturangaben sind erhalten beziehungsweise um Tabelle 6-7 ergänzt. Drei Verzeichnisse wurden aktualisiert, Beschriftungen und Seitenangaben geprüft. Alle gerenderten Seiten wurden visuell kontrolliert; die geänderten GUI-Seiten zusätzlich vergrößert. Abschnitt 7.8 beginnt für einen lesbaren Tabellenumbruch auf einer neuen Seite. Die kompakte Forschungsfragen-/Hypothesentabelle bleibt zusammen.

{v['protected_unchanged_files']} geschützte Bestandsdateien sind hashgleich, einschließlich Rohdaten, Modelle, Profile, Softwarequellen und historischer Berichte. Keine Hardwareaufnahme, PWM-Änderung, Trainings- oder echte Modellinferenz wurde ausgeführt. Es wurden nur die Haupt-Worddatei und neue separate Prüf-/Dokumentationsdateien bearbeitet; kein Commit oder Push vorgenommen.

Für die Repository- und Dokumentationsprüfung war keine Rückfrage nötig. Nur ein früherer, nicht gespeicherter Bedienvorgang bleibt durch eine Nutzerangabe ergänzbar: **Hast du die GUI tatsächlich am Bildschirm verwendet und ihre angezeigten Werte mit dem zugehörigen CSV-Protokoll abgeglichen; falls ja, wann, mit welchem Profil und gibt es dazu einen Beleg?** Eine nachträgliche Erinnerung wäre ausdrücklich als Nutzerangabe zu kennzeichnen und würde weder die fehlende v4-Integration noch die fehlende Vergleichsmessung ersetzen.
'''
(B/'gui_documentation_report.md').write_text(text)
print(str(B/'gui_documentation_report.md'))
