# Externe Referenzflanken: vorbereiteter Offline-Import

Dieses Werkzeug liest ausschließlich Dateien. Es greift weder auf GPIO/I²C zu noch schaltet es den Lüfter. Es enthält **keine neue Hardwaremessung** und schließt den fehlenden Drehzahl- oder unabhängigen Sensortaktnachweis noch nicht ab. Vorhandene Daten, Modelle und Programmdateien unter `src/` bleiben unverändert.

## Eingabe und Ausführung

Die CSV enthält die Spalten `reference_time_s,channel,edge` und optional `quality_flag`. Zeitangaben sind Sekunden im dokumentierten Bezugssystem des erfassenden Instruments, nicht nachträglich aus der nominellen 200-Hz-Vorgabe errechnete Zeitstempel. Die Daten müssen global zeitlich sortiert sein; gleichzeitige Ereignisse verschiedener Kanäle sind erlaubt. Pro Kanal müssen die Zeiten strikt steigen. `edge` ist entweder `rising` oder `falling`.

Für `quality_flag` sind `ok`, `invalid`, `gap` und `unknown` erlaubt. Eine fehlende Spalte oder ein leeres Flag wird als unbekannte Qualität dokumentiert, nicht als fehlerfreie Erfassung. Andere Flagwerte, NaN/Inf, rückläufige Zeiten, doppelte Kanalzeitstempel und unbekannte Kanäle werden zurückgewiesen. Native Instrumentflags müssen vor dem Import nachvollziehbar auf diese Werte abgebildet werden; das ursprüngliche Exportformat bleibt erhalten.

`metadata_template.json` ist eine **unvollständige Vorlage**, keine Messdokumentation. Eine neue Kopie muss vor der Nutzung mit den tatsächlichen Angaben ausgefüllt werden. Die unveränderte Vorlage wird wegen fehlender Quellen- und Instrumentangaben zurückgewiesen. Nicht vorhandene Kanäle können entfernt werden. Ein vorhandener Kanal ohne Flanken bleibt ausdrücklich als solcher dokumentiert.

```bash
python3 results/upright_v4_followup_closure_20260912/reference_tools/analyze_reference_edges.py \
  --csv /pfad/zum/neuen_instrumentexport.csv \
  --metadata /pfad/zur/ausgefuellten_metadatenkopie.json \
  --output /pfad/zu/einem/noch_nicht_existierenden_ergebnisordner
```

Das Programm schreibt `analysis.json` (Ausgabeschema 2; Metadaten-Eingabeschema weiterhin 1) nur in einen neuen Ordner. Bestehende Ausgaben werden nicht überschrieben. Eingaben und **alle abgeleiteten Zahlen** werden vor dem Erstellen einer Ausgabe geprüft; auch die vollständige JSON-Serialisierung erfolgt vorher. Endliche Zeitstempel können bei extremen Größen dennoch unendliche Differenzen, Frequenzen oder Statistiken ergeben. Diese Fälle werden zurückgewiesen, ohne einen Ausgabeordner anzulegen. Ausgabe und Metadaten enthalten SHA-256-Hashes der Quelldateien sowie des Auswerters. Die Originalexporte werden nicht verändert.

## Dokumentation der Zeitbasis und des Anschlusses

| Metadatum | Bedeutung |
|---|---|
| `dataset_kind` | `MEASUREMENT` für tatsächlich erfasste Daten; `SYNTHETIC` ausschließlich für künstliche Softwaretests. |
| `source`, `instrument` | Exportquelle, Gerät/Modell und Zuordnung zum Versuchsprotokoll; keine erfundene Gerätebezeichnung. |
| `clock_relation`, `clock_relation_basis` | `external_independent`, `shared_host` oder `unknown` sowie der dokumentierte Grund dieser Einordnung. Ein weiteres Programm auf demselben Host ist nicht automatisch eine unabhängige Zeitreferenz. |
| `time_accuracy_s`, `time_accuracy_basis` | Bekannte Zeitgenauigkeit mit Herkunft/Anwendungsbereich der Angabe; `null`, wenn unbekannt. Auflösung allein ist keine Genauigkeitsangabe. |
| `capture_integrity_confirmed`, `capture_integrity_evidence` | Externe Angabe, ob die Vollständigkeit der Instrumenterfassung durch geeignete Instrumentstatusdaten oder Vergleichsprüfungen belegt sei. Der Import prüft diesen Anspruch nicht unabhängig. Eine lückenlos nummerierte Exportdatei allein belegt die Vollständigkeit nicht. |
| `selected_edge` | Genau eine Flankenrichtung je Kanal für die Periodenauswertung. |
| `pulses_per_revolution`, `ppr_confirmed`, `ppr_evidence` | Extern angegebene Tachoimpulse pro Umdrehung und Begründung der beanspruchten Bestätigung. Keine automatische Annahme von zwei Impulsen und keine physische Verifikation durch den Import. |
| `one_edge_per_sample_confirmed`, `one_edge_per_sample_evidence` | Externe Behauptung einer 1:1-Zuordnung zwischen der gewählten DATA_READY-Flanke und neuem Sensorsample. Dazu müssten Signalverhalten, Löschung/Quittierung und mögliche zusammenfallende Ereignisse tatsächlich geprüft sein. Der Import erhält jedoch keine überprüfbare Burst-/Pulszuordnung und bestätigt diese Behauptung daher nicht. |

Die Einträge `*_confirmed` dokumentieren **extern beigebrachte Angaben und deren beanspruchte Nachweise**. Boolean-Werte und Freitext allein sind kein maschinell überprüfter physischer Nachweis. Das Auswerteprogramm kann die Verkabelung, Gerätekalibrierung oder Vollständigkeit dieser Angaben nicht selbst prüfen. Es prüft lediglich, ob eine erforderliche Begründung vorhanden ist; deren fachliche Richtigkeit bleibt Gegenstand einer separaten Messprüfung. Auch `dataset_kind: MEASUREMENT` wird nur als Deklaration übernommen (`physical_measurement_declared_in_metadata`), nicht als verifizierte Herkunft.

## Berechnung und Grenzen

- Nur aufeinanderfolgende Flanken **derselben gewählten Richtung** bilden Perioden. Die beobachtete Frequenz ist `(N−1)/(t_letzte−t_erste)`; bei weniger als zwei solchen Flanken bleibt sie unbekannt. Beide Flanken zusammen werden niemals als doppelte Dreh- oder Abtastrate ausgewertet.
- Berichtet werden Anzahl, Mittelwert, Median, Minimum, Maximum und Stichprobenstandardabweichung der Intervalle. Ein zweiter Intervallsatz berücksichtigt nur Abschnitte, deren beide Grenzen und dazwischenliegende Ereignisse ausdrücklich `ok` sind. Über auffällige Ereignisse wird keine künstliche Periode hinweg verbunden.
- Die Gesamtfrequenz bleibt bei Qualitätsproblemen als **deskriptive Flankenfrequenz** erhalten. Eine bedingte RPM-Umrechnung wird dann nicht ausgegeben. Bei unbekannter PPR gibt es ebenfalls keine RPM-Angabe. Null Flanken bedeuten niemals automatisch mechanischen Stillstand.
- Eine RPM-Schätzung benötigt eine externe PPR-Bestätigung, fehlerfrei gekennzeichnete Ereignisse und die externe Bestätigung der Erfassungsvollständigkeit. Ein numerischer `rpm_estimate` bleibt stets **bedingt durch diese externen Angaben**; `rpm_estimate_status` lautet ausdrücklich `conditional_on_external_ppr_and_capture_claims`. `independent_rpm_reference_eligible` und `software_verified_physical_reference` bleiben in diesem Werkzeug grundsätzlich `false`, auch wenn alle Metadatenfelder ausgefüllt sind. Aus einer einzelnen Genauigkeitszahl berechnet das Werkzeug bewusst kein vermeintlich vollständiges Unsicherheitsintervall.
- DATA_READY kann gehalten werden oder mehrere Ereignisse zusammenfassen. Ohne separat überprüfbare 1:1-Zuordnung ist dessen Flankenrate **keine nachgewiesene Sensor-ODR**. Dieser Import verarbeitet keine separate Burst-/Pulszuordnung. Deshalb bleiben `sensor_odr_estimate_hz` unbekannt und `independent_sensor_odr_reference_eligible` grundsätzlich `false`. Bei vollständig dokumentierten externen Zuordnungs-, Erfassungs- und unabhängigen Zeitbasisangaben kann lediglich `conditional_sensor_odr_estimate_hz` erscheinen, mit dem Status **`conditional_on_external_mapping_claim`**. Diese bedingte Umrechnung ist kein unabhängiger ODR-Nachweis. Ein `SYNTHETIC`-Datensatz kann ebenfalls keinen physischen Referenznachweis liefern.
- `physical_sample_losses` bleibt unbekannt und `physical_loss_count_eligible` bleibt falsch. Weder eine Abweichung zwischen 200 Hz und ungefähr 207 XYZ/s noch ein Frequenzunterschied zwischen zwei Quellen begründet allein eine physische Verlustzahl. Ein solcher Nachweis benötigt eine gesonderte Synchronisations- und Ereigniszuordnung.

`eligibility` trennt daher rein numerische Verfügbarkeit und dokumentierte **Metadatenansprüche** von physischer Verifikation. Die Felder für unabhängige physische Referenznachweise bleiben ausnahmslos `false`; keine Boolean-/Freitextkombination kann sie aktivieren. Schwache oder unbekannte Voraussetzungen werden nicht durch Annahmen ersetzt. Für einen späteren unabhängigen Nachweis wäre eine gesonderte Prüfung überprüfbarer Instrument- und Puls-/Burstzuordnungsdaten erforderlich.

## Softwaretests

```bash
python3 -m unittest discover \
  -s results/upright_v4_followup_closure_20260912/reference_tools \
  -p 'test_reference_edges.py' -v
```

Alle Testdaten werden in temporären Ordnern mit dem Kennzeichen **SYNTHETIC** erzeugt. Sie sind keine Messungen und keine ergänzende Normalreferenz. Zwei ausdrücklich künstliche Grenzfalltests enthalten absichtlich die unbewiesene Metadatenbehauptung `MEASUREMENT`, um zu prüfen, dass auch diese Deklaration zusammen mit Freitextbestätigungen keinen physischen Nachweis erzeugt.

**26 Tests bestehen.** Getestet werden 200 und 207 Hz, ein **rein synthetisches** Tacho-Beispiel mit zwei Impulsen pro Umdrehung, Auswahl beider Flankenrichtungen ohne Doppelzählung, unbekannte PPR, gleiche Zeit verschiedener Kanäle, fehlerhafte Zeiten/Flags, Ausgabeüberschreibschutz und gehaltenes DATA_READY ohne unzulässige ODR-Gleichsetzung. Hinzu kommen überlaufende Differenzen, Frequenzen, Mediane und RPM-Berechnungen aus endlichen Eingabewerten sowie saubere CLI-Ablehnung ohne halbe Ausgabe. Das gespeicherte Testprotokoll ist `software_tests.log`.
