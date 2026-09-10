# Vorläufiger Messparameterentscheid nach drei Piloten

Entscheidung: Noch keine Freigabe für neue Trainings-/Validierungsaufnahmen oder
Modelle. Der technische Teil der Erfassung ist in S₀, B₁ und B₁-Wiederholung
positiv geprüft. Die geringe breitbandige Trennung, zeitliche Schwankungen und
die noch fehlende Stillstandsreferenz nach dem Betrieb lassen die endgültige
Nutzband- und Driftbeurteilung offen. Die wiederkehrende schwache X-Komponente
um 71 Hz wird als Befund erhalten; ein fehlendes Lüftersignal wird nicht behauptet.

| Parameter | Entscheidung und Begründung |
|---|---|
| 200 Hz ODR, FIFO | Für S₁ beibehalten, damit der Referenzvergleich dieselbe Messkette verwendet; entspricht der dokumentierten Grenze der vorhandenen 100-kHz-I²C-Konfiguration. Beobachtete 206,5–206,9 Werte/s werden getrennt ausgewiesen. |
| Full Resolution, ±2 g | In drei Piloten keine Sättigungsflags; gleiche Einstellung für S₁. Reserve für Anomalien und absolute Sensorkalibrierung sind damit nicht nachgewiesen. |
| 512 Samples, Hann, Schritt 256 | Diagnose mit rund 0,4 Hz Stützstellenabstand. Kein Drehzahlnachweis und keine nachträgliche Festlegung eines endgültigen Nutzbandes. |
| 1–90 und 5–80 Hz | Diagnosebänder für den Vergleich; keine geprüften Filter-/Modellbänder. |
| H = S = 128 XYZ | Unveränderte Modelleingabe, nominell 0,64 s bei 200 Hz; noch kein abschließender Eignungsnachweis. |
| 30 s je Pilot | Sechs zeitliche 5-s-Abschnitte erlauben eine Driftbetrachtung; sie sind keine unabhängigen Versuchsreplikate. |
| 25 % bei 25 kHz | Vom Nutzer gewählter erster Normalbetriebspunkt; in beiden Betriebsaufnahmen konstant gehalten. Keine Gleichsetzung mit RPM. |

Abgeschlossener Status, endliche Daten, fortlaufende Indizes und null gesetzte
Gap-/Overrun-/Sättigungsflags sind die bereits implementierten technischen
Kriterien. Die Piloten erfüllen diese Prüfungen. Daraus folgt weder eine exakt
bekannte Verlustzahl noch Aliasfreiheit oder ein hinreichender Nutzsignalabstand.
Numerische Grenzen für Signaltrennung, Drift und Bandbreite werden noch nicht
als erfüllt ausgegeben. Ihre spätere Festlegung muss vor der unabhängigen
Testserie erfolgen und darf deren Ergebnisse nicht verwenden.

Nächster Schritt: neue Sichtbestätigung vollständigen Stillstands nach der
Abschaltung um 20:32:40 UTC, anschließend angekündigte 30-s-Aufnahme S₁ bei
unverändert 0 % PWM und unveränderter Montage. Der vorbereitete Runner
`run_post_operation_standstill.py` wurde noch nicht ausgeführt. Ein neuer
Bestätigungsbeleg muss die tatsächliche Nutzerantwort enthalten.

Die JSON-Datei enthält die drei CSV-/Sidecar-Prüfsummen und die technischen
Messzusammenfassungen. Kein bestehendes Profil wurde auf `verified` gesetzt.
Die Trainings-/Validierungsfolge und das eingefrorene Vergleichs-Bundle sind
vorbereitet; es wurden keine neuen Modelle oder Schwellen erzeugt.
