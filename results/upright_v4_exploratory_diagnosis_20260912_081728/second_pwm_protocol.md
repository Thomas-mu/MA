# Vorbereitetes Protokoll: zweiter NORMAL-Betriebspunkt bei 50 % PWM

Status: **vorbereitet, nicht gestartet; ausführbarer Adapter noch erforderlich**. Dieses Dokument ist keine Startfreigabe. Keine aktuelle PWM-Einstellung wurde ausgelesen oder verändert. Die letzte frühere Abschlussprüfung meldete 0 %; ein heutiger mechanischer Zustand wird daraus nicht abgeleitet.

## Fragestellung und begründeter Stellwert

Die aktuelle Wordfassung fordert mit **FF4, H3 und A10** einen zweiten normalen Betriebspunkt bei unveränderter Pipeline und einen Vergleich der Fehlalarmraten; sie gibt keinen konkreten Tastgrad vor. Quelle ist die unveränderte [Worddatei](../../docs/Akz_Masterarbeit_Bericht(3).docx), relevante Absätze stehen in [requirements_extract.txt](requirements_extract.txt). H3 ist eine zu prüfende Erwartung höherer Fehlalarmraten, kein zu erzwingendes Ergebnis.

Vorgeschlagen werden **50 % bei 25 kHz**: 25 Prozentpunkte beziehungsweise ein Drittel weniger Tastgrad als 75 %, keine Ableitung aus der früheren unklaren Angabe „halbiert“. Der Unterschied ist ausreichend deutlich als gezielt veränderte Stellbedingung. Die frühere geringe Stillstands-/Betriebstrennung bei 25 % spricht gegen 25 % als ersten zusätzlichen Prüfwert; alte 50-%-Messungen anderer Montageversionen belegen aber weder Signalqualität noch Drehzahl für v4. Eine geringere oder höhere Fehlalarmrate bei 50 % bleibt gleichermaßen ein gültiges Ergebnis. Der Wert wurde nicht anhand noch unbekannter 50-%-Modellscores ausgewählt.

Ein Tastgradvergleich ist ohne Drehzahlmessung kein nachgewiesener Vergleich zweier konkreter Drehzahlen. Ein separater Tachonachweis fehlt; GPIO18 ist der PWM-Ausgang, kein bestätigter Tachoeingang. Diese Einschränkung wird dokumentiert und blockiert nicht die Auswertung aller anderen Nachweise.

## Unveränderter Versuchsvertrag

| Merkmal | Vorgabe |
|---|---|
| Aufbau | `fan_upright_position_v4_20260911_103726`, aufrecht, unveränderte Sensorbefestigung und Lüfterposition |
| Zustand | ohne Platte; `state=normal`, `label=0`, `condition=normal_pwm50` |
| PWM | 50 %, 25 kHz; Periode 40.000 ns, Impulsdauer 20.000 ns; bestehende Hardware-PWM GPIO18 / physischer Pin 12 |
| Umfang | drei separate Starts, je 300 s, `normal_pwm50_01`, `_02`, `_03` |
| Vor jedem Start | aktuelle Freigabe und bestätigter Stillstand bei angeschlossener Versorgung; anschließend 60 s zusätzliche Auszeit |
| Sensor | nominell 200 Hz, ±2 g, volle Auflösung, FIFO-Stream, 0,0039 g/LSB, I²C-Bus 1 / konfigurierte 100 kHz |
| Aufzeichnung | vollständiger Anlauf möglichst ab Stellbefehlsaufruf; tatsächlicher erster XYZ-Punkt und Befehlsdauer protokollieren |
| Primärer Testabschnitt | unverändert `[180,300)` s seit Aufruf des 50-%-Befehls |
| Modellfenster | 128 XYZ, Schrittweite 128, keine Überlappung, erstes Fenster ab erstem XYZ mit Zeit ≥180 s, keine Grenzüberbrückung |
| Vorverarbeitung | Original-Float64, F-Anordnung für identische Reduktion, Achsenmittelwert je Fenster entfernen, Float32, gespeicherter Scaler |
| Modellpaket | `results/upright_v4_training_pilot_20260911_130614/run_001/frozen/pilot_bundle.json` |
| Pakethash | `cec1859bfb354bafef77a619e6d2c1ffd85b50787c87595aba9a1e20a80cdae5` |
| Schwellen RMS / IF / AE | 1,2747695377144315 / 0,5045395247064507 / 0,544357966122261 |
| Ende und Fehlerpfad | nach jedem Lauf 0 % einstellen und zurücklesen; mechanischen Stillstand nicht daraus ableiten; keine automatischen Wiederholungsstarts |

180 s bleiben auch für 50 % ein ungeprüfter Einlaufkandidat. Ein nachträgliches Verschieben auf einen günstigeren Abschnitt ist ausgeschlossen. Zusätzliche 5-s-Diagnostik darf den vollständigen Verlauf beschreiben, aber die primäre Modellauswahl nicht ändern. Totale Auszeiten, Versorgungstrennungen und zusätzliche Auszeit sind getrennte Angaben; es werden keine identischen gesamten Abkühlzeiten behauptet.

## Vor Messbeginn noch notwendige Softwarearbeit

Die existierenden Runner und Testleser sind absichtlich fest auf **75 %** beziehungsweise 30.000 ns Impulsdauer geprüft. Sie dürfen nicht durch bloßes Ändern eines JSON-Werts oder Umbenennen einer CSV für 50 % verwendet werden. Erforderlich ist ein **neuer separater Aufnahme-/Testadapter** für das neue Protokoll. Das eingefrorene Modellpaket, bestehende Testreader und frühere Protokolle bleiben unverändert. Die vorhandenen `build_windows`, `center_raw_window`, `standardize_ac` und Modell-Scorer werden unverändert wiederverwendet.

Vor dem Einfrieren des neuen ausführbaren Protokolls sind mindestens zu prüfen: nur explizit geplante 50 % zulässig; falsche PWM-Rücklesung/Pin-Funktion verhindert den Start; genau ein Versuch je Aufnahme-ID; frische phasenbezogene Freigabe; Fehler-Rückstellung auf 0 % ohne Neustart; Label stets NORMAL; neue Quellen dürfen in keinem früheren Trainings-/Validierungs-/Testbestand vorkommen; gleiche Originalfenster erzeugen exakt gleiche Eingaben und Entscheidungen wie der bisherige 75-%-Testweg; Qualitätsfehler ergeben INVALID und keine normalen Entscheidungen. Diese Tests werden ohne echte Hardware ausgeführt. Danach erst werden Adapterhash, Quellen-Ausschlussinventar, Modelle und Auswertungsvertrag eingefroren.

Das Paketmanifest enthält weiterhin den originalen Modellvertrag und seine Entwicklungshinweise. Die bereits enthaltene Regel für den zweiten PWM-Wert verlangt gerade keine Veränderung von Modell, Scaler, Schwellen oder Vorverarbeitung. Nur der externe Aufnahme-/Testvertrag beschreibt den neuen Stellwert und das NORMAL-Label.

## Speicherung, Qualität und Fehlerbehandlung

Neue Roh-CSV, Metadaten, Sitzungs-/Steuerungsjournal und Ergebnisdateien erhalten eigene Zeitstempel und IDs. Verknüpft werden Aufnahme-, Aufbau-, Paket-, Scaler-, Code-, Protokoll- und Dateihashes. Alle Messpunkte einschließlich Anlauf, Qualitätsfehler und Endreste bleiben erhalten. Metadaten enthalten Soll-PWM und Rücklesung getrennt, keine erfundene Drehzahl.

Die bisherigen Qualitätsregeln bleiben unverändert: Originalzeitstempel monoton und konsistent, mindestens 299,8 s zwischen erster und letzter Probe, erster XYZ-Punkt weniger als 1 s nach Befehlsaufruf. Strukturelle Fehler machen die Quelle nicht auswertbar; Rohdaten und Fehlerjournal bleiben erhalten. Betroffene Fenster sind bei Gap, Overrun, Sättigung, FIFO-Vollstand, Host-Abstand >160 ms, Rohbereichsgrenze oder nichtendlichen Daten ungültig. Abstände >10 ms werden berichtet, sind für sich aber kein Verlustnachweis. Exakte physische Verluste bleiben `unknown`, sofern nicht unabhängig bestimmt. Ein unvollständiger Lauf wird dokumentiert und nicht stillschweigend ersetzt.

Ohne bestätigten mechanischen Betrieb darf ein gesetzter 50-%-Wert nicht als tatsächlicher normaler Drehzustand ausgegeben werden. Falls der Nutzer nach dem Versuch einen ausgebliebenen Start oder eine physische Abweichung berichtet, wird diese Angabe getrennt ergänzt und die Zustandszuordnung als unbestätigt beziehungsweise abweichend gekennzeichnet. Keine Antwortfristen oder zusätzlichen automatischen Starts.

## Vorab festgelegte Auswertung

Je Methode und vollständigem Lauf: versuchte, gültige und ungültige Fenster; Fehlalarme und Fehlalarmrate unter gültigen NORMAL-Fenstern; Scoreverlauf mit eingefrorener Schwelle; aufnahmebezogene Zeit-/Qualitätskennwerte. Modellfehler sind je Methode gesondert INVALID. Gemeinsame Erfassungsfehler treffen alle drei Methoden auf denselben Fenstern. Zusätzlich gepoolte Zählwerte über die drei Läufe, ohne die Einzelergebnisse zu verdecken. Keine Recall-, Precision- oder F1-Aussage aus diesen reinen Normaldaten. Keine Erfolgsgrenze, die anschließend anhand der beobachteten Rate angepasst wird.

Vergleichsbestand bei 75 % sind **alle sechs bereits vorhandenen unabhängigen normalen v4-Testaufnahmen** des eingefrorenen Pakets: `normal_test_01–03`, `normal_sep11` sowie `normal_before` und `normal_after` der Folge vom 12.09. Training und Kalibrierungsvalidierung gehören nicht in diesen Testnenner. Aufnahme-IDs und Hashes stehen in [source_inventory.json](source_inventory.json). Die früheren Normaltests hatten je 194 gültige Fenster; zusammen RMS 60/1.164, IF 35/1.164, AE 64/1.164 Fehlalarme. Die Werte werden bei Vorbereitung des ausführbaren Protokolls noch einmal aus den unveränderten Quellen geprüft, nicht neu kalibriert.

Jeder 50-%-Lauf wird neben jedem 75-%-Lauf und den vorab festgelegten gepoolten Beständen berichtet. Es gibt keine zufällige Verteilung benachbarter Fenster, keinen Signifikanztest mit Fenstern als unabhängigen Replikaten und keine nachträgliche Auswahl besonders günstiger 75-%-Referenzen. Da die Aufnahmen zeitlich getrennt sind, beschreibt eine Ratendifferenz zunächst Betriebspunkt- und Zeitbedingungen zusammen. Eine isolierte PWM-Kausalwirkung verlangt einen gesonderten zeitnahen, kontrollierten Vergleich; ein solcher wird nicht automatisch angehängt.

## Kleinster sinnvoller nächster Versuch und Bedienung

Nach fertigem und geprüftem Softwareadapter ist **ein einzelner freigegebener 300-s-Normallauf bei 50 % plus 60 s zusätzliche Auszeit** der kleinste sinnvolle erste Schritt. Er liefert einen echten unabhängigen Normaltest und prüft den neuen Aufnahmevertrag. Er allein belegt keine Wiederholbarkeit; die beiden weiteren bereits geplanten Starts ergänzen diesen Nachweis ohne Änderung des Protokolls. Der Versuch wird nicht wegen schlechter Fehlalarmraten verworfen oder angepasst.

Der Nutzer muss keinen Aufbau ändern: Platte außerhalb des Luftstroms lassen, v4-Aufstellung und Sensorbefestigung unverändert lassen. Zum später vereinbarten Beginn werden angeschlossene Versorgung, Stillstand und Bereitschaft für genau einen Start bestätigt. Zwischen den Starts folgt nach 0-%-Rücklesung die freiwillige Nachricht „Lüfter steht, nächster Lauf freigegeben“. Keine wiederholten Rückfragen während der Aufnahme. Nach dem letzten Lauf endet die Folge bei zurückgelesenen 0 %. In diesem Auftrag wird keine dieser Freigaben angefordert und keine Messung begonnen.
