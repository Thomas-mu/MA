# Einordnung des ersten kontrollierten Pilotpaars

Die technische Erfassung ist für beide 30-s-Dateien positiv dokumentiert: 6.193 beziehungsweise 6.205 Werte, lückenlose Indizes und keine gesetzten Lücken-, Überlauf- oder Sättigungsflags. Das größte Hostintervall beträgt 7,104 ms im Stillstand und 6,009 ms im Betrieb. Die beobachteten FIFO-Durchsätze von 206,480 und 206,847 Hz liegen um 3,240 beziehungsweise 3,423 % über der nominellen Sensoreinstellung von 200 Hz. Dies sind aus Hostzeitpunkten geschätzte Durchsätze; die Messung liefert keine unabhängigen Sensorzeitstempel. Die Frequenzauflösung der 512-Werte-Spektren beträgt rund 0,403 beziehungsweise 0,404 Hz.

Die Signaltrennung ist wesentlich schwächer belegt als die technische Erfassung. Der Vektor-AC-RMS steigt von 0,012371 auf 0,013099 g. Die 5-s-Abschnitte überlappen jedoch: 0,011902–0,012959 g im Stillstand und 0,012789–0,013715 g im Betrieb. Im Stillstandsversuch nimmt dieser Kennwert vom ersten zum letzten Abschnitt ab. Diese Schwankung ist bei einer Hintergrundsubtraktion zu berücksichtigen.

Die summierte XYZ-Leistung im Diagnoseband 1–90 Hz steigt um 0,510 dB und im Band 5–80 Hz um 0,592 dB. Bei angenommener unveränderter, additiver und unkorrelierter Hintergrundleistung ergeben sich Überschuss-SNR-Schätzungen von −9,042 beziehungsweise −8,353 dB. Die Annahmen sind durch je eine Aufnahme nicht nachgewiesen. Diese Zahlen sind keine unabhängig gemessenen Lüfter-SNR-Werte und keine vorgegebenen Freigabegrenzen.

Die explorative Prüfung lokaler Maxima zeigt einzelne wiederkehrende Spektralkandidaten. Eine pauschale Gleichsetzung der gesamten Betriebsaufnahme mit Rauschen wäre daher ebenfalls unbelegt.

| Kandidat | Lokales Maximum gegenüber benachbarter Median-PSD | Bandverhältnis zum Stillstand, gesamter Betrieb | Bandverhältnis in 5-s-Abschnitten |
|---|---:|---:|---:|
| X bei 54,54 Hz | 4,18 dB | 2,14 dB | 1,45 bis 3,85 dB |
| X bei 71,51 Hz | 3,82 dB | 3,38 dB | 0,67 bis 4,50 dB |
| Y bei 23,03 Hz | 2,63 dB | 3,85 dB | 0,02 bis 9,53 dB |

Die hier ausgewerteten Kandidatenbänder umfassen jeweils ±0,8 Hz. Als lokale Umgebung für den Median dient ±5 Hz mit Ausschluss von ±1,2 Hz um den Kandidaten. Diese rein diagnostischen Breiten und die Rangfolge lokaler Maxima sind keine vorab festgelegten Akzeptanzkriterien. Die Kandidaten wurden aus derselben Betriebsaufnahme ausgewählt, deren Abschnitte anschließend geprüft wurden. Das Verfahren stellt deshalb keine unabhängige Bestätigung oder Signifikanzprüfung dar.

Beim Y-Kandidaten von 23,03 Hz entsteht die stärkste Erhöhung im Abschnitt 10–15 s mit 9,53 dB; in den übrigen Abschnitten beträgt sie lediglich 0,02–2,29 dB. Der größte Bin eines gemittelten Spektrums kann daher nicht automatisch als zeitlich stabile Linie gelten. Die schwachen wiederkehrenden X-Kandidaten verdienen eine Wiederholungsprüfung, erlauben ohne unabhängige Drehzahlreferenz aber keine Zuordnung zu Rotation oder Blattfolge.

Die jeweils obersten 20 % des einseitigen Frequenzbereichs enthalten je nach Achse rund 17–19 % der PSD-Summe. Daraus folgt kein Nachweis von Aliasfreiheit oder eines ausreichenden Abstands zur halben Abtastrate. Das Pilotpaar begründet noch keine endgültige Wahl eines Nutzbandes.

Aus diesem Paar allein wird keine Trainingsfreigabe abgeleitet. Eine weitere Betriebsaufnahme bei unveränderten 25 % PWM und eine nachfolgende kontrollierte Stillstandsreferenz können prüfen, ob die kleinen Leistungsunterschiede und die Spektralkandidaten wiederkehren. Die endgültige Entscheidung über Messparameter und Freigabe bleibt der gemeinsamen Auswertung vorbehalten. Kein Modell, keine Skalierung und keine Schwelle wurden durch diese Auswertung verändert.

Belege: `paired_report.json`, `paired_report.md`, `paired_comparison.png`/`.pdf` und `spectral_persistence.json` mit zugehörigen Grafiken. Die Eingangsdaten wurden ausschließlich gelesen; SHA-256-Werte vor und nach der Paaranalyse sind identisch.
