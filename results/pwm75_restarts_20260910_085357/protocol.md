# Wiederholbarkeit bei 75 % PWM über drei separate Starts

Prospektiv festgelegt am 10.09.2026, vor der ersten Aufnahme.

- Vor jedem Start: 0 % PWM zurücklesen und neue Nutzerbestätigung des vollständigen mechanischen Stillstands abwarten.
- Drei separate Starts auf 75 % bei 25 kHz, mit unveränderter Montage und ADXL345-Konfiguration (200 Hz nominell, ±2 g, Full Resolution, FIFO Stream).
- Einlaufzeit: fester Timer von 60 s ab Abschluss des PWM-Stellbefehls. Die Nutzerbestätigung des sichtbar gleichmäßigen Laufs muss innerhalb dieser Zeit vorliegen. Keine Verlängerung der Einlaufzeit zur Überbrückung einer fehlenden Antwort.
- Ohne rechtzeitige positive Laufbestätigung: keine Aufnahme, Abbruch protokollieren und 0 % einstellen. Ein Ersatzversuch würde separat dokumentiert und neu angekündigt.
- Nach dem Timer: unveränderter 30-s-Recorder. Zeitpunkt des ersten XYZ-Messpunkts relativ zum Stellbefehl zusätzlich aus monotonen Nanosekunden berechnen; technische Startverzögerung gesondert ausweisen. Über 100 ms Startverzögerung als prüfbedürftige zeitliche Abweichung markieren, nicht als wissenschaftliche Signalqualitätsschwelle verwenden.
- Nach jeder Aufnahme oder einem Abbruch: angekündigte Rückstellung auf 0 %, zehn Sekunden Auslaufzeit, neue Sichtprüfung vor dem nächsten Start. Nach Start 3 ebenfalls abschließende Sichtprüfung.
- Je Start eigener begrenzter Steuerprozess; keine über Nutzerwartezeiten hinweg offene Toolsitzung zwischen den Versuchen. Gemeinsame PWM- und Sensorsperren während des Versuchs.
- Keine RPM-Ableitung aus PWM oder Sichtbeobachtung. Keine Modelltrainings oder künstlichen Anomalien.
- Auswertung: Rohdaten-/Metadatenhashes, vollständige XYZ-Punktzahl, beobachteter Hostdurchsatz getrennt von nomineller ODR, Zeitstempel und Qualitätsflags; Achsenmittelwerte, Standardabweichungen (ddof=0), Vektor-AC-RMS nach eigener Achsenmittelwertentfernung; sechs gleich lange 5-s-Abschnitte pro Aufnahme.
- Zwischen den Starts Spannweite und deskriptiven Variationskoeffizienten vergleichen; kurze Abschnitte nicht als unabhängige Neustarts zählen. Früheren75-%-Pilot nur als gesonderten Kontext vergleichen, da die Einlaufbedingungen abweichen.
- Drei Starts erlauben eine erste Prüfung über Neustarts, keinen belastbaren statistischen Nachweis und keinen Nachweis erfolgreicher Anomalieerkennung.
- Daten, Worddatei, historische Protokolle, Modelle und Quellcode aus dem Ausgangsbestand bleiben unverändert; separate neue Ergebnisse und abschließender Hashvergleich.
