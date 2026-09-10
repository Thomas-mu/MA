# Protokoll vor Beginn der Messfolge

Geplant ist die zeitlich aufeinanderfolgende Sequenz Stillstand vor Betrieb →
50 % → 75 % → Stillstand nach Betrieb. Jede Phase enthält zwei getrennte
30-s-Aufnahmen mit fünf Sekunden Abstand. Innerhalb einer Phase bleibt die
PWM-Vorgabe konstant. Die Wiederholungen sind getrennte Dateien, jedoch keine
unabhängigen Neustarts. Montage, Sensorposition, 25-kHz-PWM-Frequenz, nominell
200 Hz ODR, Full Resolution, ±2 g und FIFO-Erfassung bleiben unverändert.

Vor jeder Stillstandsphase wird vollständiger mechanischer Stillstand visuell
bestätigt. Nach Umschaltung auf 50 % beziehungsweise 75 % folgen mindestens
30 s Einlaufzeit und die Bestätigung eines sichtbar gleichmäßigen Laufs.
Nach der abschließenden Umschaltung auf 0 % werden mindestens zehn Sekunden
abgewartet; erst die neue Sichtbestätigung gibt die letzten Aufnahmen frei.
Alle tatsächlichen Wartezeiten und Aufnahmezeitpunkte werden protokolliert.
Während der Aufnahmen laufen keine Analyse-, Trainings- oder Dokumentprozesse.

Die primären Kennwerte sind Achsenmittelwerte, Standardabweichungen mit
Normierung durch N und Vektor-AC-RMS. Jede Achse wird zuvor um ihren eigenen
Aufnahmemittelwert zentriert. Für eine Achse sind Standardabweichung und
AC-RMS dadurch identisch. Der Vektorwert ist die Wurzel der Summe der drei
Achsenvarianzen; die Standardabweichung des Beschleunigungsbetrags wird davon
getrennt geführt. Gleichanteile werden nicht als Schwingungsstärke ausgegeben.

Zusätzlich werden sechs nicht überlappende 5-s-Abschnitte je Aufnahme ausgewertet,
jeweils mit eigener Mittelwertentfernung. Ganze Aufnahmen erhalten gleiches
Gewicht. Berichtet werden absolute und relative Differenz der zwei Wiederholungen,
Abschnittsspannen und Überlappungen. Die Anfangs- und Endreferenz bleiben getrennt;
beide werden als Hintergrund für 50 % und 75 % herangezogen. Insbesondere wird
geprüft, ob die kleinste Betriebs-RMS über dem größten Hintergrundwert liegt.
Diese deskriptiven Abstände sind keine vorab garantierten Akzeptanzgrenzen.

Zwei Aufnahmen pro Phase reichen nicht für einen belastbaren statistischen
Nachweis. Zeitabschnitte ersetzen keine unabhängigen Versuchsreplikate. Die
festgelegte Reihenfolge kann Zeit- und Betriebspunkteffekte nicht vollständig
trennen. Eine Betriebspunktwahl soll Signalabstand und Wiederholbarkeit gemeinsam
berücksichtigen; 75 % wird nicht allein wegen einer größeren Amplitude bevorzugt.
Die Eignung für normale und anomale Zustände bei identischer PWM bleibt später
zu prüfen. In diesem Auftrag werden weder Modelle trainiert noch Anomalien
hergestellt. Worddatei und historische Protokolle bleiben unverändert.

Die Erfassung schreibt neue CSV-/JSON-Dateien unter
`data/pwm50_75_sequence_20260910/`. `run_sequence.py` hält den gemeinsamen
PWM-Lock und fragt die expliziten Phasenübergänge über stdin ab. Nur die
Stellmethoden schreiben PWM; Verifikationen ändern die Hardware nicht.
`analyze_sequence.py` verarbeitet erst die vollständig abgeschlossene Folge
von acht Aufnahmen und verwendet ausschließlich diese neuen Messdateien.
