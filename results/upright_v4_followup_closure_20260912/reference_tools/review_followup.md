# Abschlussprüfung nach Korrektur des Referenzimports

Stand: 12.09.2026. Gezielte unabhängige Nachprüfung der beiden Befunde aus [review.md](review.md). Quellcode, Tests, README und Korrekturprotokoll wurden nur gelesen. Keine Hardwarezugriffe; ausschließlich dieser neue Prüfbericht wurde im Repository angelegt.

**Beide Befunde sind im geprüften Umfang behoben.**

1. **Kein Nachweis aus Metadaten:** `independent_sensor_odr_reference_eligible`, `independent_rpm_reference_eligible` und `software_verified_physical_reference` sind im Ausgabecode fest auf `false` gesetzt. `sensor_odr_estimate_hz` bleibt `null`. Ein vorhandener Zahlenwert unter `conditional_sensor_odr_estimate_hz` trägt ausdrücklich den Status `conditional_on_external_mapping_claim`. Die RPM-Schätzung ist analog als bedingte Umrechnung externer Angaben bezeichnet. Eine unbewiesene MEASUREMENT-Deklaration mit positiv behaupteter 1:1-Zuordnung ändert den Nachweisstatus nicht.
2. **Numerische Prüfung vor Ausgabe:** Abgeleitete Intervalle, Frequenzen und RPM-Schätzungen werden auf positive endliche Werte geprüft. Die zusätzliche rekursive Prüfung erfasst sämtliche Ergebniszahlen einschließlich Statistiken. `run()` serialisiert das gesamte Ergebnis vor `mkdir()`. Die ursprünglichen Gegenbeispiele mit Zeiten `0, 1e-320` beziehungsweise `−1e308, +1e308` werden nun mit nachvollziehbaren ValueError-Meldungen zurückgewiesen; in beiden Fällen bleibt der Ergebnisordner nachweislich unangelegt.

Der gehaltene DATA_READY-Fall (`rising@0`, `falling@1`, `rising@1.01`) wurde nochmals mit ausschließlich künstlichen, ausdrücklich so bezeichneten Angaben getestet, darunter die bewusst unbewiesene Metadatenbehauptung MEASUREMENT. Ergebnis: alle genannten Nachweisfelder `false`, eigentliche Sensor-ODR `null`; lediglich die bedingte Umrechnung ergibt 0,9900990099 Hz. Damit entsteht kein unabhängiger ODR-Nachweis aus dieser Ereignisliste.

Die vollständige aktuelle Regression wurde mit `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s results/upright_v4_followup_closure_20260912/reference_tools -p 'test_reference_edges.py' -q` erneut ausgeführt: **26 Tests bestanden**, 0,216 s. Temporäre Gegenbeispieldateien wurden automatisch entfernt. README und [review_changes.md](review_changes.md) beschreiben die nun tatsächlich implementierte Grenze zutreffend.

Diese Freigabe betrifft den Offline-Import als konservative Vorbereitung. Eine physische Drehzahl-, Takt- oder Puls-/Samplezuordnungsprüfung ist damit weiterhin nicht durchgeführt.

Geprüfte SHA-256-Werte:

- `analyze_reference_edges.py`: `ed2844a94860d4373610d739c9074eec3a934c64e729c5d4b370c54b0717eadd`
- `test_reference_edges.py`: `0d5f5362424d2c215ffb61667fe64cfa8cd38b22b2a67b3e91735fe5a1cd11a8`
- `README.md`: `c70fa9f0248350ad2a4bdbc7acfd08e7f14b499cd6e20844cd4d6e57a73b5131`
- `review_changes.md`: `67445ea30f250482b80774a21cbb734680ba5ee22b6a5e99bddc2ce3d42b0323`
