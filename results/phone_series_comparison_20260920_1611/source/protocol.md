# Smartphone-Messreihe: Versuch 1 bis 10

Google Pixel 9a; unveränderte Positionen, Orientierung und Befestigungen. Das bestehende Profil standlauf_pwm75_200hz einschließlich aller Modelle, Standardisierung, 128/128-Fenster und Schwellen bleibt eingefroren.

75 % PWM bei 25 kHz werden vor der Aufnahme gesetzt und rückgelesen. Einlaufzeit 30 s, danach mindestens 30 s Normalbetrieb. Alle Rohdaten einschließlich Einlauf werden gespeichert. Zehn Anrufe mit jeweils Aufforderung und Rückmeldung; mindestens 30 s Ruhe nach jeder Rückmeldung. Nach Versuch 10 automatischer kontrollierter Stopp nach mindestens 30 s Nachlauf. Kein 600-s-Limit. Ein Stop-Befehl oder SIGTERM beendet kontrolliert. Die PWM wird in keinem Abschnitt und auch beim Aufnahmestopp geändert.

Marker verwenden lokale Pi-Zeit und dieselbe monotone Zeitbasis wie die Aufnahme. Sie begrenzen Suchbereiche und messen keinen Vibrationsbeginn oder kein Vibrationsende. Die Dauer eines Anrufs wird nicht vorgegeben. Die vorab gespeicherten Regeln stehen in analysis_rules.json. Methodenvergleich und separater Rechenzeitbenchmark folgen nach Abschluss; es entstehen keine gemessenen Live-Ausgabezeiten.
