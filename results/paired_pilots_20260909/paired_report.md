# Kontrolliertes Pilotpaar vom 09.09.2026

Die beiden neu erhobenen Pilotaufnahmen werden getrennt von Training, Validierung und unabhängigen Tests ausgewertet. Die Montage am Lüfterrahmen und der sichtbare gleichmäßige Betrieb wurden vom Nutzer bestätigt. 25 % bezeichnet den Softwaretastgrad; eine Drehzahl wurde nicht gemessen.

| Kennwert | Stillstand | Betrieb bei 25 % |
|---|---:|---:|
| Wertezahl | 6193 | 6205 |
| Beobachteter FIFO-Durchsatz / Hz | 206.480 | 206.847 |
| Größtes Hostintervall / ms | 7.104 | 6.009 |
| Vektor-AC-RMS / g | 0.012371 | 0.013099 |
| AC-RMS des Betrags / g | 0.008791 | 0.009230 |

In beiden Dateien sind Lücken-, Überlauf- und Sättigungsflags durchgängig falsch. Die Sampleindizes sind vollständig und monoton. Die FIFO-Tiefe ist maximal eins. Dies ist ein positiver Erfassungsbefund, kein Nachweis einer exakt bestimmten Zahl physikalischer Abtastungen oder einer kalibrierten Frequenzachse.

| Achse | AC-RMS Stillstand / g | AC-RMS Betrieb / g | Mittelwert Stillstand / g | Mittelwert Betrieb / g |
|---|---:|---:|---:|---:|
| X | 0.006465 | 0.006860 | -0.152954 | -0.154055 |
| Y | 0.005462 | 0.005926 | 0.006333 | 0.007122 |
| Z | 0.009024 | 0.009455 | -1.090168 | -1.089077 |

PSD: 512 Werte pro symmetrischem Hann-Fenster, 256 Werte Vorschub, Mittelwertentfernung je Segment, einseitige Leistungsdichte und arithmetische Mittelung der vollständigen Segmente. Die Bandintegration verwendet lineare Interpolation an gemeinsamen exakten Bandgrenzen und die Trapezregel. Die Diagnosebänder 1–90 Hz und 5–80 Hz dienen der breiten Gegenüberstellung; sie sind keine nachgewiesenen Nutzbänder oder vorgegebenen Akzeptanzgrenzen.

| Diagnoseband | Größe | Leistung Stillstand / g² | Leistung Betrieb / g² | Betrieb/Stillstand / dB | Bedingter Überschuss-SNR / dB |
|---|---|---:|---:|---:|---:|
| 1–90 Hz | x_g | 3.6549589e-05 | 4.1698665e-05 | 0.57 | -8.51 |
| 1–90 Hz | y_g | 2.6141572e-05 | 3.0747946e-05 | 0.70 | -7.54 |
| 1–90 Hz | z_g | 7.0755431e-05 | 7.7638762e-05 | 0.40 | -10.12 |
| 1–90 Hz | xyz_sum | 0.00013344659 | 0.00015008537 | 0.51 | -9.04 |
| 5–80 Hz | x_g | 3.099382e-05 | 3.6064551e-05 | 0.66 | -7.86 |
| 5–80 Hz | y_g | 2.1843511e-05 | 2.6728981e-05 | 0.88 | -6.50 |
| 5–80 Hz | z_g | 5.962179e-05 | 6.6098562e-05 | 0.45 | -9.64 |
| 5–80 Hz | xyz_sum | 0.00011245912 | 0.00012889209 | 0.59 | -8.35 |

Betrieb/Stillstand bezeichnet 10 log10(P_Betrieb/P_Stillstand). Der nur bei positivem Überschuss angegebene SNR-Schätzwert lautet 10 log10((P_Betrieb−P_Stillstand)/P_Stillstand). Er setzt einen stationären unveränderten Hintergrund, additive unkorrelierte Beiträge und eine gleiche mechanische Übertragung voraus. Das getrennte Pilotpaar belegt diese Annahmen nicht. Der Schätzwert ist deshalb kein unabhängig gemessener Lüfter-SNR.

| Zustand | 5-s-Abschnitt / s | Werte | FIFO-Durchsatz / Hz | Vektor-AC-RMS / g |
|---|---:|---:|---:|---:|
| Stillstand | 0–5 | 1033 | 206.505 | 0.012959 |
| Stillstand | 5–10 | 1033 | 206.477 | 0.012771 |
| Stillstand | 10–15 | 1032 | 206.480 | 0.012164 |
| Stillstand | 15–20 | 1032 | 206.425 | 0.012195 |
| Stillstand | 20–25 | 1033 | 206.451 | 0.012187 |
| Stillstand | 25–30 | 1030 | 206.461 | 0.011902 |
| Betrieb, 25 % PWM | 0–5 | 1035 | 206.811 | 0.012827 |
| Betrieb, 25 % PWM | 5–10 | 1034 | 206.912 | 0.012968 |
| Betrieb, 25 % PWM | 10–15 | 1034 | 206.856 | 0.013115 |
| Betrieb, 25 % PWM | 15–20 | 1034 | 206.835 | 0.013088 |
| Betrieb, 25 % PWM | 20–25 | 1035 | 206.864 | 0.012789 |
| Betrieb, 25 % PWM | 25–30 | 1033 | 206.800 | 0.013715 |

Die Spektren und Abschnittswerte sind in `paired_comparison.png` und `.pdf` dargestellt. Vollständige Kennwerte einschließlich Minima/Maxima, Achsenmittelwerten, Qualitätsflags und Datei-Hashes stehen in `paired_report.json`. Die jeweiligen Einzel-FFT-Berichte liegen in neuen Unterverzeichnissen; ihre generischen Einschränkungen beziehen sich auf die Einzelaufnahme. Erst dieser Paarbericht führt den kontrollierten Zustand und die bedingte Hintergrundsubtraktion zusammen.

Die kleine Leistungszunahme im Betrieb liefert einen messbaren Unterschied dieser beiden Dateien. Sie trägt allein keine belastbare allgemeine Trennung des Lüfternutzsignals vom Hintergrund: Es fehlen Wiederholungen, Unsicherheitsschätzung und eine Drehzahlreferenz. Größte Spektralbins werden keiner Drehzahl oder Blattfolge zugeordnet. Energie nahe der halben Abtastrate belegt weder Aliasfreiheit noch ein geeignetes Nutzband. Modelle und Schwellen werden aus dieser Analyse nicht freigegeben.
