# Korrekturen nach Software-Review

1. **Metadatenanspruch und physische Verifikation getrennt.** Boolean-Werte und Freitext zu PPR, Erfassungsvollständigkeit oder DATA_READY-Zuordnung aktivieren keinen unabhängigen Nachweis. `independent_rpm_reference_eligible`, `independent_sensor_odr_reference_eligible` und `software_verified_physical_reference` bleiben grundsätzlich `false`. RPM und gegebenenfalls ODR können nur als ausdrücklich bedingte Umrechnungen externer Angaben erscheinen. Eine separat überprüfbare Burst-/Pulszuordnung wird von diesem kleinen Import nicht verarbeitet. Die Ausgabeschemaversion ist deshalb 2; das Metadaten-Eingabeschema bleibt 1.

2. **Abgeleitete Zahlen vor Ausgabebeginn geprüft.** Auch endliche Zeitstempel können nichtendliche Differenzen, Frequenzen oder Statistiken erzeugen. Eine rekursive Endlichkeitsprüfung erfasst sämtliche Ergebniszahlen; Berechnungsfehler werden als Eingabefehler zurückgewiesen. Zusätzlich wird die komplette JSON-Ausgabe vor `output.mkdir` serialisiert. Numerisch unzulässige Daten erzeugen somit keinen leeren oder teilweise beschriebenen Ergebnisordner.

3. **Tests erweitert.** Die bisherigen 21 Testszenarien bestehen weiter; hinzugekommen sind fünf Tests für unbewiesene Metadatenansprüche und numerische Grenzfälle. Insgesamt bestehen 26 Tests. Sämtliche Eingaben sind ausdrücklich künstliche Softwaretests, auch wenn ein Grenzfall bewusst eine unbewiesene `MEASUREMENT`-Deklaration enthält.

Es erfolgten keine Hardwarezugriffe, keine PWM-Änderungen und keine Änderungen an Originaldaten, Modellen, Berichten außerhalb dieses Werkzeugs oder der Worddatei.
