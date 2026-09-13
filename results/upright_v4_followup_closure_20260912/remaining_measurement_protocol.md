# Gezielter Abschlussplan für die verbleibenden physischen Nachweise

Status: **vorbereitet, nicht durchgeführt**. Keine der nachfolgend beschriebenen Messungen wurde in diesem Auftrag gestartet. Die Vorgabe wurde nur lesend mit 0 % bei 25 kHz kontrolliert. Sensorbefestigung und Aufbau v4 bleiben erhalten. Persönliche Freigaben, angeschlossene Instrumente und mechanischer Stillstand werden nicht aus dieser Planung abgeleitet.

## Was bereits abschließbar ist

Die fachliche Kennzahlenbewertung des eingefrorenen Pakets ist ein zulässiges negatives Ergebnis. A9 verlangt eine gemeinsame Auswertung, keinen Mindest-F1 und keine gesicherte Schadensdiagnose. Die vorhandene unabhängige Normal–Platte–Normal-Folge liefert diese begrenzte Auswertung. Offen ist insbesondere die Wiederholung der veränderten Bedingung nach A11. Es wird kein Defekt erzeugt, um nachträglich einen strengeren Auftrag zu erfüllen.

Der Import externer Flankendateien wird unter `reference_tools/` sensorfrei vorbereitet und mit ausdrücklich synthetischen Daten geprüft. Er ersetzt weder ein angeschlossenes Messgerät noch den tatsächlichen Referenzversuch. Die technischen Einzelheiten und die Herstellerquellen stehen in [timebase_rpm_audit.md](timebase_rpm_audit.md).

## R1 – Eine kurze unabhängige Sensorzeitprüfung

**Frage:** Entspricht der beobachtete FIFO-Durchsatz von ungefähr 207 XYZ/s auch der Datenbereitstellung gegen einen unabhängigen Zeitbezug?

- Geplant sind 60 s Sensorerfassung bei 0 % PWM; ein Lüfterstart ist nicht nötig.
- ODR 200 Hz, ±2 g, Full Resolution und FIFO-Stream bleiben wie bisher eingestellt.
- Geplant ist ein externer Mitschnitt von SCL, SDA und zugänglichem DATA_READY-Ausgang gegen eine dokumentierte Instrumentzeitbasis. Instrumentmodell, Zeitgenauigkeit, Exportformat und tatsächliche Signalbelegung sind noch unbekannt.
- Vor einer Änderung der Interruptausgabe wird eine eigene Diagnosefassung erstellt, die INT_ENABLE und INT_MAP sichert und nachher wiederherstellt. Keine Änderung an den eingefrorenen Erfassungsmodulen; die Probe ist kein normaler Modelltest.
- DATA_READY kann über mehrere Bereitstellungen aktiv bleiben. Ein gezählter Puls ist deshalb nicht ungeprüft ein Sensorwert. Flanken müssen mit den dekodierten Datenbursts und der zurückkehrenden Inaktivität zugeordnet werden. Mehrdeutige Abschnitte bleiben erhalten und machen den betreffenden Nachweis unvollständig.
- Auswertungsgrößen: externe Flankenperioden, eindeutig zugeordnete Bereitstellungen, Bus-Burstzahl, Host-/Instrumentzeitmaßstab, FIFO-Randzustände, Instrumentverluste und Unsicherheit. Keine genaue physische Verlustzahl allein aus einer Differenz zwischen Flanken und CSV-Zeilen ableiten.

**Deine spätere Handlung:** Ein verfügbares Gerät mit Typbezeichnung nennen. Erst nach Prüfung der tatsächlichen Anschlüsse werden konkrete Messleitungen benannt; dafür die Versorgung trennen. Sensorplatine und Lüfter müssen nicht neu befestigt werden. Nach der Instrumentierung reicht eine Freigabe; die 60-s-Probe läuft ohne weitere Chatantwort und ohne Lüfterstart.

## R2 – Drehzahlreferenz, möglichst mit einem ohnehin nötigen Normallauf verbinden

**Frage:** Welche tatsächliche Drehzahl liegt im gemessenen Normalzustand bei 75 % PWM vor?

Bevorzugt wird entweder ein geeignetes berührungsloses Drehzahlmessgerät oder das bestätigte separate Tachosignal verwendet. GPIO18 bleibt der PWM-Ausgang (physischer Pi-Pin 12). Ein vorhandener Linux-hwmon-Wert des Pi-Kühlers ist keine Prüflüfter-Drehzahl.

Vor Anschluss einer Tacholeitung an den Pi müssen Signalpegel und Pull-up-Beschaltung geprüft sein. Die Zahl der Impulse pro Umdrehung muss erst für die Umrechnung in RPM bekannt sein; eine sichere Frequenzmessung kann auch vorher ausschließlich Hz liefern. Eine direkte Umrechnung aus PWM oder einem Vibrationspeak ist keine Drehzahlreferenz.

Nach bestätigter Messtechnik kann die Drehzahlaufnahme mit `normal_before` einer der unten geplanten Wiederholungen verbunden werden. Dann wird kein zusätzlicher Lüfterstart nur für RPM benötigt. Ganze 300 s bei 75 % und 25 kHz speichern; Drehzahl im festgelegten Abschnitt [180,300) s zusätzlich in 10-s-Abschnitten mit Methode und Unsicherheit berichten. Ein optisches Gerät mit nötiger Rotor-Markierung erfordert zuerst eine eigene Prüfung; der Plan autorisiert keine unkontrollierte Masseänderung am Rotor.

Ein einzelner solcher Lauf belegt die Drehzahl nur während dieses Laufs. Er ergänzt keine rückwirkenden RPM-Werte in die historischen Aufnahmen.

## R3 – Zwei weitere unabhängige Zustandsfolgen mit dem eingefrorenen Paket

Die bereits abgeschlossene unabhängige Folge vom 12.09. unter `upright_v4_frozen_airflow_test_20260912_073015/` wird als Folge 1 erhalten. Für einen überschaubaren Replikationsversuch werden **zwei weitere vollständige Folgen** geplant. Damit liegen drei getrennte Plattenaufnahmen und sechs zugehörige normale Referenzen vor. Drei Wiederholungen sind weiterhin ein begrenzter Pilotumfang, keine begründete populationsweite Genauigkeitsgarantie.

| Folge | Phase | Label | Soll-PWM | geplante Aufnahme |
|---|---|---|---:|---:|
| 2 | normal_before | NORMAL / 0 | 75 % | 300 s |
| 2 | airflow_modified | kontrollierte Änderung / 1 | 75 % | 300 s |
| 2 | normal_after | NORMAL / 0 | 75 % | 300 s |
| 3 | normal_before | NORMAL / 0 | 75 % | 300 s |
| 3 | airflow_modified | kontrollierte Änderung / 1 | 75 % | 300 s |
| 3 | normal_after | NORMAL / 0 | 75 % | 300 s |

Bei allen Läufen gelten 25 kHz und die bestehende Sensorkonfiguration. Die Platte ist wie in der gültigen Folge separat befestigt: 120 × 120 mm, parallel und 100 mm vor dem Luftauslass, ohne Kontakt zu Lüfter oder Sensor. Diese vorhandene Geometrie wird nicht stärker verändert, um bessere Kennzahlen zu erzielen. Die tatsächliche Wiederherstellung wird für jede neue Folge dokumentiert.

**Manuelle Reihenfolge:**

1. Ohne Platte bereitstellen, vollständigen Stillstand bestätigen, Versorgung anschließen und den nächsten Lauf freigeben. Die Freigabe benennt den aktuellen Stillstand und die angeschlossene Versorgung ausdrücklich. Die bereits geprüfte sichere Montage wird übernommen; eine neue Befestigung ist nicht gefordert.
2. Nach der Freigabe folgen 60 s zusätzliche Vorgabe 0 %, danach genau ein Start und 300 s Aufnahme ab möglichst nahe dem Stellbefehl. Anschließend 0 % setzen und zurücklesen.
3. Versorgung trennen, vollständigen Stillstand abwarten und ausschließlich die Platte einsetzen. Danach Versorgung wieder anschließen und den nächsten Lauf freigeben.
4. Nach dem Plattenlauf wieder 0 % und Rücklesung. Versorgung trennen, Stillstand abwarten, nur die Platte entfernen und anschließend Versorgung anschließen/freigeben.
5. Nach der normalen Rückkehrreferenz wieder 0 % und Rücklesung. Vor der nächsten Folge bleibt die Platte entfernt; auf den bestätigten Stillstand und die ausdrückliche nächste Freigabe warten.

Keine Fragen zum sichtbaren Lauf während einer Aufnahme, keine Antwortfristen und keine automatischen Wiederholungsstarts. Bei einem Fehler Teilaufnahme erhalten, nach Möglichkeit 0 % einstellen, den tatsächlich rückgelesenen Zustand melden und pausieren. Gleiche zusätzliche Auszeiten bedeuten keine gleichen gesamten Auszeiten; beide werden getrennt protokolliert. Ein rückgelesener Wert von 0 % ist kein automatischer mechanischer Stillstandsnachweis.

## Vorab festgelegte Auswertung und Abschlussentscheidung

- Unverändertes Pilotpaket `run_001/frozen`, Bundle-SHA-256 `cec1859bfb354bafef77a619e6d2c1ffd85b50787c87595aba9a1e20a80cdae5`; alle vorhandenen Modelldateien, Skalierungen und Schwellen bleiben eingefroren.
- Gesamten Anlauf speichern; nur [180,300) s für Modelle, 128 XYZ pro Fenster, Schritt 128, keine Überlappung oder Aufnahmegrenzenüberschreitung. Vorverarbeitung unverändert: Float64-Mittelwertentfernung je Achse, Float32, gespeicherter Scaler.
- Alle drei Methoden erhalten identische Fenster. Datenqualität, Zeitbasis, Host-Leseabstände, ungültige Fenster und unvollständige Reste werden getrennt erhalten. Nominale 200 Hz und beobachteter Durchsatz bleiben getrennt.
- Je Lauf Verwechslungszahlen und die zur vorhandenen Klasse passende primäre Rate berichten; je vollständiger Folge sowie zusammengefasst zusätzlich die definierten Zwei-Klassen-Kennzahlen. Hohe Fehlalarme und geringe Markierung des Plattenzustands bleiben Ergebnisse.
- 5-s-Vektor-AC-RMS mit eigener achsenweiser Mittelwertentfernung dient nur der Diagnostik. Vollständige Verläufe sowie [180,300) vergleichen; gleiche Achsen/Geometrie/Methodenregeln. Keine nachträgliche Verschiebung der 180-s-Grenze.
- Zeitliche Trends innerhalb eines Laufs und Mittelwertunterschiede zwischen Läufen getrennt berichten. Die Rückkehr wird mit beiden Normalreferenzen und der Variabilität über Folgen beurteilt; exakt gleiche RMS-Mittelwerte sind keine notwendige Bedingung mechanischer Rücksetzung.
- Die Untersuchung endet nach den zwei vollständig freigegebenen neuen Folgen, unabhängig von der Güte. Keine zusätzlichen Starts, bis ein günstiges Ergebnis entsteht. Ein Fehler wird nicht automatisch durch einen Ersatzlauf verdeckt.
- Es wird kein Mindest-F1 erfunden. Die Arbeit bewertet den vorhandenen Detektor; eine zuverlässige Erkennung darf erst beansprucht werden, wenn Umfang und Ergebnisse diese Aussage tragen. Zeigen die Wiederholungen erneut schwache Erkennung, lautet der Abschluss entsprechend. Ein neuer Detektor wäre ein neuer Entwicklungsauftrag mit neuen unabhängigen Tests.

## Aufwand und noch notwendige Mitwirkung

R3 benötigt 30 min reine Rohaufnahme, mindestens 6 min zusätzliche Auszeit sowie vier manuelle Plattenumbauten und die bestätigten Auslaufpausen. R1 ergänzt 60 s Sensoraufnahme nach Instrumentierung; R2 kann mit einem der Normalstarts kombiniert werden. Vorbereitung und Analyse hängen vom verfügbaren Messgerät ab. Der Nutzer wird nur für Geräteangaben, die tatsächliche Instrumentierung und die genannten Umbau-/Stillstandsfreigaben benötigt. Die persönliche Autorenprüfung und Unterschrift bleiben beim Autor.
