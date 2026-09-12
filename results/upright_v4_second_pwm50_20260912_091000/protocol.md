# Vorab festgelegter zweiter NORMAL-Betriebspunkt für v4

Drei getrennte 300-s-Aufnahmen ohne Platte bei 50 % PWM und 25 kHz
(40000 ns Periode, 20000 ns Tastzeit), unveränderte v4-Montage und ADXL345-Konfiguration.
Das eingefrorene Paket wird vollständig unverändert verwendet. NORMAL, Label 0.
Bewertung ausschließlich [180,300) s seit Stellbefehl, 128 XYZ-Punkte je Fenster,
Schrittweite 128, keine Überlappung und keine Verbindung zwischen Aufnahmen.

Der Nutzer hat selbstständige Starts und Stopps ausdrücklich erlaubt. Die aktuelle
Anfangsbestätigung (ohne Platte, v4 unverändert, mechanisch still, Versorgung
angeschlossen) liegt noch nicht vor. Es wurde keine Freigabedatei erzeugt.

Nach der ersten Bestätigung mindestens 60 s zusätzliche Auszeit. Zwischen den
vorab autorisierten Starts wird 0 % eingestellt und zurückgelesen; danach mindestens
60 s zusätzliche Software-Auszeit. Das ersetzt keine Sicht- oder Tachobestätigung
des mechanischen Stillstands. Abweichung vom zunächst vorgesehenen manuellen
Freigabeablauf: automatische Fortsetzung gemäß der späteren Nutzeranweisung.
Gesamte Auszeiten separat aus den Zeitstempeln berichten; nicht als identisch behaupten.
Bei Fehler keine Wiederholung und kein weiterer Start. Bei einem Erfassungsfehler
führt der besitzende Steuerprozess nach Möglichkeit die geprüfte Nullstellung aus.

Alle sechs früheren unabhängigen normalen v4-Testaufnahmen bei 75 % bilden die
vorab festgelegte Vergleichsgruppe. Training und Validierung sind keine Testnenner.
Ein nicht zeitgleicher Vergleich isoliert keinen kausalen PWM-Effekt.

Qualitätsfehler bleiben erhalten. Ungültige Fenster zählen nicht als NORMAL.
Nominelle 200 Hz, beobachteter XYZ-Durchsatz, Host-Leseabstände und unbekannte genaue
physische Verluste getrennt ausweisen. Alle Rohdaten einschließlich Anlauf speichern.
Keine Schwellenanpassung, kein Nachtraining, keine nachträgliche Abschnittswahl.

Ausführung nach dokumentierter Anfangsbereitschaft:
`python src/run_second_pwm_sequence.py --protocol <dieses Verzeichnis>/protocol.json`.
Das Skript verlangt die passende `normal_pwm50_01_release.json`; eine fehlende
Antwort oder die Protokollvorbereitung erzeugt diese Datei nicht automatisch.

Die Softwaretests stehen im benachbarten Ergebnisverzeichnis
`upright_v4_runtime_adapter_20260912_090008`. Die JSON-Datei hält Quellen-,
Paket- und Ausschlusshashes fest. Neue Messungen wurden hier noch nicht ausgeführt.
