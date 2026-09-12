# Dokumentprüfung der Abschlussfassung

Die Wordfassung basiert auf der vor der Bearbeitung gesicherten Datei `docs/backups/Akz_Masterarbeit_Bericht(3)_vor_abschluss_20260912_103145.docx`. Die Ausgangskopie bleibt unverändert. Kapitel 6–10, Anhang, Literaturverzeichnis und die Verzeichnisse wurden anhand der gespeicherten Projektbelege ergänzt beziehungsweise neu gesetzt.

## Inhalt und Erhaltung

- Haupttext und Tabellenwortlaut der Kapitel 1–5 stimmen nach Normalisierung von Leerraum mit der Ausgangskopie überein.
- Die drei mathematischen Ausdrücke stimmen nach kanonischem OMML-Vergleich von Operatoren, Wurzeln, Brüchen, Summengrenzen und Indizes überein. LibreOffice normalisiert Minuszeichen, Leerraum und Klammerdarstellungen; diese reinen Serialisierungsunterschiede werden nicht als Inhaltsänderung ausgegeben.
- 39 Literaturangaben wurden den bereits vorhandenen beziehungsweise ergänzten Zitaten zugeordnet; vollständige Einträge stehen in `bibliography.json`.
- Umsetzung, nachgewiesene Ergebnisse und teilweise/noch nicht erfüllte Anforderungen sind in getrennten Abschnitten und Tabelle 7-9 ausgewiesen. Der Status des eingefrorenen Pakets bleibt Entwicklungspilot.
- Die nachträgliche Nutzerangabe zum ausgeschalteten Lüfter im frühen Arbeitsdurchlauf wird mit ihrer historischen Unsicherheit erläutert. Frühere Aufnahmen werden dadurch nicht rückwirkend zu kontrollierten Stillstandsreferenzen.
- Datum und Unterschrift der persönlichen Erklärung bleiben für eine neue Prüfung durch den Autor frei. Die alte eingebettete Unterschrift ist nur in der gesicherten Ausgangskopie erhalten.

## Layout und korrigierte Befunde

Der finale PDF-Export besitzt 66 Seiten: Deckblatt ohne Seitenzahl, sechs römisch nummerierte Vorseiten und 59 fortlaufend arabisch nummerierte Haupt-/Anhang-/Literaturseiten. Die Hauptkapitel tragen 1–10. Anhang und Literaturverzeichnis sind unnummerierte Überschriften. Die drei Verzeichnisse sind aktualisierte Felder und keine manuell erfundenen Seitenangaben.

Alle sechs Kontaktübersichten wurden visuell geprüft. Zusätzlich wurden die drei Gleichungen, die wissenschaftlichen Ergebnisgrafiken sowie die Latenz-, Ressourcen- und Verwechslungszahlentabellen vergrößert geprüft. Es gibt 34 Tabellen einschließlich Abkürzungsverzeichnis, 33 eindeutige Tabellenbeschriftungen und sechs Abbildungsbeschriftungen. Tabellenköpfe wiederholen sich bei Seitenwechseln; Zeilen werden nicht mitten im Inhalt getrennt. Kein Text ragt über die geprüften Seitenränder. Alle 39 Seitenverweise der Beschriftungsverzeichnisse stimmen mit der tatsächlichen PDF-Seite überein.

Im ersten Export fehlten die Formeln wegen der nicht installierten LibreOffice-Math-Komponente. Die zwei zugehörigen Pakete wurden nach den Laufzeitprüfungen ergänzt, ohne bestehende Pakete zu aktualisieren. Der erneute Export stellt alle Formeln dar. Außerdem wurden die Reihenfolge der ersten zwei Abbildungsnummern und eine ungünstig umbrechende Tabellenüberschrift korrigiert. Die frühen Exporte bleiben als klar benannte Diagnosefassungen in `layout_first_export/` und `layout_second_export/` erhalten.

Die CPU-Grafik in der Wordfassung gewichtet die vollständigen dokumentierten Monitorintervalle nach Dauer in 1-s-Abschnitten. Die allererste CPU-Probe besitzt keinen protokollierten vorherigen Monitorzeitstempel; sie bleibt in den Rohdaten, wird aber nicht als bekanntes Zeitintervall in die Grafik eingerechnet. In einer IF-Aufnahme war dieser erste Quotient 1.322,725 % eines Kerns und damit kein plausibler kontinuierlicher Prozessanteil des Vierkernrechners. Die rohe Probe darf nicht als länger anhaltende reale Auslastung interpretiert werden. Die ohnehin aus vollständigen Intervallen zeitgewichteten Kennwerte im aktiven Abschnitt [180,300) s ändern sich nicht. Die ersten groben Ressourcenplots unter `runtime_analysis/` enthalten einfache Darstellungsaggregate der Rohproben; für die abschließende CPU-Darstellung ist `word_figures/sensor_live_resources.png` mit der beschriebenen Intervallgewichtung maßgeblich.

## Nachweise und praktische Grenze

Die maschinenlesbaren Kontrollen liegen in `completion_verification.json`, `thesis_final_layout_audit.json` sowie `layout_review/page_number_verification.json` und `layout_review/text_bounds_audit.json`. Die Grafiken haben ein eigenes Herkunftsmanifest in `word_figures/provenance.json`.

Die Kontrolle erfolgte mit der lokal installierten LibreOffice-Version und anhand des exportierten PDF. Andere Word-/Schriftumgebungen können den Umbruch erneut berechnen. Der PDF-Export ist deshalb die feste visuelle Referenz dieser Prüfung. Die persönliche fachliche Freigabe, eine zutreffende Hilfsmittelerklärung und eine spätere Unterschrift sind keine durch Softwaretests ersetzbaren Nachweise.
