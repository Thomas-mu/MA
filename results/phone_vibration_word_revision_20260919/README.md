# Word-Revision: Handyvibration, 19.09.2026

Zieldatei: `docs/Akz_Masterarbeit_Bericht(3).docx`.
Die dazugehörige PDF dient der Layoutkontrolle und Weitergabe.
Die unveränderte Ausgangsfassung liegt unter
`docs/backups/Akz_Masterarbeit_Bericht(3)_vor_handyversuch_20260919.docx`.

## Inhalt der Änderung

- Zusammenfassung, Zielsetzung, Abgrenzung und Übergänge aktualisiert.
- Kapitel 6–10 auf die Handyreihe umgestellt: Aufbau, Annahmen, Normalprofil,
  Verarbeitung, Einzelbetrieb, Replay, gemeinsamer Live-Lauf, Ressourcen,
  Diskussion, Ausblick und Fazit.
- Neun neue Abbildungen aus den archivierten Daten beziehungsweise als
  ausdrücklich gekennzeichnete schematische Darstellungen erstellt.
- Ursprüngliche Hypothesen und Anforderungen nicht zugunsten des Ergebnisses
  verändert; Nachweisstand inklusive A1–A13 ausgewiesen.
- Hardwareauswahl und theoretische Grundlage erhalten. Frühere Erkennungs-
  und Raspberry-Pi-Ressourcentabellen zahlenmäßig unverändert im Anhang erhalten.
- Keine Bezeichnung des eigenen Versuchs als „Laborversuch“ oder „im Labor“.
- Deckblatt, persönliche Erklärung, Gleichungen und Literaturverzeichnis erhalten.
- Inhalts-, Abbildungs- und Tabellenverzeichnis mit Writer neu berechnet.

Der Autoencoder-Vorteil wird auf das tatsächlich gemessene Kriterium bezogen:
früheste Alarmausgabe im gemeinsamen Lauf, 19,061 ms vor IF und 615,659 ms vor RMS.
AE und IF markieren dasselbe erste Fenster 108; RMS markiert Fenster 109.
Die Handyreihe belegt weder einen höheren F1 noch eine allgemeine Überlegenheit.
Elektrische Leistung/Energie wurde nicht gemessen. Bedienmarker ersetzen keine
unabhängige physische Zeitreferenz. Diese Einschränkungen stehen im Bericht.

## Belege und Prüfungen

- `manuscript_update.md`: Textgrundlage für Kapitel 6–10 und Anhang.
- `figure_manifest.json`: neun Abbildungen mit Quelldateien und SHA-256.
- `derived_metrics.json`: aus den Original-CSV berechnete Prozesskennwerte.
- `evidence_audit.json`: erneute Offline-Auswertung, 1.205 originale
  Live-Entscheidungen exakt reproduziert; keine Hardware angesteuert.
- `revision_manifest.json`: Ausgangshash, gezielte Änderungen vor Kapitel 6,
  Hash der Textgrundlage und bibliografischer Erhaltungsnachweis.
- `document_checks.json`: Paket-, Nummerierungs-, Verzeichnis- und PDF-Grenzprüfung.
- `Akz_Masterarbeit_Bericht(3)_layout_audit.json`: tatsächlich aktualisierte
  Verzeichnisse und Überschriftennummern aus Writer.
- `previews/`: gerenderte PDF-Seiten und Kontaktbögen zur visuellen Kontrolle.
- `delivery_manifest.json`: Erhaltungsprüfung, ausgelieferte Dateihashes und
  Abschlussstatus; wird erst bei der tatsächlichen Übergabe geschrieben.

Originaldaten: `results/phone_vibration_pilot_20260919/`.
Die dort vorhandenen Rohdaten, Modelle, Schwellen, Protokolle, Präsentationen
und bisherigen Ergebnisse wurden durch diese Revision nicht geändert.
Die vorbereitete `protocol.md` bleibt als Planungsstand erhalten; für Ergebnisse
werden abgeschlossene Laufjournale und Auswertungen verwendet.

## Reproduktion

Die Skripte im Projektstamm benötigen die vorhandene Projektumgebung mit
NumPy/Matplotlib/LiteRT; der Word-Build zusätzlich python-docx 1.2.0 und lxml
6.1.3. Diese beiden Pakete wurden für die Revision nur in eine isolierte
temporäre Abhängigkeitenablage installiert, nicht in die Messumgebung.
Die Layoutausgabe verwendet die installierte Writer-/UNO-Umgebung.

```sh
.venv/bin/python tools/plot_phone_manuscript.py
.venv/bin/python tools/audit_phone_manuscript.py
# Mit python-docx/lxml im Python-Suchpfad:
.venv/bin/python tools/revise_phone_manuscript.py
/usr/bin/python3 tools/render_phone_word.py
pdftoppm -scale-to 520 -png 'results/phone_vibration_word_revision_20260919/Akz_Masterarbeit_Bericht(3).pdf' results/phone_vibration_word_revision_20260919/previews/page
pdftotext -bbox 'results/phone_vibration_word_revision_20260919/Akz_Masterarbeit_Bericht(3).pdf' results/phone_vibration_word_revision_20260919/pdf_bounds.html
.venv/bin/python tools/check_phone_word_layout.py
```

Der Build erzeugt eine Arbeitsfassung im Ergebnisverzeichnis, nicht unmittelbar
die Zieldatei. Vor deren Austausch prüft die Übergabe, ob die Ausgangsfassung
seit Beginn unverändert geblieben ist. Die visuelle Prüfung ist zusätzlich zu
den automatischen Prüfungen erforderlich. Der kleine Paketnormalisierungsschritt
korrigiert ausschließlich die von Writer exportierte Core-Properties-Relation;
Dokumentinhalt und PDF-Layout bleiben dabei unverändert.

Die Überarbeitung einschließlich Textformulierung wurde durch Codex unterstützt;
die entsprechende Offenlegung im Word-Anhang bleibt erhalten. Die fachliche
Verantwortung und die persönliche Prüfung vor Abgabe bleiben beim Autor.
