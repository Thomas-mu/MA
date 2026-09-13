# Unabhängige Prüfung des Offline-Referenzimports

Stand: 12.09.2026. Geprüft: `analyze_reference_edges.py`, `test_reference_edges.py`, `README.md` und `metadata_template.json`. Ausschließlich Dateiverarbeitung; keine Hardwarezugriffe und keine Änderungen dieser vier Dateien. Alle zusätzlichen Gegenbeispiele wurden in temporären Ordnern als ausdrücklich künstliche Prüfbeispiele ausgeführt und anschließend gelöscht.

## Ergebnis

Die 21 vorhandenen Unittests bestehen erneut. Die Trennung von Flankenfrequenz und unbekannter Drehzahl sowie die normale Behandlung fehlender/auffälliger Qualitätsflags sind konservativ. Vor Verwendung als Beleg für eine unabhängige Sensor-ODR sollten zwei konkrete Punkte behoben werden.

### F1 – Physischer ODR-Status entsteht aus einer Metadatenbehauptung

`analyze()` setzt `sample_correspondence` ausschließlich aus `kind=adxl_data_ready` und `one_edge_per_sample_confirmed=true`. Die Validierung verlangt hierfür nur einen beliebigen nichtleeren Text in `one_edge_per_sample_evidence`. Weder DATA_READY-Deassertion noch eine Zuordnung zu I²C-Bursts/Samples werden ausgewertet. Bei zusätzlich angegebenem externem Instrumenttakt, Zeitgenauigkeit, bestätigter Erfassungsvollständigkeit und `dataset_kind=MEASUREMENT` entstehen dennoch `independent_sensor_odr_reference_eligible=true` und ein numerisches `sensor_odr_estimate_hz`.

Reproduziertes künstliches Gegenbeispiel: drei Ereignisse `rising@0`, `falling@1`, `rising@1.01`, jeweils Flag `ok`. Die Leitung ist eine Sekunde gehalten; die Ereignisliste belegt keine einzige zusätzliche Sensorwandlung während dieser Zeit. Mit den oben genannten Metadaten meldet das Werkzeug trotzdem ODR `0.9900990099009901 Hz` und unabhängige Referenzeignung. Für diesen **negativen Softwaretest** wurde gezielt der MEASUREMENT-Codezweig angesprochen; Quelle und Instrument waren ausdrücklich als `SYNTHETIC NEGATIVE REVIEW FIXTURE` bezeichnet. Es wurde keine reale Messung erzeugt oder als solche archiviert.

Der README-Text weist korrekt darauf hin, dass die Metadaten externe Behauptungen/Nachweise darstellen und vom Programm nicht fachlich überprüft werden. Damit ist der aktuelle Code als **bedingte Umrechnung extern attestierter Angaben** erklärbar. Die maschinenlesbaren ODR-Felder sind jedoch stärker als der tatsächlich erfolgte Programmcheck. Insbesondere schützt `test_held_data_ready_is_not_odr` nur den Fall `one_edge_per_sample_confirmed=false` und prüft diese Übernahme behaupteter Evidenz nicht.

**Kleinste erforderliche Korrektur:** Der Import sollte eindeutig zwischen `declared/externally_attested` und `verified_by_this_tool` unterscheiden. Eine aus beigebrachten Metadaten abgeleitete Zahl kann als bedingte ODR-Schätzung erhalten bleiben; das Werkzeug darf ohne zusätzliche Zuordnungsprüfung keinen selbst geprüften unabhängigen Sensor-ODR-Nachweis ausgeben. Eine vorhandene fachliche Zuordnungsprüfung kann später separat mit ihren tatsächlichen Belegen verknüpft werden. Bloße weitere Pflichttexte lösen dieses Problem nicht. Der gehaltene-Leitung-Fall muss auch bei positiv behaupteter 1:1-Zuordnung im Test abgedeckt sein.

### F2 – Endliche Zeitwerte können erst nach Ausgabeanlage zurückgewiesen werden

`read_events()` prüft endliche, streng steigende Zeitwerte. Abgeleitete Intervalle, Mittelwerte und Kehrwerte werden aber nicht erneut auf Endlichkeit geprüft. Zwei tatsächlich reproduzierte künstliche Eingaben:

- Zeiten `0` und `1e-320`: endliches positives Intervall, aber unendlicher Frequenzkehrwert.
- Zeiten `−1e308` und `+1e308`: beide endlich und zunehmend, ihre Differenz wird unendlich.

In beiden Fällen erzeugt `run()` zunächst den Ausgabeordner. Erst `json.dumps(..., allow_nan=False)` scheitert mit `ValueError: Out of range float values are not JSON compliant: inf`. Es entsteht kein gültiges Ergebnis, jedoch ein bereits angelegter leerer Ordner. Das widerspricht der dokumentierten Zusicherung, ungültige Eingaben vor der Ausgabeanlage abzuweisen; ein erneuter Lauf auf denselben Ordner wird anschließend vom Überschreibschutz blockiert.

**Kleinste erforderliche Korrektur:** Auch alle berechneten Perioden und Raten müssen endlich sein; erforderliche positive Werte dürfen nicht null sein. Zusätzlich die vollständige Ergebnisserialisierung vor `mkdir()` durchführen. Regression: beide Fälle müssen einen nachvollziehbaren Eingabefehler liefern, ohne den Ausgabeordner anzulegen.

## Geprüfte korrekte Eigenschaften

- PPR wird nicht automatisch auf zwei gesetzt. Fehlende oder unbestätigte PPR verhindert die RPM-Umrechnung; eine Flankenfrequenz bleibt verfügbar. Eine bestätigte PPR benötigt einen positiven endlichen Wert und dokumentierte Herkunft.
- Ausschließlich eine gewählte Flankenrichtung bestimmt die Perioden; beide Richtungen führen nicht zur Verdopplung der Frequenz.
- Fehlende oder leere Qualitätsflags sind `unknown`. Nicht bekannte Flagwörter werden abgewiesen. Auffällige Ereignisse, auch entgegengesetzter Richtung innerhalb eines Intervalls, verhindern dessen Aufnahme in die qualifizierte Intervallmenge.
- Eine qualitätsauffällige Aufnahme erhält keine freigegebene RPM-Umrechnung. Gesamtfrequenzen bleiben ausdrücklich beschreibend; ungültige Ereignisse werden nicht still entfernt und die übrigen dann neu verbunden.
- Rückläufige Zeiten, gleiche Zeiten im selben Kanal und explizites NaN/Inf werden abgewiesen; gleichzeitige Ereignisse verschiedener Kanäle sind zulässig.
- Keine Flanken bedeuten keinen mechanischen Stillstand. Physische Sensorverluste bleiben unbekannt. SYNTHETIC-Testdaten bleiben als künstlich erkennbar und können den gegenwärtigen unabhängigen ODR-Status nicht erfüllen.
- Vorhandene Ergebnisordner werden nicht überschrieben; CSV, Metadaten und Auswerter sind gehasht.

## Reproduzierte Prüfung

Befehl: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s results/upright_v4_followup_closure_20260912/reference_tools -p 'test_reference_edges.py' -v`.

Ergebnis: **21 Tests bestanden**, 0,154 s im erneuten Prüfaufruf. Die beiden Gegenbeispiele oben wurden zusätzlich direkt mit `run()` ausgeführt. Dieser Bericht verlangt keinen Hardwareversuch und keine Änderung des eingefrorenen Modellpakets.

Geprüfte Dateihashes:

- `analyze_reference_edges.py`: `c608593f2a38966eb5386efada66f61d7aecc651d9f434fe9aa2b2a85a9582ae`
- `test_reference_edges.py`: `dae21d0266b3ec5cd48fba8fea754c65f2d4d03ab7a068afc270fc12465bc7ff`
- `README.md`: `a4bd805ff19e1286963cdbac8388ef091e29b29959e9558c0a492b1ae805c77d`
- `metadata_template.json`: `26a0ea8cfcec273497c11db33d917f0770da5c1580a76befdb89e8d61a493b7d`
