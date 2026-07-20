# ⚓ Too busy for Beer – Boots-Wächter

Eine kleine Web-Seite, die für unsere Donau-Bootstour zwei Dinge automatisch beobachtet
und übersichtlich anzeigt: **das Wetter** und den **Blaualgen-/Bakterien-Status** der Donau.
Link teilen, fertig – jeder sieht denselben Stand.

## Was die Seite kann (Lastenheft, kurz)

- **Zwei Themen als „Wächter":** Wetter am Tourtag + Algen/Bakterien in der Donau.
- **Automatik ~3×/Tag** (07:10 / 13:10 / 19:10 MESZ) über GitHub Actions – läuft auch, wenn niemand die Seite offen hat.
- **Wetter = Konsens mehrerer Modelle** (Open-Meteo: ICON, GFS, ECMWF): mittlerer Wert + Spannbreite, plus Regen-%, Wind/Böen, Gewitter, Morgentemperatur und ein 3-Stunden-Verlauf für den Tourtag. Für beide Streckenenden (Kapfelberg/Kelheim + Regensburg), inkl. Karte.
- **Algen = amtliche Lage (Landkreis Kelheim) + Nachrichtenlage** mit Direktlinks und Datum der letzten Prüfung.
- **Ampel + Klartext** (grün/gelb/rot), bewusst **vorsichtig**: im Zweifel eher Gelb.
- **Letzter vs. aktueller Stand:** Tendenzpfeile + Mini-Verlauf, wie sich die Prognose über die Tage bewegt.
- **Countdown** bis zum Ablegen, **Tourdatum einstellbar** (in `config.json`), mobilfreundlich.

## Dateien

| Datei | Zweck |
|---|---|
| `index.html` | Die Seite (nur diese wird angezeigt) |
| `config.json` | **Hier stellst du Tourdatum, Uhrzeit & Orte ein** |
| `scripts/update.py` | Holt Wetter + Algen-Status, schreibt die Daten |
| `data.json` | Aktueller Stand (automatisch erzeugt) |
| `history.json` | Verlauf für die Trend-Anzeige (automatisch) |
| `.github/workflows/update.yml` | Der 3×/Tag-Automatik-Job |

## Datum / Orte ändern

In `config.json` einfach `trip_date` (Format `JJJJ-MM-TT`) bzw. `trip_start_time` anpassen und speichern.
Beim nächsten Lauf (oder „Run workflow", siehe unten) rechnet die Seite alles neu.

## Einrichten auf GitHub (einmalig, ohne Kommandozeile)

1. **Neues Repository** anlegen (z. B. `boots-waechter`), Sichtbarkeit **Public**.
2. Alle Dateien aus diesem Ordner hochladen (**Add file → Upload files**), Ordnerstruktur beibehalten
   (`scripts/` und `.github/workflows/` müssen erhalten bleiben – am einfachsten den ganzen Ordner-Inhalt reinziehen).
3. **Actions aktivieren:** Tab **Actions** → einmal bestätigen, dass Workflows laufen dürfen.
4. **Pages aktivieren:** **Settings → Pages** → *Source: Deploy from a branch* → Branch **main**, Ordner **/(root)** → Save.
5. **Ersten Lauf starten:** Tab **Actions → „Boots-Wächter Update" → Run workflow.** Danach steht `data.json`.
6. Nach 1–2 Minuten ist die Seite live unter:
   `https://DEIN-BENUTZERNAME.github.io/boots-waechter/`
   → **diesen Link an die Jungs schicken.** 🍻

> Hinweis: Der Automatik-Job braucht Schreibrechte (schon im Workflow gesetzt: `permissions: contents: write`).
> Falls das Committen fehlschlägt: **Settings → Actions → General → Workflow permissions → „Read and write permissions"** aktivieren.

## Quellen & Haftung

Wetter: [Open-Meteo](https://open-meteo.com) (freie Modell-API). Algen/Bakterien: Landkreis Kelheim
sowie öffentliche Nachrichten. Alles ohne Gewähr – am Tourtag morgens bitte selbst nochmal draufschauen,
besonders bei Gewitter (bei Blitz vom Wasser) und beim Wasserkontakt.
