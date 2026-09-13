# Abschließender Statistik-Textreview

Geprüfte Datei: `thesis_pilot_unformatted.docx` im selben Verzeichnis. SHA-256 des vollständig in den Speicher gelesenen Prüfstands: `1a7d79f047683f7da8760ca5b6ec95cbd5f22c5965d354aa9e42b76775079967`. Prüfung am 13.09.2026. Grundlage des Zahlenabgleichs: `statistical_audit.md` und `statistical_audit.json`. Dies ist ein Textreview, keine erneute Rohdatenprüfung. Es wurden keine Inferenz, Messung, Modelländerung oder Hardwarezugriffe durchgeführt; das Word-Dokument wurde ausschließlich gelesen.

**Ergebnis: Keine sachlich erheblichen Zahlenfehler oder überzogenen Schlussfolgerungen in den gezielt geprüften neuen bzw. überarbeiteten Passagen gefunden. Die Pilotabgrenzung bleibt nachvollziehbar.**

## Geprüfte Passagen

| Passage | Prüfung und Ergebnis |
|---|---|
| Zusammenfassung | 194 positive Fenster; RMS 7, IF 4, AE 0 Markierungen; F1 6,93 %, 4,04 %, 0 % korrekt. Abschnitt [180,300) s einer 300-s-Aufnahme ausdrücklich genannt. Sensor-P99-Bereich 6,113–28,577 ms mit dem Audit bestätigt. Keine zuverlässige Änderungserkennung oder allgemeine Defektleistung behauptet. |
| Tabelle 7-10, FF/H-Matrix | FF2/H1 auf eine Plattenfolge beschränkt. Für FF3/H2 liegen tatsächlich in allen 18 Prozessen (9 Sensor, 9 Replay) P99 unter dem jeweiligen Intervall und null Überschreitungen vor. Die Matrix bezeichnet diese nicht als 18 unabhängige physikalische Zustandsversuche. FF4/H3 ausdrücklich deskriptiv und durch Startvariabilität begrenzt. |
| F1-Absatz in 7.4 und Diskussion | 582 gültige Fenster der vollständigen Folge sowie F1-Differenz AE minus RMS von −6,93 Prozentpunkten stimmen. Die 194 positiven Fenster werden einer einzigen Aufnahme zugeordnet. H1 bleibt in dieser Folge nicht bestätigt; kein allgemeiner Überlegenheitsnachweis für RMS. |
| Mittelwerte und Einzelfenster in 7.5 | Der Text unterscheidet korrekt den Mittelwert der drei Achsenfehler von der Aussage über jede einzelne Schwellenentscheidung. Der ergänzte Satz, dass ein kleinerer Gruppenmittelwert allein den Nullbefund nicht belegt, beseitigt die mögliche Überinterpretation. Das eingefrorene AE-Limit von rund 0,54436 ist korrekt. |
| H3 in 7.6 | 75-%-AE-FPR 64/1164 = 5,50 %, 50-%-AE-FPR 35/582 = 6,01 %, Differenz +0,52 Prozentpunkte korrekt gerundet. Spannweite 0–26,29 % bei 75 % sowie Verlauf 8,76→3,61 % bei 50 % korrekt. Das Pooling bleibt als Mischung erhalten; einheitliche oder kausale Verschiebung wird ausdrücklich nicht behauptet. |
| Kalibrierungspräzisierung in 6.5 | Die Doppelnutzung der einen normalen Validierungsaufnahme für Epochenwahl und Schwelle ist nun ausdrücklich benannt. Vom Test getrennt bedeutet hier weiterhin keine unabhängig zusätzliche Kalibrierungsstichprobe. |
| Fazit | Negative Erkennungsergebnisse bleiben erhalten. H2 ist auf hostseitige Verarbeitung, endliche Prozesse und 120 s aktive Bewertung begrenzt. H3 bleibt nicht pauschal bestätigt. Offene Wiederholungs-, Drehzahl- und Messkettennachweise werden nicht als ausgeführt dargestellt. |
| Anhang zur Klassenverteilung | 388 normale und 194 veränderte Fenster sowie 66,67 % Accuracy für stets „normal“ korrekt. IF-Precision von 100 % wird zutreffend auf vier Alarme und 190 nicht markierte positive Fenster eingegrenzt. |

## Optionale sprachliche Präzisierungen

Diese Punkte ändern keine Zahlen oder Ergebnisbewertung und sind keine Hindernisse für den Abschluss:

- **H3, Abschnitt 7.6:** „H3 wird für den Autoencoder nur in der Richtung des zusammengefassten Anteils unterstützt“ ist durch den unmittelbaren Zusatz „weder allgemein noch kausal bestätigt“ ausreichend eingegrenzt. Noch eindeutiger deskriptiv wäre: „Der zusammengefasste Autoencoder-Anteil ist lediglich in seiner Richtung mit H3 vereinbar.“ Die Aussage zur entgegengesetzten gepoolten Richtung von RMS und IF bleibt bestehen.
- **Tabelle 7-9, A8:** „CPU, RSS, Modellgrößen, Queue und Verluste gemessen“ könnte „CPU, RSS, Modellgrößen und Queue gemessen; verworfene Entscheidungsfenster gezählt“ lauten. „Verluste“ bezeichnet hier Softwareverwerfungen; unbekannte physische Sensorverluste wurden nicht gemessen. Die übrigen Abschnitte unterscheiden diese Begriffe bereits korrekt.

Keine zusätzlichen Signifikanztests oder Konfidenzintervalle sind für diese Textfassung erforderlich. Die geringe Zahl unabhängiger positiver Aufnahmen und die nicht randomisierte PWM-Vergleichsstruktur bleiben offen und werden angemessen beschrieben.
