# Kontrollierte Messfolge – Stand nach zwei Betriebspiloten

**Aktualisierung nach Steuerungsübernahme:** Der Nutzer hat den Lüfter selbst
mit GPIO18 High gestartet und die frühere Stillstandsbedingung aufgehoben.
Er hat den Agenten anschließend zur Softwaresteuerung autorisiert. Nach
Ankündigung hat der Agent den vorhandenen Hardware-PWM-Kanal auf 0 % bei
25 kHz gestellt und GPIO18 auf `a3` zurückgesetzt. Die zehnsekündige Auslaufphase
ist abgeschlossen; der Nutzer hat vollständigen Stillstand visuell bestätigt.
Der Nutzer hat GPIO18 abschließend als Steueranschluss und den ADXL345 mit
vorgesehener I²C-Beschaltung an einer Ecke des Lüfterrahmens bestätigt. Diese
Hardwarepunkte sind geklärt und werden nicht erneut als Aufbau-TODO geführt. Die folgenden Ansagen zur Zuständigkeit sind
deshalb wie folgt konkretisiert: **Der Agent gibt sämtliche Steuerbefehle ein;
der Nutzer bestätigt nur Zustände und liefert fehlende Angaben.**
Der Nutzer hat den nächsten Betriebs-PWM-Wert ausdrücklich auf **25 %** festgelegt. Ein erneuter Steuerungsauftrag
oder eine erneute Erlaubnis zu den bereits autorisierten Schritten ist nicht nötig.
Vollständige Zeit-/Befehlsbelege liegen im Steuerjournal unter
`results/fan_control_20260909/`.

Stand 09.09.2026. Planwerte und inzwischen erhobene Pilotbelege werden getrennt geführt. Die Hardware
ist aufgebaut; GPIO18-Steuerung und Sensorbefestigung am Lüfterrahmen sind
festgelegt. Der aktuelle Auftrag setzt Softwareprüfung und Wordbearbeitung fort.
Die neue 30-s-Stillstandsaufnahme ist inzwischen abgeschlossen und technisch
ausgewertet. Nach Bereitschaftsbestätigung wurde D₁ = 25 % eingestellt; die
Betriebsaufnahme ist nach bestätigtem gleichmäßigem Lauf abgeschlossen.
Nach einer zweiten 30-s-Betriebsaufnahme bei unveränderten 25 % wurde erneut
0 % eingestellt. Vor S₁ fehlt eine neue Sichtbestätigung des vollständigen
Stillstands. Die geringe Signaltrennung im ersten Paar ergibt noch keine
Trainingsfreigabe; der Messparameterentscheid berücksichtigt Wiederholung und S₁.

## Voraussetzungen und Kommunikation

Vor jeder Messphase werden laufende Erfassungs-/Steuerungsprozesse, offene
Geräte und PWM-/Pinzustand erneut geprüft. Keine parallele Dokumentkonvertierung,
Modellbildung oder Ressourcenmessung während der Sensoraufnahme. Aufnahmen
verwenden neue Pfade unter `data/controlled_20260909/`; Analysen erhalten neue
Unterordner in `results/continuation_20260909/`. Bestehende Protokolle bleiben
unverändert. Eine heutige Nutzerangabe wird separat datiert, nicht in historische
Messjournale eingesetzt.

Die nächste Ansage lautet: **Lüfter soll AUS sein; Stellvorgabe 0 % bei 25 kHz;
vollständiger Stillstand ist nach dem zwischenzeitlichen Betrieb noch neu
visuell zu bestätigen; der Aufbau ist geklärt.
Der Beginn der 30-s-Aufnahme wird ausdrücklich angekündigt. Währenddessen
nichts berühren.** Die zuvor gespeicherten 25 % bei 25 kHz waren lediglich ein
ausgelesener PWM-Subsystemzustand. GPIO18 ist jetzt wieder der PWM zugeordnet.
Versorgung,
Signal am Pin und tatsächlicher Stillstand müssen davon getrennt bestätigt werden.

Vor der Betriebsmessung lautet die Ansage: **Lüfter AN bei D₁ = 25 %. Der Agent stellt diesen Wert am vorhandenen Hardware-PWM-Kanal ein.
Montage und Vorgabe danach unverändert lassen. Aufnahme beginnt nach der
angekündigten Einlaufphase und Startmeldung.** Vor diesem Schritt wird die Bereitschaft für die angekündigte
Betriebsmessung bestätigt; die Hardwarezuordnung ist bereits geklärt. Die Einlaufphase beträgt zunächst 30 s. Die neu gewählten
25 % belegen keinen früheren Betriebspunkt; historische 25/50 % dürfen nicht aus
Profilnamen als tatsächliche Werte abgeleitet werden.
Die Abschaltdemonstration `live_tflite_fan_control.py` ist hierfür ungeeignet:
Ihr RUN-Zustand ist 100 %, und Detektionsentscheidungen könnten den Zustand ändern.

## Montage- und Bedingungsprotokoll

Als feste Randbedingungen gelten GPIO18 als Lüftersteuerung und der ADXL345 mit
vorgesehener I²C-Beschaltung an einer Ecke des Lüfterrahmens. Die Montagekennung
`fan_frame_corner_adxl345_gpio18_v1` verweist auf diese bestätigte Beschreibung;
sie benennt keine nicht mitgeteilte Ecke oder Achsausrichtung. Künftige Journale
übernehmen diese Beschreibung und die zugehörige Nutzerbestätigung. Zusätzliche
nicht übermittelte Konstruktionsdetails werden nicht erfunden und führen nicht
zu einer erneuten Rückfrage zu den beiden abgeschlossenen Hardwarepunkten.
Eine frühere Ausschaltangabe belegt keine damalige Auslaufzeit.
Berührung, Fremdschwingung oder Zustandswechsel während eines Piloten führen
zu einer dokumentierten Wiederholung unter neuem Dateinamen.

## Messfolge und Zuordnung vor Aufnahme

| Phase | Zustand / Zweck | Geplanter Umfang | Freigabebedingung |
|---|---|---|---|
| S₀ | vollständiger Stillstand; `pilot`, Label −1 | 30 s abgeschlossen; 6.193 Werte | Neue Aufnahme standstill_20260909_200838.csv; keine gesetzten Qualitätsflags |
| B₁ | normaler Lauf bei D₁; `pilot`, Label 0 | 30 s nach zunächst 30 s Einlaufzeit | Lauf und unveränderte Montage bestätigt; 30 s abgeschlossen, 6.205 Werte ohne gesetzte Qualitätsflags |
| B₁-Wiederholung | derselbe Betriebspunkt 25 %; `pilot` | 30 s abgeschlossen; 6.205 Werte | Keine gesetzten Qualitätsflags, anschließend angekündigt 0 % eingestellt |
| S₁ | erneuter vollständiger Stillstand; `pilot` | 30 s vorgesehen | Neue Sichtbestätigung nach Abschaltung noch ausstehend; keine Aufnahme gestartet |
| T₁–T₆ | Normalbetrieb D₁; `training` | Vorschlag: 6 vollständige Aufnahmen à 60 s | Messparameter mit Pilotbelegen festgelegt |
| V₁–V₂ | Normalbetrieb D₁; `validation` | Vorschlag: 2 weitere Aufnahmen à 60 s | Zuordnung vor Aufnahme; keine Überschneidung mit Training |
| N₁ / N₂ | Normalbetrieb D₁ / D₂; `test` | Vorschlag: je 5 getrennte Aufnahmen à 60 s | gemeinsames Bundle und Testprotokoll vorab eingefroren |
| Aⱼ | konkret hergestellter, rücksetzbarer Anomaliezustand j; `test` | Vorschlag: je 5 getrennte Aufnahmen à 60 s | Art, Zustandsherstellung und Rücksetzung vorab festgelegt |

Umfang und Einlaufzeit sind Planwerte, keine bewiesene Stabilität oder statistische
Fallzahlplanung. Kontinuierlich nacheinander gespeicherte Trainingsdateien sind
getrennte Aufnahmen, aber keine unabhängig neu hergestellten Prüfstandzustände.
Für unabhängige Testwiederholungen werden Zustand und Einlaufphase jeweils neu
protokolliert, ohne den Sensor neu zu montieren. Fensterzahl ersetzt keine
Wiederholungszahl. Anomalien werden nicht spontan durch Eingriffe an rotierenden
Teilen erzeugt; die konkrete vorhandene Möglichkeit ist vor dieser Phase zu klären.

## Pilotparameter und Auswertung

200 Hz ODR, Full Resolution und ±2 g sind zunächst technische Pilotparameter
der vorhandenen 100-kHz-I²C-Messkette. Die FIFO-Erfassung und Registerrücklesung
werden verwendet. Jeder Pilot erhält Zeitstempel, Sampleindizes, Gap-/Overrun-/
Sättigungsflags, Quellcodehashes und CSV-/JSON-Prüfsummen. Die Stillstandsreferenz
ist keine Normaltrainingsaufnahme für den laufenden Lüfter.

Ausgewertet werden alle Achsen: Mittelwert, AC-RMS, Wertebereich, Wiederholungsquote,
beobachteter FIFO-Durchsatz, Hostintervallverteilung, maximale FIFO-Füllung und
gesetzte Qualitätsflags. Für die Frequenzanalyse dienen 512 Samples, 50 %
Überlappung, Hann-Fenster und Mittelwertentfernung je Segment als Startwerte.
Eine zweite Segmentlänge kann im Pilot zur Beurteilung schmaler Peaks dienen;
spätere Testdaten dürfen die Parameterwahl nicht beeinflussen.

Für einen dokumentierten gemeinsamen Frequenzbereich wird die integrierte
Leistung im Betrieb P_B mit der Stillstandsleistung P_S verglichen.
10 log₁₀(P_B/P_S) heißt **Betriebs-/Stillstandsleistungsverhältnis**.
Nur unter der zusätzlichen Annahme additiver, unveränderter und unkorrelierter
Hintergrundanteile kann 10 log₁₀((P_B−P_S)/P_S) bei P_B>P_S als Schätzung
eines Überschuss-SNR angegeben werden. Stillstand enthält auch Fremdschwingungen
und ist kein isoliert gemessenes Sensoreigenrauschen. Bei P_B≤P_S wird kein
positiver Nutzsignalnachweis behauptet. Bandgrenzen und Annahmen stehen im Bericht.

Null gesetzte Lücken-/Überlauf-/Sättigungsflags und vollständig abgeschlossene,
endliche, fortlaufende Daten sind die vorhandenen konservativen Aufnahmekriterien.
Eine große Hostlücke unterhalb der FIFO-Kapazität ist noch kein exakter Verlustnachweis.
Keine Flags beweisen umgekehrt nicht exakt null verlorene physikalische Werte.
Der Anteil hoher Frequenzen ist eine Diagnose, kein Aliasingfreiheitsnachweis.
Drehfrequenz und Harmonische werden nur bei unabhängig bestätigter Drehzahl
zugeordnet. GPIO18 wird als Steueranschluss verwendet. Eine unabhängige Drehzahlmessung
ist nicht vorhanden; Drehzahl bleibt `null`. Daraus wird kein Hardwareumbau abgeleitet. Der Pi-Kühler wird nicht stellvertretend
gemessen. Zeitaufgelöste Tachozählungen sind einem übernommenen Einzelwert vorzuziehen.

## Entscheidung vor neuer Modellbildung

Ein eigener Parameterentscheid muss die Pilotpfade und Prüfsummen, Montage,
ODR, Bereich, betrachtetes Band, Segmentlänge, H/S, Aufnahmedauer und Akzeptanzgrenzen
enthalten. Zu begründen sind die Trennung von Stillstand/Betrieb, Sättigungsreserve,
Rate und Datenkontinuität sowie Frequenzanteile an der verfügbaren Bandgrenze.
Numerische SNR-/Driftgrenzen sind aktuell offen und müssen sachlich begründet
vor Training und Test festgelegt werden; sie werden nicht als bereits erfüllt
markiert. Falls 200 Hz das relevante Band nicht abdeckt oder keine belastbare
Signaltrennung vorliegt, bleibt A1 offen und die Modellbildung wartet.

H=S=128 ist die aktuelle, fest implementierte Modelleingabe. Bei nominell 200 Hz
folgen daraus 0,64 s Fensterintervall. Diese Rechengröße ist kein Eignungsnachweis.
Eine abweichende Pilotentscheidung erfordert zuerst eine konsistente Änderung
von Erfassung, Modellform, Vergleich und Livebetrieb; sie darf nicht allein in
Metadaten eingetragen werden. Die aktuelle Validierung steuert außerdem Early
Stopping und kalibriert P99. Ein zusätzlicher Kalibrierungssplit wäre eine vorab
zu implementierende Protokolländerung, nicht stillschweigend bereits vorhanden.

## Gemeinsamer Vergleich und unveränderter zweiter Betriebspunkt

Erst nach Pilotentscheidung neue Aufnahmen mit `calibrate_and_train.py --record-only`
erstellen, Qualität prüfen und das neue Profil anschließend mit `--train-only`
trainieren. Vorläufiger Umfang: `--recordings 8 --validation-recordings 2 --seconds 60`.
Montagekennung und D₁ = 25 % sind festgelegt; die endgültigen Messparameter
werden anhand der erhobenen Piloten und der noch ausstehenden Stillstandsreferenz S₁ begründet.
Kein Aufruf dieser Art wurde mit unbestätigten Bedingungen ausgeführt.

`common_comparison.py calibrate` erhält das neue geprüfte Profil. Alle Verfahren
verwenden dieselben XYZ-Fenster und trainingsbasierte Skalierung; RMS, negativer
IF-Normalitätsscore und Float32-TFLite-Rekonstruktionsfehler werden nach derselben
linearen P99-Regel kalibriert. Konvertierung und Entscheidungen sind am neuen
Modell erneut zu prüfen. Der Status `measurement_chain_verified` darf nur mit
dem abgelegten Parameterentscheid samt Pilotbelegen gesetzt werden. Dies ist
im bisherigen Training kein automatisch erbrachter Nutzband-/SNR-Nachweis.

Vor den Tests werden Modelle, Skalierung, sämtliche Schwellen, Quellcode und
Versuchsprotokoll gehasht. Das Testmanifest nennt genau dieses Bundle und die
neuen Aufnahmejournale. D₂ bleibt normale Klasse 0 und verwendet dasselbe
Bundle wie D₁: kein Nachtrainieren, keine neue Skalierung, keine Schwellenanpassung.
Ein separat trainiertes `fan_50` ersetzt diesen Versuch nicht. Die Reihenfolge
der Testzustände und Wiederholungen wird vorab festgelegt; bei Driftverdacht
ist eine abschließende Wiederholung von D₁ vorgesehen.

Ergebnisgrößen: Konfusionsmatrizen, Precision/Recall/F1/FPR insgesamt und je
Aufnahme/Zustand, ungültige Entscheidungen, Fristüberschreitungen, Erfassungslücken,
CPU und Prozess-RSS. H2 benötigt Live-Latenz ab vollständigem Fenster; Replay
allein genügt nicht. Wiederholungen und Unsicherheit werden auf Aufnahmeebene
betrachtet. Eine GUI-Lastprüfung benötigt eine nutzbare Desktop-Sitzung.
