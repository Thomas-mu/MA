"""Write the final review handoff from verified document and evidence metadata."""
from pathlib import Path
from datetime import datetime, timezone
import json

B=Path(__file__).resolve().parent
v=json.loads((B/'manuscript_verification.json').read_text())
assert v['authorized_word_updated']
text=f'''# Abschluss der Berichtsüberarbeitung mit vorhandenen Daten

Stand: 13.09.2026. Neue Ergebnisse dieses Ordners sind Dokument- und Dateiprüfungen, keine neuen Messungen. Die empirische Datenbasis endet am 12.09.2026.

Die Fassung stellt die Untersuchung als begrenzte Pilotstudie dar. Der technische Methodenvergleich wurde realisiert und geprüft; eine zuverlässige Erkennung der untersuchten Luftstromänderung ist nicht belegt. Diese negative Erkenntnis bleibt erhalten. Die ursprünglichen Anforderungen und Hypothesen wurden nicht an die Ergebnisse angepasst. Insbesondere bleiben A1 und A11 nur teilweise nachgewiesen. Die fehlenden Nachweise sind dokumentiert, durch diese Überarbeitung jedoch nicht erbracht.

## Abgabefassung und Sicherung

- [Aktualisierte Worddatei](../../docs/Akz_Masterarbeit_Bericht(3).docx).
- [Geprüfte PDF-Lesefassung](thesis_pilot.pdf); {v['pdf_pages']} Seiten einschließlich Titel und Verzeichnissen.
- [Unveränderte Ausgangskopie](../../docs/backups/Akz_Masterarbeit_Bericht(3)_vor_pilotabschluss_20260913_064035.docx).
- [Dokumentierter Änderungsnachweis](word_changes.json) und [abschließende Erhaltungs-/Formatprüfung](manuscript_verification.json).

Die wissenschaftliche Angemessenheit einer begrenzten Pilotstudie ist von der vollständigen Erfüllung der ursprünglichen Aufgabenstellung zu unterscheiden. Ob dieser Umfang für die konkrete Prüfungsleistung genügt und welche Note er erhält, entscheiden die Prüfenden. Eine Fehlerfreiheit oder Note 1,0 wird nicht zugesichert.

## Ergebnis des unveränderten Modellpakets

Die eine unabhängige Folge Normal → Luftstrom verändert → Normal enthält je Aufnahme 194 gültige Modellfenster aus dem festgelegten Abschnitt [180,300) s. Die Fensterlänge beträgt 128 XYZ-Punkte. Die insgesamt 582 Fenster sind keine 582 unabhängigen Versuchsreplikate.

| Methode | Markierte veränderte Fenster | Normale Fehlalarme der Folge | F1 für das definierte Zustandslabel |
|---|---:|---:|---:|
| RMS auf standardisierten Werten | 7/194 | 1/388 | 6,93 % |
| Isolation Forest | 4/194 | 0/388 | 4,04 % |
| TFLite-Autoencoder | 0/194 | 55/388 | 0,00 % |

Der Autoencoder erzeugt davon 51 Fehlalarme in normal_before und vier in normal_after. Die explorative Fehleranalyse erklärt die Scores anhand der gespeicherten Achsenskalierung und geringerer X-/Y-Rekonstruktionsfehler im Plattenzustand. Höhere physische Z-Vibration führt deshalb nicht notwendig zu einem höheren standardisierten Modellscore. Der fehlende einzelne Schwellenübertritt wurde separat aus den gespeicherten Fensterentscheidungen geprüft; er wird nicht allein aus einem kleineren Gruppenmittelwert hergeleitet. Eine konkrete physikalische Ursache der Signaländerungen ist dadurch nicht kausal nachgewiesen.

H1 ist in dieser Folge nicht bestätigt. H2 ist für die gemessenen hostseitigen Verarbeitungsgrenzen erfüllt: P99 liegt in allen 18 Sensor-/Replay-Prozessen unter dem jeweiligen Fensterintervall, ohne gezählte Überschreitung. Die neun Sensorprozesse liegen bei P99 zwischen 6,113 und 28,577 ms; das Intervall beträgt etwa 618 ms. Dies ist weder ein unbegrenzter Dauerbetriebsnachweis noch eine harte Echtzeitgarantie.

Der zweite normale Betriebspunkt bei 50 % PWM wurde bereits unabhängig getestet. Die leicht höhere gepoolte Autoencoder-Fehlalarmrate von 6,01 % gegenüber 5,50 % bei 75 % beschreibt keine einheitliche Veränderung über alle Starts. RMS und Isolation Forest zeigen in diesem Vergleich niedrigere Anteile. H3 ist nicht pauschal bestätigt. Reihenfolge, Startvariation und weitere Einflüsse sind nicht kausal von der PWM getrennt.

## Durchgeführte Überarbeitung und Prüfung

- Zusammenfassung, zentrale FF-/H-Ergebnistabelle 7-10 und abgestimmtes Fazit ergänzt. Umgesetzte Funktionen, beobachtete Ergebnisse und unerbrachte Nachweise sind getrennt.
- Kapitel 1–5 gegen den tatsächlichen Abschluss eingeordnet. Die ursprünglich vorgesehene Drehzahlmessung bleibt sichtbar; eine PWM-Stellvorgabe wird nicht als Drehzahl behandelt.
- Die Doppelnutzung einer normalen Validierungsaufnahme für Epochenauswahl und Schwelle, die wirkliche Isolation-Forest-Scoredefinition und die Auswertungseinheit präzisiert.
- Alle 5.820 gespeicherten Methodenausgaben der zehn ursprünglichen Testaufnahmen nachgezählt; davon 5.238 normale Ausgaben auch gegen die zusammengefasste Tabelle geprüft. Zusätzlich 3.492 Laufzeitentscheidungen kontrolliert. Gültigkeit, Abschnittsauswahl, Fensterzuordnung, eingefrorene Schwellen und Quellenhashes sind konsistent. Es wurde keine neue Modellinferenz ausgeführt. Details: [Statistikaudit](statistical_audit.md).
- Sechs zentrale Originalstudien gezielt gegen ihre Volltexte geprüft. Bei 39 Literaturangaben wurde die Zuordnung zu Zitaten kontrolliert; dies ist keine vollständige Inhaltsprüfung aller 39 Quellen. Eine eigene kritische Einordnung ist deutlicher gekennzeichnet und eine bestätigte DOI ergänzt. Details: [Quellenprüfung](sources_review.md).
- Substantielle KI-Unterstützung in Text, Analyse und Code offengelegt. Die persönliche Eigenständigkeitserklärung wurde nicht unterschrieben oder stellvertretend bestätigt. Details: [Unterstützungs- und Autorenprüfnachweis](ki_unterstuetzung_und_autorenpruefung.md).
- {v['tables']} Tabellen einschließlich Abkürzungsverzeichnis, sechs bestehende Abbildungen, drei Formeln und {v['unique_captions']} eindeutige Beschriftungen geprüft. Inhalts-, Tabellen- und Abbildungsverzeichnis aktualisiert; Seitenangaben, Nummerierung und Seitenränder kontrolliert. Die gerenderten Seiten wurden visuell geprüft; kurze redundante Übergänge wurden zur Verbesserung des Umbruchs gekürzt.

Die Worddatei enthält nur registrierte Text- und Tabelleneingriffe. Ihre Ausgangsfassung ist gesichert. {v['protected_unchanged_files']:,} geschützte Bestandsdateien sind hashgleich erhalten geblieben, darunter Rohdaten, Modelle, Softwarequellen und historische Berichte. Es gab in diesem Abschlusslauf weder Hardwarezugriff oder PWM-Befehle noch neue Aufnahmen, Nachtraining, Skalierung oder Schwellenanpassung. Ein aktueller mechanischer Lüfterzustand wurde nicht ermittelt.

## Was weiterhin nicht nachgewiesen ist

| Offener Nachweis | Aussage mit vorhandenen Daten | Nur durch zusätzliche Erhebung schließbar |
|---|---|---|
| Wiederholbarkeit des veränderten Zustands | Eine unabhängige Plattenfolge; mehrere Normalstarts ersetzen keine positive Wiederholung. | Weitere vollständige unabhängige Folgen mit vorher festgelegtem Protokoll. Zwei vorbereitete Zusatzfolgen bleiben ungemessen und wären weiterhin ein kleiner Pilotumfang. |
| Tatsächliche Drehzahl | PWM-Stellvorgaben und Rücklesung dokumentiert; keine gemessene RPM. | Geeignete unabhängige Drehzahlmessung oder korrekt zugeordneter und geprüfter Tachoweg. |
| Physikalische Sensorzeitbasis | Nominelle 200 Hz und ungefähr 207 XYZ/s Host-Durchsatz getrennt dokumentiert. | Unabhängige Zeitreferenz für die Erfassung; unbekannte physische Verluste bleiben unbekannt. |
| Übertragbarkeit | Aussagen für diesen Aufbau, dieses Paket und die dokumentierten kurzen Versuche. | Neue unabhängige Daten für weitere Geräte, Montage-, Umgebungs- oder Defektbedingungen. |

Es ist nicht erforderlich, Ergebnisse durch Schwellenänderungen oder eine Umbenennung der Versuchsklasse günstiger erscheinen zu lassen. Eine neue Modellversion wäre eine Anschlussarbeit mit neuen unabhängigen Tests. Die optionale GUI-Integration ist kein nachträglich eingeführtes Abschlusskriterium des gemessenen Kernwegs.

## Deine verbleibende Vorbereitung zur Abgabe

1. Lies besonders Zusammenfassung, Abschnitte 7.4–7.8 und Kapitel 8–10. Prüfe, ob Beschreibung und Nutzerbeobachtungen deinen tatsächlich ausgeführten Aufbau wiedergeben und ob du die Schlussfolgerungen erklären kannst.
2. Gleiche den ausgewiesenen Pilotumfang einschließlich A1/A11 und fehlender Drehzahl mit der verbindlichen Aufgabenstellung bzw. Rückmeldung deiner Prüfenden ab. Diese Entscheidung kann die Software nicht ersetzen; die offenen Anforderungen werden im Bericht nicht verborgen.
3. Prüfe die für deinen Studiengang geltenden Regeln zur KI-Unterstützung anhand der tatsächlichen Nutzung. Der vorbereitete Nachweis ist keine institutionell genehmigte Erklärung und keine lückenlose Zuordnung sämtlicher älterer Textpassagen.
4. Kontrolliere persönliche Angaben, verbindlichen Abgabetermin und formale Vorgaben. Unterschreibe die Eigenständigkeitserklärung erst nach deiner eigenen Prüfung; eine Unterschrift wurde nicht erzeugt.

Für diesen dokumentarischen Abschluss ist kein Umbau und kein weiterer Lüfterstart vorgesehen. Die Prüfunterlagen erlauben eine nachvollziehbare persönliche Abschlusskontrolle; sie versprechen weder die vollständige Erfüllung aller ursprünglichen Nachweise noch eine bestimmte Bewertung.
'''
text=text.replace(f"{v['protected_unchanged_files']:,}",f"{v['protected_unchanged_files']:,}".replace(',','.'))
(B/'abschlussbericht.md').write_text(text)
print(str(B/'abschlussbericht.md'))
