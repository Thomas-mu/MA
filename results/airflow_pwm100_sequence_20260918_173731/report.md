Plattenversuch bei 100 % PWM – abgeschlossen

Reihenfolge: ohne Platte → mit Platte → wieder ohne Platte. Je Phase 300 s; danach 0 % PWM. Alle drei Aufnahmen und die unveränderten Quell-/Modelldateien sind geprüft.

| Phase | Gültige Modellfenster | RMS-Alarme | IF-Alarme | AE-Alarme | Vektor-AC-RMS [g] |
|---|---:|---:|---:|---:|---:|
| Ohne Platte (vorher) | 191 / 192 | 100.0 % | 100.0 % | 100.0 % | 0.056500 |
| Mit Platte | 194 / 194 | 100.0 % | 100.0 % | 100.0 % | 0.070870 |
| Ohne Platte (nachher) | 194 / 194 | 100.0 % | 100.0 % | 100.0 % | 0.060751 |

Auswertung jeweils [180,300) s seit PWM-Start. Die physische Schwingung ist der Mittelwert der Vektor-AC-RMS-Werte aus 5-s-Abschnitten ohne gemeldete Sensorflags; alle Originalabschnitte bleiben gespeichert.

Mit Platte verändert sich dieser Schwingungswert gegenüber vorher um +25.44 % und gegenüber nachher um +16.66 %. Die beiden Phasen ohne Platte unterscheiden sich um +7.52 %.

Das eingefrorene v4-Modellpaket verwendet seine unveränderte 75-%-Referenz. Die Alarmanteile müssen daher zusammen mit den Referenzphasen beurteilt werden; ein Alarm allein weist keinen Platteneffekt oder Defekt nach. Es wurde nicht nachtrainiert oder nachkalibriert.

Der erste Startversuch von Phase 2 wurde vor einer PWM-Änderung durch eine parallel laufende GUI blockiert. Die GUI wurde regulär geschlossen; der Versuch ist separat archiviert. Die anschließende Plattenaufnahme wurde vollständig ausgeführt.

Ergebnisse: [Screenshot aller Phasen](screenshot_normal_after.png), [Diagramm](comparison_through_normal_after.png), [vollständige Kennzahlen und Prüfungen](sequence_summary.json).
