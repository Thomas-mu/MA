# Große Rohdatenaufnahme

`amplitude_gui_20260920_112415_062294.raw.csv` ist für einen regulären GitHub-Push zu groß. Die unveränderten CSV-Daten sind deshalb verlustfrei als gleichnamige `.csv.gz` versioniert. Die lokale CSV bleibt erhalten und wird gezielt in `.gitignore` ausgeschlossen.

Nach einem frischen Checkout im Projektverzeichnis entpacken:

```bash
gzip -dk results/live_runs/amplitude_gui_20260920_112415_062294.raw.csv.gz
```

`gzip -dk` behält das Archiv und überschreibt ohne zusätzliche Option keine vorhandene CSV. Vor der Auswertung oder einer Prüfung der vorhandenen Aufnahme-Hashes muss die CSV entpackt sein.

SHA-256 der unkomprimierten CSV: `600338e971268a7682dcae1db8cce0d7f984f600bab038efbfef6357bbaef72b`.
