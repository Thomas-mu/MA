# Vorläufige Wiederholungsprüfung: drei Aufnahmen

Die bestehenden Erstberichte bleiben unverändert. Diese Ergänzung vergleicht S₀, B₁ und die bei unveränderten 25 % PWM aufgenommene B₁-Wiederholung. S₁ ist noch nicht aufgenommen; die neue Sichtbestätigung des Stillstands steht aus. Keine Drehzahlmessung liegt vor.

| Kennwert | S₀ | B₁ | B₁-Wiederholung |
|---|---:|---:|---:|
| Samples | 6193 | 6205 | 6205 |
| FIFO-Durchsatz / Hz | 206.480 | 206.847 | 206.863 |
| Größtes Hostintervall / ms | 7.104 | 6.009 | 6.057 |
| Vektor-AC-RMS / g | 0.012371 | 0.013099 | 0.012954 |
| AC-RMS des Betrags / g | 0.008791 | 0.009230 | 0.009089 |

Alle drei Aufnahmen erfüllen die implementierten Eingangsprüfungen: abgeschlossene FIFO-Erfassung, verifizierter CSV-Hash, gültige lückenlose Sampleindizes und keine gesetzten Qualitätsflags. Diese technische Qualität bestätigt noch keine ausreichende Trennung von Nutzsignal und Hintergrund.

| Diagnoseband / XYZ-Summe | B₁ relativ S₀ | B₁-Wiederholung relativ S₀ |
|---|---:|---:|
| 1–90 Hz | 0.510 dB | 0.347 dB |
| 5–80 Hz | 0.592 dB | 0.371 dB |

| Fester Kandidat, ±0,8 Hz | B₁ relativ S₀ | Wiederholung relativ S₀ | 5-s-Bereich S₀ relativ eigenem Gesamtmittel | 5-s-Bereich Wiederholung relativ S₀ |
|---|---:|---:|---:|---:|
| X 54.54 Hz | 2.14 dB | 1.55 dB | -1.71…1.59 dB | -0.70…2.56 dB |
| X 71.51 Hz | 3.38 dB | 4.10 dB | -2.02…2.03 dB | 2.13…6.04 dB |
| Y 23.03 Hz | 3.85 dB | 1.58 dB | -3.38…0.98 dB | -0.49…3.99 dB |

Die Kandidatenfrequenzen und Bandbreiten wurden aus der ersten Aufnahme unverändert übernommen. Es erfolgt keine neue Kandidatensuche oder Anpassung an die Wiederholung. Verglichen wird die integrierte Leistung; eine lokale Maximalfrequenz in einem eingeschränkten Suchbereich ist kein unabhängiger Nachweis einer stabilen Linie.

Die vollständigen Achsenwerte, Minima/Maxima, Zeitabschnitte, Diagnosebandleistungen und bedingten Überschuss-SNR-Werte stehen in `three_recordings.json`. Negative Überschuss-SNR-Werte bedeuten unter den dokumentierten Additivitätsannahmen, dass der geschätzte zusätzliche Beitrag kleiner ist als der Hintergrund; daraus folgt nicht die Abwesenheit eines Signals.

Eine nachfolgende kontrollierte Stillstandsreferenz wird benötigt, um die unveränderte Hintergrundleistung zumindest empirisch gegenzuprüfen. Bis dahin bleibt die Messparameter- und Trainingsfreigabe offen. Die Begründung einer möglichen höheren ODR und die Grenzen von 200 Hz werden in `provisional_recommendation.md` zusammengeführt.
