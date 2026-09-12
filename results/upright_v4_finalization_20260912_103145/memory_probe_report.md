# Explorative Prüfung des Speicherverlaufs

Diese nachgelagerte Softwarediagnose verändert weder die abgeschlossenen Laufzeitmessungen noch den gemessenen Quellcode. Sie verwendet sechsmal dieselbe gespeicherte Normalaufnahme, den Fensteraufbau und ausschließlich den eingefrorenen RMS-Auswerter. Es erfolgen keine Sensorzugriffe oder Lüfterstarts. Queue, Journale und Sensorerfassung sind nicht Teil dieser Probe. Die 1.164 Entscheidungen sind keine neuen unabhängigen Normaltests.

In den neun eigentlichen Sensorläufen nahm der RSS zwischen erster und letzter Ressourcenprobe im aktiven Abschnitt [180,300) s um 1,219–1,844 MiB zu. Die folgende Probe verwendet zusätzlich `tracemalloc` und ist ausdrücklich kein Latenz- oder RAM-Benchmark des regulären Betriebs.

| Zeitpunkt der Probe | insgesamt verarbeitete Fenster | Prozess-RSS [MiB] | aktuell durch tracemalloc erfasste Allokationen [KiB] |
|---|---:|---:|---:|
| Nach Laden und Aufwärmen, vor den sechs Durchläufen | 0 | 125,344 | 0,359 |
| Nach sechs Durchläufen | 1.164 | 126,891 | 442,786 |
| Nach explizitem GC-Aufruf und zwischenzeitlichem Diagnosesnapshot | 1.164 | 127,578 | 88,651 |

Die größten zuvor noch registrierten Zuwächse stammen aus Allokationspfaden des DataFrame-Aufbaus und interner pandas-/NumPy-Verarbeitung. Nach dem expliziten GC-Aufruf ist die erfasste aktuelle Allokationsmenge deutlich kleiner. Der GC-Rückgabewert beträgt jedoch null; ein Nachweis eingesammelter zyklisch unerreichbarer Objekte liegt damit nicht vor. Die Diagnose erzeugt zudem eigene Snapshots und Listen: Der erhöhte Objektzähler nach dem Snapshot ist deshalb nicht mit einer Zunahme zurückgehaltener Messfenster gleichzusetzen.

Der RSS fällt in dieser instrumentierten Probe nicht entsprechend ab. Er umfasst mehr als die von tracemalloc aktuell registrierten Python-Allokationen. Die Ergebnisse belegen keine lineare, unbegrenzte Speicherung aller Fenster. Ebenso wenig beweisen sechs kurze, ungetaktete Durchläufe eine allgemeine Speicherobergrenze oder erklären den gesamten RSS-Verlauf der Sensorprozesse. Unterschiedliche Messumfänge und Diagnose-Overhead werden nicht miteinander verrechnet.

Für die abgeschlossene Pilotbewertung genügt es, den positiven RSS-Verlauf ausdrücklich zu erhalten und den Nachweis auf die gemessene Dauer zu begrenzen. Vor einem behaupteten unbegrenzten Dauerbetrieb wäre eine eigene längere Softwareprüfung mit zeitlich verdichteten Speicherkennwerten, dokumentiertem Aufwärmen und Allokationszuordnung erforderlich. Eine gegebenenfalls daraus folgende Implementierungsänderung erhielte neue Quellcodehashes und einen erneuten Konsistenz- und Laufzeitnachweis. Im aktuellen Auftrag wurde keine Speicherbereinigung in den gemessenen Datenweg eingebaut.

Maschinenlesbare Einzelwerte, Allokationspfade und Quellenhash: [memory_probe.json](memory_probe.json). Reguläre Messwerte: [runtime_analysis/runtime_report.md](runtime_analysis/runtime_report.md).
