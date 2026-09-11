# Zusätzlicher Normallauf ohne Plattenumbau

Aufbauversion: `fan_upright_position_v4_20260911_103726`. Neue, getrennte Aufnahme `normal_followup`; die abgeschlossene Normal–Platte–Normal-Folge bleibt unverändert.

Ziel: Prüfen, ob bei einem weiteren Normalstart ohne erneuten Plattenumbau das erhöhte Vibrationsniveau der Rückkehrreferenz erneut beobachtet wird. Eine einzelne Zusatzaufnahme ist keine allgemeine Reproduzierbarkeitsprüfung.

Freigabe: `normal_followup_release.json`. Mechanischer Stillstand war durch die vorausgehende Nutzernachricht bestätigt; der Nutzer wurde angewiesen, Platte entfernt, 12-V-Versorgung angeschlossen sowie Lüfter und Sensor unverändert zu lassen, und hat den konkret erläuterten Start anschließend ausdrücklich freigegeben. Keine neue unabhängige Sichtbeobachtung wird behauptet.

Geplant: 60 s zusätzliche Auszeit ab Annahme der Freigabe, dann einmalig 75 % PWM bei 25 kHz, möglichst unmittelbar 300 s Erfassung, anschließend 0 % und Rücklesen. Keine Antwortfrist, Laufbeobachtungsfrage oder automatische Wiederholung. Die tatsächliche zusätzliche Auszeit fiel wegen der Vorbereitung des getrennten Messordners etwas länger aus; ihr exakter Wert steht nach Abschluss in der Sitzung. Der Abstand zum vorherigen Nullbefehl wird separat berichtet und ist keine unabhängig gemessene mechanische oder thermische Auszeit.

Sensor unverändert: ADXL345, nominell 200 Hz, ±2 g, Full Resolution, FIFO-Stream, 0,0039 g/LSB, I²C-Bus 1, Adresse 0x53, konfiguriert 100 kHz. Die vollständig rückgelesene Konfiguration wird gegen die letzte v4-Normalreferenz geprüft.

Steuerung: bestehende Hardware-PWM an BCM GPIO18, physischer Pin 12, RP1 PWM0 Kanal 2, Funktion a3/PWM0_CHAN2, Periode 40.000 ns. Steuerbefehle und Rücklesungen werden protokolliert. Keine Drehzahlmessung und keine erkennungsabhängige Änderung.

Erfassung und Fehlerbehandlung verwenden eine Kopie des vorhandenen Einzelphasen-Runners. Die Änderungen betreffen die zusätzliche Prüfung gleicher Sensorkonfiguration, die Herkunft der vorangegangenen Nullzeit und die Abschlussmeldung. Die Freigabeprüfung ist auf genau diesen neuen Normallauf begrenzt; bestehende Sitzungs- oder Journaldateien verhindern einen weiteren Versuch. Bei Erfassungsfehlern wird im finally-Pfad nach Möglichkeit 0 % eingestellt und der tatsächlich rückgelesene Status gemeldet.

Auswertung: nominelle ODR und beobachteter XYZ-Durchsatz getrennt; Hostzeitstempel, Leseabstände, Softwareindices, Lücken-, Überlauf- und Sättigungsflags sowie Rohdatenhashes prüfen. Je 5-s-Abschnitt eigene XYZ-Achsenmittelwerte entfernen und Vektor-AC-RMS berechnen. Vollständigen Verlauf und unverändertes Prüffenster 180–300 s mit beiden vorherigen v4-Normalaufnahmen vergleichen. Zeitliche Trends innerhalb eines Laufs und Niveauunterschiede zwischen Starts getrennt ausweisen. Keine zufällige Verteilung benachbarter Fenster auf Daten-Splits.

Neue Ergebnisse werden ausschließlich hier und im zugehörigen neuen Datenordner gespeichert. Worddatei, Modelle und historische Dateien bleiben unverändert. Kein Training und kein zusätzlicher Plattenversuch.
