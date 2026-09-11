# Drei unabhängige Normalstarts mit unveränderter neuer Montage

Je Lauf: neue ausdrückliche Stillstandsbestätigung; dann 60 s bei 0 % ab protokollierter Annahme der Antwort (monotone Hostzeit). Nach Vorbereitung und Ablauf dieser Zeit einmalig 75 % bei 25 kHz einstellen und unmittelbar 300 s aufzeichnen. Tatsächlichen Versatz des ersten XYZ-Punktes zu Befehlsaufruf, Befehlsabschluss und Tastdauer-Rücklesung dokumentieren. Danach 0 % einstellen, zurücklesen und mindestens zehn Sekunden auslaufen lassen. Vor dem nächsten Lauf neue Sichtbestätigung abwarten. Keine Antwortfrist, kein automatischer Ersatzstart, keine Entscheidung steuert während der Messung den Lüfter.

Die feste Auszeit nach Bestätigung wird für alle drei Läufe gleich angefordert. Die zusätzliche Zeit seit dem vorherigen Ausschalten bis zur Antwort ist variabel; beide Zeiten werden getrennt angegeben. Gleiche thermische Ausgangsbedingungen sind damit nicht bewiesen.

Die bestätigte neue Montage bleibt unverändert: ADXL345 mit zwei Schrauben am äußeren, feststehenden Lüfterrahmen; Platine schräg. Bestehende Sicherheitsbestätigung vom heutigen Pilot gilt weiter. Externe 12-V-Versorgung bleibt angeschlossen. ADXL345: nominell 200 Hz, ±2 g, Full Resolution, FIFO Stream; I²C-Konfiguration 100 kHz. GPIO18 (BCM), physisch Pin 12, PWM0_CHAN2/a3, 40.000 ns Periodendauer.

Primärer, vorab festgelegter Analysebereich: 180–300 s seit erstem tatsächlich erfasstem XYZ-Punkt, Versatz zum PWM-Befehl je Lauf separat. Je fünf Sekunden eigene Achsenmittelwerte entfernen und Vektor-AC-RMS berechnen. Die 180 s sind eine zu prüfende Einlaufzeit. Auswertung aller 60 Abschnitte je Lauf; im primären Bereich jeweils 24 Abschnitte. Keine nachträgliche Auswahl besser passender Intervalle. Zeitstempel, Durchsatz, FIFO-/Lücken-/Überlauf-/Sättigungsflags sowie Host-Leseabstände prüfen. Keine Interpolation oder stillschweigende Verwerfung von Daten.

Innerhalb jedes Laufs Abschnittsverteilung und Verlauf angeben. Zwischen den drei Läufen deren Abschnittsmittel, Bereiche, Standardabweichungen und Drift vergleichen. Benachbarte 5-s-Abschnitte sind keine unabhängigen Neustarts; drei Läufe erlauben nur eine Pilotbewertung. Keine Signifikanz oder erfolgreiche Anomalieerkennung aus der Trennung zum Stillstand ableiten. Frühere Aufnahmen werden nicht in die drei neuen Wiederholungen eingerechnet.

Alle Daten und Berichte erhalten neue Pfade. Bei Fehlern nach Möglichkeit 0 % anfordern und den tatsächlichen Steuerungsstatus melden. Keine Modelle trainieren, keine Anomalien erzeugen, bestehende Dateien und Word unverändert lassen.
