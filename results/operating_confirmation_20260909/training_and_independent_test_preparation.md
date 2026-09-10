# Vorbereitung der neuen Aufnahmen und des unveränderten Methodenvergleichs

GPIO18-Steuerung und ADXL345-Befestigung an einer Ecke des Lüfterrahmens sind
festgelegt. Der erste normale Betriebspunkt beträgt 25 % PWM. Eine Drehzahl ist
nicht gemessen. Die geplanten sechs Trainings- und zwei Validierungsaufnahmen
mit jeweils 60 s beginnen erst nach Freigabe der Messparameter anhand der Piloten.
Bis dahin bleibt `measurement_chain_verified` falsch; Modelle werden nicht trainiert.

Das Begleitdokument `training_and_independent_test_preparation.json` enthält
bewusst keine ausführbare Testfreigabe und keine erfundenen Modellhashes,
Schwellen, Drehzahlen oder zweiten PWM-Werte.

Für die spätere Aufnahmesequenz wird ein FanPWM-Kontext über alle acht Aufnahmen
gehalten. Die Erfassung setzt selbst keine PWM. Vor und nach jeder Aufnahme
werden unveränderte Vorgabe und Pin-Funktion geprüft. Metadaten werden vor dem
Aufnahmebeginn um tatsächliche Agenten-Steuerquelle, Controljournal,
Parameterentscheid samt Hash und Zustandsbestätigung ergänzt; abgeschlossene
Rohsidecars werden dafür nicht nachträglich umgeschrieben. Die CLI benennt die
PWM-Quelle bislang fest als `operator_documented_external_setting`; für die
Agentensteuerung ist deshalb ein Recorder-Wrapper vor der Aufnahme vorgesehen.

`--train-only` greift nicht auf Sensor oder Lüfter zu, prüft die gespeicherten
Aufnahmen jedoch erneut. Ein automatisches Gate auf den physikalischen
Parameterentscheid ist dort derzeit nicht implementiert; der Arbeitsablauf
verhindert den Aufruf bis zur dokumentierten Freigabe. Ein bloßer Profilboolean
ersetzt keinen Messbeleg.

Das gemeinsame Bundle wird erst aus dem neu geprüften Profil erstellt und vor
unabhängigen Tests gehasht. RMS, Isolation Forest und Float32-TFLite erhalten
dieselben XYZ-Fenster und dieselbe ausschließlich trainingsbasierte Skalierung.
Alle Schwellen folgen derselben linearen P99-Regel auf normaler Validierung.
Die Validierung dient beim Autoencoder zusätzlich Early Stopping; dies bleibt
eine methodische Einschränkung gegenüber einem gesonderten Kalibrierungssplit.

Für den zweiten normalen Betriebspunkt bleibt exakt dieses Bundle erhalten:
kein neues Modell, kein neuer Scaler, keine veränderte Schwelle. Dessen konkreter
PWM-Wert sowie Art, Rücksetzung und Reihenfolge der unabhängigen Anomalieversuche
werden vor der Testphase festgelegt. Ganze Aufnahmen werden getrennt zugeordnet;
aufeinanderfolgende Fenster ersetzen keine unabhängigen Versuchsreplikate.
