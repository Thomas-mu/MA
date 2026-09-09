# Fortsetzung vom 09.09.2026

Dieser Ordner enthält Dokumentations- und Softwareprüfungen, **keine neue
kontrollierte Sensormessung**. Die Bestätigung des Nutzers steht aus.

- `baseline.json`: DOCX-Ausgangshash, Backup-Pfad und 293 zu erhaltende Dateien.
- `read_only_hardware_state.json`: datierter Prozess-/Geräte-/PWM-Befund;
  gespeicherte PWM-Werte sind kein Nachweis eines Signals am Pin oder der RPM.
- `software_tests.xml`: 61 Tests und zwölf Untertests bestanden, ohne Hardwarezugriff.
- `docx_structure_check_final.json`: Kapitel 1–5 und Formeln erhalten;
  fünf neue Tabellen, keine unaufgelösten internen Links, eine Ausblick-Überschrift.
- `docx_page_reference_cache.json`: 76 anhand der Paginierung aktualisierte
  Seitenverweise; native Word-Felder bleiben aktualisierbar.
- `word_layout_final/report.pdf`: geprüfte Ausgabe mit 52 PDF-Seiten;
  Implementierung auf arabischen Seiten 29–37. `layout.json` enthält die
  Bookmark-Paginierung, `report.txt` die Textausgabe für die Kontrolle.
- `document_render_environment.txt`: verwendete Dokumentsoftware und
  Calibri-Ersatzschrift; der PDF-Renderer ist LibreOffice, nicht Microsoft Word.
- `preservation_and_status_final.json`: unveränderte 293 bestehende Dateien,
  endgültiger DOCX-Hash und der noch ausstehende nächste Messschritt.

Visuell geprüft wurden die Verzeichnisse, Kapitelanfang und die fünf neuen
Tabellen auf Aufteilung, lesbare Zellinhalte, Überschrifteneinzüge und Nummerierung.
Nach der letzten Layoutänderung waren sämtliche Bookmark-Seiten gegenüber
der zum Zwischenspeichern der Seitenzahlen verwendeten Fassung stabil.
Die DOCX wurde nicht durch eine vollständige LibreOffice-Rückkonvertierung
ersetzt; außer Dokumenttext/-struktur und Feldeinstellungen bleiben die
ursprünglichen ZIP-Bestandteile unverändert.

Die Kapitelquelle ist `docs/implementierung_20260909.md`. Hilfsprogramme in
`tools/` erzeugen aus der gesicherten Ausgangsdatei neue, nicht überschreibende
Arbeitskopien und prüfen sie. Zwischenfassungen dieser Bearbeitung liegen
nur unter `/tmp/edgeai_docx_intermediate_20260909/`; sie sind keine Messbelege.
Der dauerhafte Versuchsplan ist `docs/versuchsplan_kontrolliert_20260909.md`.
