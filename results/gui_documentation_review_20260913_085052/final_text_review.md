# Abschlussreview der GUI-Texte

Geprüft: `thesis_gui_unformatted.docx`, Stand der Dateifassung beim Review am 13.09.2026. Gegenbelege: `code_audit.md`, `evidence_audit.md`, `gui_contract_check.json`, tatsächlicher GUI-/Monitor-/Pipelinecode und die drei vorhandenen GUI-Regressionen. Keine weiteren Tests oder Hardwarezugriffe ausgeführt.

## Ergebnis

Die neuen Aussagen sind sachlich mit den geprüften Quellen vereinbar. Sie trennen die implementierte Oberfläche, die fehlende finale v4-Einbindung und die begrenzten gespeicherten Prüfungen korrekt. Keine Anpassung von Anforderungen oder Erkennungskennzahlen ist erkennbar.

| Stelle | Bewertung |
|---|---|
| Abschnitt 6.8, erster Absatz | Vorhandene Funktionen und tatsächliche Entkopplung korrekt; Start/Stop betreffen die Erfassung, keine Lüftersteuerung. MSE-Verlauf korrekt als Scoreverlauf bezeichnet. |
| Abschnitt 6.8, Datenweg | Fortlaufende 128er-XYZ-Fenster des GUI-Wegs korrekt von der PWM-bezogenen Auswahl `[180,300)` des finalen Tests getrennt. Fehlende Float64-Achsenmittelwertentfernung korrekt und synthetisch belegt. |
| Abschnitt 6.8, Profile | Aktuelle FIFO-Erfassung und 200-Hz-Voreinstellung korrekt von den 500-Hz-Altprofilmetadaten getrennt. Abweichendes Bundleschema und fehlende direkte v4-Ladeintegration korrekt. |
| Tabelle 6-7 | Implementierung wird anerkannt; Codeinstrumentierung wird nicht als gespeicherte Laufmessung ausgegeben. Simulationsmodus und reine Regressionen werden nicht als grafische Prüfung dargestellt. |
| Evaluation, zwei neue Absätze | 16 historische CSVs mit 30.075 Entscheidungszeilen korrekt; Provenienz-/Bildschirmgrenzen angemessen. Die drei aktuellen Mock-Regressionen sind weder Sensorversuch noch Sichtprüfung. Keine Umdeutung der 18 Prozesse ohne GUI zu GUI-Ressourcennachweisen. |
| A12 | „GUI umgesetzt; Nachweis unvollständig“ ist zutreffend. Die ursprünglich bedingte Nachweispflicht wird nicht durch die Einstufung KANN aufgehoben. |
| Diskussion und Ausblick | Fehlende Integration, Anzeige-/Ergebnisabgleich und Vergleich mit/ohne GUI werden konkret benannt; keine reine Textänderung wird als Softwareintegration behauptet. |

## Empfohlene kleine Präzisierung

Die Tabelle bezeichnet bisher „GUI-Zeichenzeitpunkte“. Zur ausdrücklich gewünschten Trennung vom physikalischen Bildschirmzeitpunkt sollte die Protokollierungszeile präziser lauten:

- Umgesetzt: „Rohdaten, Entscheidungen und Ressourcen über den Monitor; zusätzliche Matplotlib-Zeichenabschlüsse und Anzeigemeldungsverluste.“
- Grenze: „Kein Nachweis des physikalischen Anzeigezeitpunkts oder einer vergleichbaren Messreihe.“

Grundlage: `record_gui_draw` in `src/live_tflite_gui.py:699–712` registriert einen Matplotlib-Draw-Callback mit Hostzeitstempel. Dies misst nicht den Zeitpunkt, an dem die Änderung physikalisch auf dem Monitor sichtbar wird. Die geprüfte Fassung behauptet zwar keinen solchen Nachweis, nennt diese Grenze jedoch noch nicht ausdrücklich. Weitere sachliche Textkorrekturen sind aus diesem Review nicht erforderlich.

## Erhaltene Kernaussagen

Die vier mit `FF1:` bis `FF4:` beginnenden Forschungsfragen sowie alle sechs Textabsätze unter dem Hauptkapitel „Fazit“ sind gegenüber `input_blocks.json` wortgleich erhalten. Der ursprüngliche A12-Anforderungstext und die ursprüngliche Verpflichtung zum Vergleich mit und ohne Anzeige stehen weiterhin im Anforderungskapitel. Die umfassende Dokument-/Artefakterhaltungs- und Layoutprüfung erfolgt getrennt durch den Hauptlauf.
