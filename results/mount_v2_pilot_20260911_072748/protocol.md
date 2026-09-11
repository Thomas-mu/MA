# Pilot der neuen vorläufigen Sensorbefestigung

Die neue Aufbauversion ist getrennt vom bisherigen Aufbau zu behandeln. Alte Messungen werden nicht als gemeinsame Normalreferenz verwendet.

## Reihenfolge

1. Ausdrückliche Nutzerbestätigung der Prüfungen bei getrennter Versorgung: Rotorfreiheit, sichere Kabelführung, keine elektrischen Kurzschlüsse, Sensorplatine fest und nicht verbogen. Die Angabe „sitzt fest“ allein öffnet die Startsperre nicht.
2. Sensorerkennung mit bestehender Software; ADXL345 0xE5, nominell200Hz, ±2g, Full Resolution, FIFO Stream, konfigurierte I²C-Frequenz100kHz. Prüfung und ursprüngliche Registerwerte sind separat protokolliert.
3. Vor den Referenzen: aktuelle Sichtbestätigung vollständigen Stillstands. Für den Vorher/Nachher-Vergleich externe12-V-Versorgung in beiden Stillstandsphasen angeschlossen und PWM0%; falls sie noch getrennt ist, Wiederanschluss erst nach vollständiger Sicherheitsbestätigung und Rücklesung von0%, danach neue Stillstandsbestätigung. Keine Annahme, dass0% mechanischen Stillstand garantiert.
4. Zwei separate30-s-Stillstandsaufnahmen bei0%, mit fünf Sekunden Abstand und unveränderter Montage.
5. Ein angekündigter Start auf75% bei25kHz, ohne absichtliche Einlaufpause unmittelbar gefolgt von einer durchgehenden300-s-Aufnahme. Monotone Zeitstempel für Befehlsaufruf, Befehlsabschluss und tatsächlichen ersten XYZ-Punkt; sysfs-Schreib-/Rücklesejournal zusätzlich erhalten. Keine Antwortfrist und kein automatischer Ersatzstart.
6. Anschließend0% anfordern, zurücklesen und zehn Sekunden Auslaufzeit abwarten. Erst nach neuer ausdrücklicher Nutzerbestätigung des mechanischen Stillstands eine zusätzliche30-s-Schlussreferenz.
7. Auch bei Erfassungsfehlern nach Möglichkeit0% über die geprüfte Steuerung anfordern; tatsächliche Rücklesung oder fehlgeschlagene Rückstellung melden. Teilaufnahmen und Fehlerjournale bleiben erhalten.

## Auswertung

Alle Dateien separat mit Aufbaukennung, Aufnahmezweckpilot, UTC-/monotonen Zeitstempeln, PWM-Vorgabe, Sensorparametern, XYZ-Punktzahl und Qualitätsflags. Nominelle ODR getrennt vom beobachteten Durchsatz(N−1)/(letzter−erster Hostzeitpunkt). Vollständige XYZ-Punkte von einzelnen Achsenwerten unterscheiden.

Vektor-AC-RMS=sqrt(mean((X−MittelX)^2+(Y−MittelY)^2+(Z−MittelZ)^2)); für jeden nicht überlappenden5-s-Abschnitt die Achsenmittelwerte neu bestimmen. Je30-s-Referenz sechs Abschnitte, im300-s-Betrieb sechzig Abschnitte. Zeiten der Betriebsabschnitte zum tatsächlichen ersten XYZ-Punkt definieren und den Versatz zum PWM-Befehl gesondert darstellen.

Vergleich der beiden Anfangsreferenzen und der einzelnen Schlussreferenz: Achsenmittelwerte, Achsenstreuungen, Gesamt-Vektor-AC-RMS, Abschnittsbereiche und Vorher/Nachher-Änderung. Eine Schlussreferenz erlaubt keine Schätzung der Wiederholungsstreuung am Ende. Betriebsverlauf und Abstand zum neuen Stillstandsbereich beschreiben; keine nachträgliche Bestehensschwelle. Ein einzelner Betriebslauf belegt keine allgemeine Reproduzierbarkeit oder erfolgreiche Anomalieerkennung. Keine Modelle trainieren, keine Anomalien erzeugen, keine Word-/Altdateien ändern.
