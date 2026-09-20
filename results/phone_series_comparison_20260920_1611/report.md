# Smartphoneversuch: zehn Anrufe

Geplant: zehn Versuche; vollständig und eindeutig markiert: 10/10. Aufnahmestatus: completed.
Profil: standlauf_pwm75_200hz; PWM-Konfiguration: `{"percent": 75, "frequency_hz": 25000, "period_ns": 40000, "duty_cycle_ns": 30000, "enable": 1, "gpio_bcm": 18, "hold_all_phases": true, "change_after_start": false}`. Einlaufzeit: 30 s. Beobachtungsdauer gespeicherter Samples: 1114.808 s.
Die Serie ist eine wiederholte Untersuchung am unveränderten Aufbau mit Google Pixel 9a. Die Konfiguration und die vollständige Aufnahme einschließlich Modellversionen sind unter source archiviert.

Die Chatmarker begrenzen Suchbereiche; Vibrationsbeginn und -ende wurden nicht separat gemessen. Nur vollständig enthaltene Fenster gehen in den primären Vergleich ein. Randfenster sind separat unklar. Ein bestehender Alarm ist keine neue Reaktion: Ein neuer Alarm erfordert ein direkt vorheriges gültiges, lückenlos anschließendes NORMAL-Fenster. Zeitabstände beruhen auf gespeicherten Host-Empfangszeiten, nicht auf Live-Ausgabezeiten.
Modelle, Skalierung, 128/128-Fenster und Schwellen bleiben unverändert. Alle Verfahren erhalten dieselben Rohfenster. Technisch ungültige Fenster und fehlende Versuche bleiben sichtbar. Es wurden keine künstlichen Vibrationsdauern oder verfahrensabhängigen Vergleichslabels erzeugt.

| Verfahren | Erstes Alarmfenster (Versuche/10) | Neuer Alarm (Versuche/10) | Normal: Alarmfenster/gültige Fenster | Normaler Alarmfensteranteil | Normale Beobachtung [s] |
|---|---:|---:|---:|---:|---:|
| RMS | 10/10 | 10/10 | 0/783 | 0.0% | 490.323 |
| Isolation Forest | 10/10 | 10/10 | 0/783 | 0.0% | 490.323 |
| Autoencoder | 10/10 | 10/10 | 0/783 | 0.0% | 490.323 |

| Versuch | Verfahren | Erstes Alarmfenster | Erstes neues Alarmfenster | Rang neuer Alarm | Befund / Unklarheiten |
|---|---|---:|---:|---:|---|
| Versuch 1 | RMS | 250 | 250 | 2 (Gleichstand) | new_alarm_found;  |
| Versuch 1 | Isolation Forest | 250 | 250 | 2 (Gleichstand) | new_alarm_found;  |
| Versuch 1 | Autoencoder | 249 | 249 | 1 | new_alarm_found;  |
| Versuch 2 | RMS | 444 | 444 | 3 | new_alarm_found;  |
| Versuch 2 | Isolation Forest | 440 | 440 | 2 | new_alarm_found;  |
| Versuch 2 | Autoencoder | 439 | 439 | 1 | new_alarm_found;  |
| Versuch 3 | RMS | 575 | 575 | 2 (Gleichstand) | new_alarm_found;  |
| Versuch 3 | Isolation Forest | 575 | 575 | 2 (Gleichstand) | new_alarm_found;  |
| Versuch 3 | Autoencoder | 574 | 574 | 1 | new_alarm_found;  |
| Versuch 4 | RMS | 702 | 702 | 2 (Gleichstand) | new_alarm_found;  |
| Versuch 4 | Isolation Forest | 702 | 702 | 2 (Gleichstand) | new_alarm_found;  |
| Versuch 4 | Autoencoder | 701 | 701 | 1 | new_alarm_found;  |
| Versuch 5 | RMS | 875 | 875 | 2 (Gleichstand) | new_alarm_found;  |
| Versuch 5 | Isolation Forest | 875 | 875 | 2 (Gleichstand) | new_alarm_found;  |
| Versuch 5 | Autoencoder | 874 | 874 | 1 | new_alarm_found;  |
| Versuch 6 | RMS | 1045 | 1045 | 2 (Gleichstand) | new_alarm_found;  |
| Versuch 6 | Isolation Forest | 1045 | 1045 | 2 (Gleichstand) | new_alarm_found;  |
| Versuch 6 | Autoencoder | 1044 | 1044 | 1 | new_alarm_found;  |
| Versuch 7 | RMS | 1186 | 1186 | 1 (Gleichstand) | new_alarm_found;  |
| Versuch 7 | Isolation Forest | 1186 | 1186 | 1 (Gleichstand) | new_alarm_found;  |
| Versuch 7 | Autoencoder | 1186 | 1186 | 1 (Gleichstand) | new_alarm_found;  |
| Versuch 8 | RMS | 1366 | 1366 | 1 (Gleichstand) | new_alarm_found;  |
| Versuch 8 | Isolation Forest | 1366 | 1366 | 1 (Gleichstand) | new_alarm_found;  |
| Versuch 8 | Autoencoder | 1366 | 1366 | 1 (Gleichstand) | new_alarm_found;  |
| Versuch 9 | RMS | 1526 | 1526 | 1 (Gleichstand) | new_alarm_found;  |
| Versuch 9 | Isolation Forest | 1526 | 1526 | 1 (Gleichstand) | new_alarm_found;  |
| Versuch 9 | Autoencoder | 1526 | 1526 | 1 (Gleichstand) | new_alarm_found;  |
| Versuch 10 | RMS | 1725 | 1725 | 2 (Gleichstand) | new_alarm_found;  |
| Versuch 10 | Isolation Forest | 1725 | 1725 | 2 (Gleichstand) | new_alarm_found;  |
| Versuch 10 | Autoencoder | 1724 | 1724 | 1 | new_alarm_found;  |

Alarmfensteranteile werden auf gültige vollständig enthaltene Fenster bezogen. Die CSV-Dateien nennen zusätzlich ungültige Fenster und Randfenster sowie Suchbereichs- und Beobachtungsdauern. Unterschiedlich lange Suchbereiche werden nicht allein anhand der Alarmanzahl verglichen. Es wird keine allgemeine Überlegenheit eines Verfahrens abgeleitet.

Der separate Benchmark enthält je Verfahren und Runde 20 Warm-up-Fenster, identische gespeicherte gültige Fenster und wechselnde Methodenreihenfolgen; Median und P95 stehen in processing_benchmark.json. Dies ist Rechenzeit auf dem Raspberry Pi, keine Live-Reaktionszeit.

Reproduktion (neuer Ausgabeordner erforderlich):

```sh
python /home/malik/masterarbeit-edge-ai/results/phone_series_comparison_20260920_1611/analyze_phone_series.py --run /home/malik/masterarbeit-edge-ai/results/phone_series_comparison_20260920_1611/source --output NEUER_ERGEBNISORDNER --runtime litert --threads 1 --benchmark
```


| Verfahren | Gemessene Fenster | Median [ms] | P95 [ms] |
|---|---:|---:|---:|
| RMS | 10824 | 0.032500 | 0.035463 |
| Isolation Forest | 10824 | 12.970697 | 14.523543 |
| Autoencoder | 10824 | 0.057537 | 0.062148 |