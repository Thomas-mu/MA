# Gemeinsamer RMS-, Isolation-Forest- und Float32-TFLite-Vergleich

Stand: 09.09.2026. Anforderungen: Masterarbeit `Akz_Masterarbeit_Bericht(3).docx`,
Kapitel 4 und 5, insbesondere identische Fenster, normale Trainingsdaten,
separate normale P99-Validierung und unveränderte Artefakte im Test.

`src/common_comparison.py` ergänzt eine gemeinsame Pipeline. Vorhandene
Aufnahmen, Profile, Modelle und Ergebnisdateien werden nicht verändert.
Jeder Aufruf benötigt einen neuen Ausgabeordner. Ein vorhandener Ordner wird
zurückgewiesen. Die Worddatei wurde als Anforderungsquelle verwendet.

## Implementiert und geprüft

1. Die Aufnahmezuordnung aus `profile.json` wird vor der Fensterbildung gelesen.
   Dateihashes und die dort gespeicherten Train-/Validierungslisten müssen
   zusammenpassen. Derselbe Dateipfad, identische Dateihashes und identische
   Messwert-/Zeitstempelfolgen dürfen nicht mehrfach auftreten. Das erkennt
   vollständige Kopien; umformatierte Ausschnitte sind damit nicht allgemein
   erkennbar. Tatsächliche Unabhängigkeit benötigt zusätzlich ein Aufnahmeprotokoll.
2. Alle drei Methoden bekommen dieselben Float32-Rohfenster in derselben
   Reihenfolge. Ein Fenster überschreitet niemals eine Aufnahmegrenze.
   Unvollständige Restfenster werden mit ihrer Samplezahl dokumentiert.
3. Der bestehende `StandardScaler` wird gegen einen erneuten Fit ausschließlich
   auf normalen Trainingsfenstern geprüft, einschließlich Mittelwert, Varianz,
   Skalierung und Zahl der Trainingswerte. Seine Parameter bleiben unverändert.
   Die NumPy-Anwendung reproduziert `StandardScaler.transform` aus scikit-learn
   1.9 auf Float32 exakt; die Implementierung prüft dies bei neuer Kalibrierung.
   RMS benötigt deshalb zur Ausführung keine sklearn-Bibliothek.
4. RMS ist gemäß Kapitel 5 `sqrt(mean(square(X_standardisiert)))` über alle
   `H × 3` Werte, dimensionslos. IF erhält genau dasselbe standardisierte Fenster
   flach in C-Reihenfolge. IF verwendet 200 Bäume, `max_samples='auto'`,
   `random_state=42`, einen Worker; Score ist `-score_samples`. Diese Einstellung
   wurde aus der bestehenden Vergleichsimplementierung übernommen, nicht an
   Testdaten gewählt.
5. RMS-/IF-Schwellen sind das 99. Perzentil (`method='linear'`) ausschließlich
   der normalen Validierungsfenster. Der AE übernimmt die bisherige Profil-P99
   unverändert. Die auf denselben Fenstern beobachtete TFLite-P99 muss innerhalb
   der im Profil dokumentierten Konvertierungstoleranz liegen. Die Schwelle wird
   dabei nicht angepasst. Ihre Herkunft lautet ausdrücklich
   `PROFILE/P99_FROZEN_KERAS_CALIBRATION`, denn die ursprüngliche Kalibrierung
   erfolgte mit Keras; die jetzt ausgewertete Inferenz ist Float32-TFLite.
6. Ein `bundle.json` bindet Modell, Scaler, Profilkopie und Datensplit über SHA-256.
   Neu erzeugte Bundles enthalten auch eine Quellcodekopie. `evaluate` kann weder
   trainieren noch Schwellen verändern. Ein Testmanifest muss den vorab
   eingefrorenen Bundle-Hash nennen. Das ist auch für einen zweiten normalen
   Betriebspunkt dasselbe Bundle.
7. Nichtendliche Messwerte, unzulässige Labels und nicht streng steigende
   Zeitstempel werden zurückgewiesen. Neue FIFO-CSV müssen alle drei Flags
   `gap`, `overrun`, `saturated` gemeinsam enthalten; zulässig sind
   `True/False/1/0` (Groß-/Kleinschreibung egal). Bereits ein gesetztes Flag oder
   nicht fortlaufende Sample-Indizes verwerfen konservativ die ganze Aufnahme,
   auch wenn das betroffene Sample in einem später verworfenen Restfenster liegt.
   Alte CSV ohne Flags erhalten den Status unbekannter Messqualität.
8. Ungültige Modellausgaben oder Scores ergeben `INVALID`, niemals `NORMAL`.
   Ergebnisse führen Zahl ungültiger Entscheidungen und Anteil gültiger
   Entscheidungen getrennt auf. Gütekennzahlen beziehen sich ausdrücklich auf
   gültige Entscheidungen; Klassenanteile und Kennzahlen werden insgesamt, je
   Aufnahme und je Zustand ausgegeben. Undefinierte Kennzahlen sind JSON `null`.
   F1 verwendet die Wordformel `2TP / (2TP + FP + FN)`; bei reinen Normaldaten
   mit Fehlalarmen ist sie rechnerisch 0, ohne dass damit Anomalieerkennung geprüft wäre.
9. Kein Vergleichsaufruf steuert den Lüfter. Ein Testmanifest muss ausdrücklich
   erklären, dass keine detektionsabhängige Abschaltung erfolgte. Für eine finale
   Aufnahme wird dies zusätzlich gegen das Erfassungsprotokoll geprüft.

## Tatsächlich vorliegende Pilotbefunde

Neue Ergebnisse liegen unter `results/common_comparison_20260909/`:

| Profil | Train-Aufnahmen/-Fenster | Validierungsaufnahmen/-Fenster | RMS-P99 | IF-P99 | unveränderte AE-P99 |
|---|---:|---:|---:|---:|---:|
| fan_25 | 6 / 1404 | 2 / 468 | 1,1746529475380507 | 0,46205377181774965 | 0,18673839128379896 |
| fan_50 | 7 / 1638 | 1 / 234 | 1,1082771254487802 | 0,4576683345789156 | 0,22105744905736202 |

Die gespeicherten Scaler wurden aus diesen Trainingsfenstern reproduziert.
Alle Methoden bewerten dieselben 468 beziehungsweise 234 Validierungsfenster.
Je Methode liegen bei fan_25 fünf und bei fan_50 drei Validierungsfenster oberhalb
der P99. Das sind 1,0684 % beziehungsweise 1,2821 %. Diese Werte sind eine
Kalibrierungsdiagnose, kein unabhängiger Nachweis der Falschpositivrate. Es sind
keine Anomalien enthalten; Recall/F1 und H1/H3 sind damit nicht nachgewiesen.

Die alten Profile tragen weiterhin `measurement_chain_status='unverified_legacy'`.
Die bisherige nominelle 500-Hz-Rate wurde aus Software-Zeitstempeln berechnet.
Die damalige Sensor-ODR und Zahl neuer Messwerte sind nicht nachgewiesen. Neue
200-Hz-FIFO-Daten sind deshalb kein austauschbarer Testdatensatz für diese
alten 500-Hz-Profile. `evaluate` lässt sie für solche Bundles nur mit dem
ausdrücklichen Zusatz `--pilot` zu und kennzeichnet die Ergebnisse explorativ.

Der ursprüngliche AE nutzte die normale Validierung auch für Trainingsüberwachung
und Early Stopping. Sie ist auf Aufnahmeebene vom Training getrennt, aber kein
dritter, zusätzlich vom Modellwahlprozess abgeschirmter Kalibrierungssplit.
Diese Einschränkung wird in den Bundles dokumentiert. Ein dritter Split wäre eine
vor neuen Versuchen zu treffende Protokollentscheidung; vorhandene Profile werden
dafür nicht rückwirkend verändert.

Die ursprünglichen Bundles wurden vor späteren Prüfungsverschärfungen erzeugt.
Der zu ihrem `implementation_sha256` passende Quelltext liegt als
`implementation_476185bb5573c8f7c5de17fdf6de5786f590652d78907143c6fe98b927a884bd.py`
im Ergebnisordner. Sie bleiben als historische Pilotergebnisse unverändert.
Die späteren Prüfungen ändern keine der oben angegebenen Schwellen.
Die ursprünglichen Pilotdiagnosen setzen F1 bei fehlender Anomalieklasse
zusätzlich auf `null`. Die aktuelle Implementierung nutzt stattdessen die
oben angegebene Wordformel mit `null` ausschließlich bei Nenner 0. Historische
Ergebnisdateien werden dafür nicht überschrieben.

## Ressourcenmessung und ihre Grenzen

`benchmark` startet jede Methode nacheinander in einem frischen Prozess. Gemessen
wird ab dem vollständigen unskalierten Fenster im RAM bis zur verfügbaren,
auf Endlichkeit geprüften Schwellenentscheidung. Enthalten sind Float32-Kopie,
Skalierung, Umformung, RMS beziehungsweise Inferenz, Score und Entscheidung.
Sensor/Fensterfüllzeit, Warteschlange, GUI, Dateilesen und Protokollausgabe liegen
außerhalb dieser Replay-Latenz. Bibliotheks-/Modellladen wird separat gemessen.

CPU ist die Benutzer- plus Systemzeit des gesamten Prozesses, einschließlich
Vorverarbeitung und Messinstrumentierung. 100 % bedeuten einen CPU-Kern; zusätzlich
wird auf alle logischen Kerne normiert. RAM ist der gesamte Prozess-RSS,
einschließlich Python und aller Methodenbibliotheken; Baseline, geladener Zustand
und alle 5 ms abgetastetes Maximum werden gespeichert. Das Maximum ist kein
allokationsgenauer Spitzenwert. Modellgröße und Prozessspeicher sind verschiedene
Größen. Der Interpretername unterscheidet standalone `ai_edge_litert.Interpreter`
und `tensorflow.lite.Interpreter`; keiner davon ist ein Keras-Benchmark.

Der zuletzt ausgeführte Ressourcenpilot `fan_25_resources_10s_bounded` lief auf dem Raspberry Pi 5
mit `.venv`, standalone LiteRT, einem TFLite-Thread, 20 Warmup-Fenstern und
mindestens zehn Sekunden je Methode. Jede Methode wiederholte nur vollständige
Durchläufe aller 468 identischen Validierungsfenster. Die relative Häufigkeit
jedes Fensters ist somit identisch; die Zahl der Durchläufe hängt von der
Methodengeschwindigkeit ab.

| Methode | gemessene Entscheidungen | Messdauer s | mittlere Verarbeitung ms | P99 ms | maximal abgetasteter RSS MiB | Prozess-CPU %, 1 Kern = 100 % |
|---|---:|---:|---:|---:|---:|---:|
| RMS | 269100 | 10,012 | 0,03235 | 0,03759 | 38,44 | 106,17 |
| Isolation Forest | 1404 | 18,508 | 13,16638 | 13,78814 | 167,22 | 101,31 |
| Float32-TFLite-AE | 157248 | 10,022 | 0,05953 | 0,08263 | 48,59 | 101,08 |

Dieser Versuch betreibt die Modelle bei vollem Durchsatz ohne Echtzeit-Pausen.
Die CPU-Werte sind daher keine Vorhersage der CPU-Last bei einem real eintreffenden
Fensterstrom. Bibliotheksthreads und der RSS-Abtastthread zählen zum Prozess;
Werte über 100 % sind auf einem Mehrkernsystem möglich. Der aktuelle Messlauf
schreibt alle Latenzen nach dem Entscheidungszeitstempel in ein Binärjournal
(Little-Endian-Float64) mit festem 64-KiB-Puffer. Die CPU-Messung enthält diesen
Aufwand, die einzelne Verarbeitungslatenz nicht. Erst nach Ende der CPU-/RSS-
Messung werden sämtliche Werte zur exakten empirischen P99-Berechnung geladen.
Der Speicher dieser nachträglichen Statistik wird separat angegeben. Der RSS
nach Modellladen betrug RMS 37,64 MiB, IF 166,39 MiB und TFLite 47,67 MiB.
Die zusätzliche Differenz zum gemessenen Maximum enthält unter anderem
Eingabeseiten, Schreibpuffer und RSS-Abtastung; sie ist kein isolierter Modellbedarf.

Alle drei Methoden dieses Laufs verwenden denselben Quelltext mit SHA-256
`aff8075a676f55484faae53a3170f312091062f21e1ead2b7cdd05d93266b6a7`.
Die Codekopie, Rohjournale, Einzellatenz-CSV und vollständigen JSON-Berichte
liegen gemeinsam im Ergebnisordner.

Der erste Pilot `fan_25_resources` mit jeweils nur 1000 Entscheidungen bleibt
ebenfalls erhalten. RMS und AE liefen dort weniger als 0,1 s; ihre CPU-Prozentwerte
sind wegen kurzer Beobachtung und CPU-Zeitauflösung nicht belastbar.
Der Zwischenlauf `fan_25_resources_10s` verwendete bereits zehn Sekunden
Mindestdauer, hielt jedoch alle Einzellatenzen in einer wachsenden Python-Liste.
Damit wuchs der zusätzliche Messspeicher methodenabhängig mit der Zahl der
Wiederholungen. Seine RSS-Spitzen sind für einen direkten Methodenvergleich
ungeeignet; er bleibt als dokumentierter Entwicklungslauf erhalten.

Feste Methodenreihenfolge, ein Durchgang und fehlende Kontrolle des thermischen
Zustands begrenzen alle Piloten. GUI-Einfluss, gleichzeitige Sensorerfassung,
Pufferverzug, vollständige Live-Latenz und H2 werden daraus nicht abgeleitet.
Der GUI-/Headless-Vergleich benötigt einen eigenen Versuch mit demselben
eingefrorenen Bundle und denselben Wiedergabedaten beziehungsweise reproduzierbar
protokollierten Zuständen. Keras-Messwerte aus älteren Ressourcenberichten dürfen
nicht als TFLite-Werte bezeichnet werden.

## Startbefehle

Vom Repository-Verzeichnis aus; alle `*_neu`-Ordner müssen noch nicht existieren:

```bash
.venv/bin/python -m unittest discover -s tests -p test_common_comparison.py -v

.venv/bin/python src/common_comparison.py calibrate \
  --profile fan_25 --runtime litert \
  --output results/gemeinsamer_vergleich_neu/fan_25

.venv/bin/python src/common_comparison.py benchmark \
  --bundle results/gemeinsamer_vergleich_neu/fan_25 --runtime litert \
  --windows 1000 --minimum-seconds 10 \
  --output results/gemeinsamer_vergleich_neu/fan_25_ressourcen

.venv/bin/python src/common_comparison.py evaluate \
  --bundle results/gemeinsamer_vergleich_neu/fan_25 --runtime litert \
  --test-manifest data/test_neu/test_manifest.json --pilot \
  --output results/gemeinsamer_vergleich_neu/test_pilot
```

`--runtime tensorflow` ist eine gesondert gekennzeichnete Alternative, falls nur
`.venv_tf` zur Verfügung steht. Sie lädt das vollständige TensorFlow-Paket und
ist daher auch beim Speichervergleich als andere Laufzeit zu behandeln.
Es gibt keinen manuellen Schwellenparameter in dieser Vergleichspipeline.
Eine in anderen Livewerkzeugen verwendete Schwelle 0,3 ersetzt nicht die
eingefrorene Profil-P99.

## Vorbereitung neuer unabhängiger Testaufnahmen

Zuerst müssen die Messkette, Montage, Zustände und Messparameter überprüft sowie
Train-/Validierungs-/Testzwecke vor der Erfassung festgelegt werden. Ein
nachweislich passend kalibriertes Modell/Scaler/P99-Bundle wird vor dem Test
eingefroren. Die neuen Aufnahmen bekommen ihre Labels aus dem hergestellten
Zustand, niemals aus der Modelldetektion. PWM-Vorgabe in Prozent und unabhängig
gemessene Drehzahl in rpm bleiben getrennt. Eine nicht gemessene Drehzahl ist
`null`; eine geschätzte Drehzahl aus PWM ist kein Messwert.

Das Manifest hat folgende Struktur. Pfade werden relativ zur Manifestdatei
aufgelöst. Die Platzhalter sind nach tatsächlicher Erfassung durch die
entsprechenden SHA-256-Werte und Zustandsangaben zu ersetzen:

```json
{
  "frozen_bundle_sha256": "SHA256_DER_VORHER_EINGEFRORENEN_bundle.json",
  "independent_recordings": true,
  "detection_dependent_fan_shutdown": false,
  "measurement_chain_verified": true,
  "sampling_rate_hz": 200,
  "sensor": {"odr_hz": 200, "range_g": 2, "acquisition_mode": "fifo_stream"},
  "protocol": {"path": "versuchsprotokoll.md", "sha256": "SHA256_DES_FESTGELEGTEN_PROTOKOLLS"},
  "recordings": [
    {
      "path": "normal_betriebspunkt_1_001.csv",
      "sha256": "SHA256_DER_CSV",
      "metadata_sha256": "SHA256_DER_GLEICHNAMIGEN_JSON",
      "label": 0,
      "state": "normal_betriebspunkt_1",
      "pwm_setpoint_percent": 25,
      "measured_rpm": null
    },
    {
      "path": "normal_betriebspunkt_2_001.csv",
      "sha256": "SHA256_DER_CSV",
      "metadata_sha256": "SHA256_DER_GLEICHNAMIGEN_JSON",
      "label": 0,
      "state": "normal_betriebspunkt_2",
      "pwm_setpoint_percent": 50,
      "measured_rpm": null
    }
  ]
}
```

Die Zahlen 200 Hz, ±2 g sowie PWM 25/50 % sind hier ein Formatbeispiel,
keine aus dieser Pipeline abgeleitete Eignungsentscheidung. Insbesondere muss
für 200 Hz ein dazu passendes neues Kalibrierungsbundle existieren. Die
aktuellen fan_25/fan_50-Bundles erfüllen diese Voraussetzung ausdrücklich nicht.

Ohne `--pilot` verlangt die Pipeline zusätzlich zum Manifest ein abgeschlossenes,
gehashtes JSON-Erfassungsprotokoll je Aufnahme: Zweck `test`, passende CSV-Prüfsumme,
Label und Zustand, dokumentierte Montage, FIFO-Modus, ausgelesene Sensorregister,
keine Qualitätsflags und keine detektionsabhängige Lüftersteuerung. ODR, Bereich,
Erfassungsmodus, Register und Montage müssen mit dem eingefrorenen Bundle
übereinstimmen. Dessen bestätigter Status setzt seinerseits entsprechende
Train-/Validierungsprotokolle voraus. Ein allein gesetztes
`measurement_chain_verified: true` genügt damit nicht.

Der zweite normale Betriebspunkt erhält ein anderes Zustandslabel im selben
Testmanifest, aber dasselbe Bundle. Das separat trainierte fan_50-Bundle bleibt
ein Entwicklungsvergleich und ersetzt diesen Versuch nicht. Anomaliezustände
benötigen weitere unabhängige Aufnahmen mit `label: 1` und eindeutigen Namen.
Zahl, Dauer und Wiederholungen sowie die zulässige Zustandsherstellung sind im
Versuchsprotokoll vorab festzulegen. Änderungen nach Einsicht in Testausgaben
erfordern einen neuen Entwicklungszyklus und neue unabhängige Testaufnahmen.

## Noch nicht nachgewiesen

- Abschließende Qualität einschließlich Anomalie-Recall/F1, Aufnahmevariabilität
  und Konfidenzintervallen; hier wurden nur normale Kalibrierungsdaten ausgewertet.
- Verhalten eines unveränderten Modells/Scalers/P99 bei einem zweiten normalen
  Betriebspunkt mit bestätigter gleicher Messkette.
- Eignung der neuen Messparameter für das relevante Spektrum, unabhängige
  Drehzahlmessung und bestätigte Zustände am Prüfstand.
- Vollständiger Methodenvergleich bei Live-Erfassung sowie zusätzlicher Einfluss
  der GUI unter denselben Bedingungen.

Die aktuellen 18 automatisierten Prüfungen decken Aufnahmegrenzen, Datenkopien,
Labels/Zeitstempel/Qualitätsflags, Scaler-Gleichheit, RMS-Definition, P99,
unveränderte Schwellen, identische Methodeneingaben, ungültige Entscheidungen,
undefinierte Kennzahlen, vollständige Latenzjournale und Schutz des finalen Tests ab. Sie ersetzen keinen
Messketten- oder Hardwareversuch.
