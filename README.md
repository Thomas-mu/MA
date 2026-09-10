# KI-basierte Anomalieerkennung auf ressourcenbeschränkter Edge-Hardware

Bestehender Prüfstand: Raspberry Pi 5, ADXL345, PWM-Lüfter.
Verglichen werden RMS, Isolation Forest und ein Float32-TFLite-Autoencoder.

Der aktuelle dokumentierte Arbeitsstand steht in
[docs/arbeitsstand_20260909.md](docs/arbeitsstand_20260909.md).
Die Masterarbeit [docs/Akz_Masterarbeit_Bericht(3).docx](docs/Akz_Masterarbeit_Bericht(3).docx)
enthält die Anforderungsgrundlage in Kapitel 1–5 und das ergänzte
Implementierungskapitel 6. Die Ausgangskopie liegt unter `docs/backups/`.
Der [kontrollierte Versuchsplan](docs/versuchsplan_kontrolliert_20260909.md)
trennt die noch ausstehenden Pilot-, Trainings-/Validierungs- und Testaufnahmen.
GPIO18 ist als Steueranschluss bestätigt; der ADXL345 ist mit vorgesehener
I²C-Beschaltung an einer Ecke des Lüfterrahmens befestigt. Diese Hardwarepunkte
sind geklärt. Die neue 30-s-Stillstandsaufnahme und zwei 30-s-Betriebsaufnahmen
bei 25 % PWM sind abgeschlossen. Nach angekündigter Abschaltung beträgt die
Vorgabe 0 %; vor der zweiten Stillstandsaufnahme ist vollständiger Stillstand
noch neu visuell zu bestätigen. Die geringe Signaltrennung ergibt noch keine
Trainingsfreigabe. Eine unabhängige Drehzahlmessung liegt nicht vor. Die
nachträgliche Ausschaltangabe macht frühere Aufnahmen nicht zu kontrollierten
Stillstandsreferenzen.

- [Softwaresteuerung, Pinzuordnung und ausgeführte Befehle](docs/steuerungsuebernahme_20260909.md)
- [Anforderungen, vorhandene Belege und Widersprüche](docs/anforderungsabgleich_20260909.md)
- [Messkette, FFT-Pilot und ausstehende Versuche](docs/messkette_und_versuche.md)
- [Gemeinsamer Methodenvergleich und Ressourcenmessung](docs/gemeinsamer_vergleich.md)
- [Neue Kalibrierungsaufnahmen](docs/kalibrierung.md)
- [Livebetrieb, Startbefehle und Messdefinitionen](docs/livebetrieb.md)

Auf dem geprüften Pi enthält `.venv` alle für die Softwareprüfungen benötigten
Pakete sowie den eigenständigen LiteRT-Interpreter. `.venv_tf` enthält TensorFlow,
aber zum Prüfzeitpunkt weder pytest noch den eigenständigen LiteRT-Interpreter.
Die vollständige Systemaufnahme liegt in
`results/verification_20260909/environment_initial.json`.

```bash
.venv/bin/python -m pytest -q tests
.venv/bin/python src/live_tflite_monitor.py --profile fan_25 --self-test
.venv/bin/python src/calibrate_and_train.py --profile neuer_fifo_pilot --dry-run
```

Diese drei Befehle greifen nicht auf Sensor oder Lüfter zu. Echte Aufnahmen
benötigen einen bestätigten und dokumentierten Prüfstandzustand. Die alte Angabe
500 Hz bezeichnet Softwareabfragen und belegt keine 500 neuen Sensorwerte/s.
Neue Erfassung verwendet standardmäßig 200-Hz-ODR und FIFO; vorhandene Profile
sind dafür nicht stillschweigend neu kalibriert. Manuelle Schwellen und eine
bewusst zugelassene Messratenabweichung bleiben gekennzeichnete Entwicklungsmodi.

Neue Ergebnisse liegen getrennt unter `results/verification_20260909/` und
`results/common_comparison_20260909/`. Vorhandene Dateien werden nicht überschrieben.
Unabhängige Testgüte, kontrollierter Betriebspunktwechsel, ausreichende Nutzbandbreite,
SNR, Drehzahlmessung und GUI-Zusatzlast sind noch nicht abschließend nachgewiesen.

Die Lüfterprogramme verwenden `src/fan_pwm.py` für den vorhandenen RP1-Hardware-
PWM-Kanal (`pwmchip0/pwm2`, GPIO18 = physischer Pin 12, Funktion `a3`, 25 kHz).
Das Modul prüft Zuordnung und Rücklesung und hält eine gemeinsame Prozesssperre.
`FanPWM` öffnet/schließt ohne Ausgangsänderung; seine Stellmethoden sind explizit.
Der Entwicklungsadapter `FanController` setzt dagegen beim Start seine Vorgabe
und fordert beim Beenden 0 % bei weiterhin aktivierter PWM an. Er ersetzt weder
die Sichtbestätigung des Stillstands noch eine Drehzahlmessung. Die Entwicklungs-
abschaltung wird für den Methodenvergleich nicht gestartet.
