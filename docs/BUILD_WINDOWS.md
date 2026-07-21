# Bygga Windows-installern (.exe)

SirDoge Ledger-installern **måste byggas på Windows** (PyInstaller + Inno Setup).  
Från Linux kan du inte skapa en `.exe` lokalt — använd GitHub Actions eller en Windows-dator/VM.

## Alternativ 1 — Ladda ner färdig installer (GitHub Actions)

1. Pusha repot till GitHub (om du inte redan gjort det).
2. Gå till **Actions** → **build-windows-installer** → **Run workflow**.
3. När jobbet är klart: ladda ner artefakten **SirDogeLedger-Windows-Setup**.
4. Kopiera `SirDogeLedger-Setup.exe` till din Windows-dator.
5. Dubbelklicka → Next → Next → Finish.
6. Starta **SirDoge Ledger** från Startmenyn — webbläsaren öppnas automatiskt.

Workflowen körs också automatiskt när du pushar en tagg som `v0.4.0`.

## Alternativ 2 — Bygg på din Windows-dator

### Krav

- Windows 10/11 (scripten är skrivna för Windows PowerShell 5.1 som ingår i Windows)
- [Python 3.11+](https://www.python.org/downloads/)
- [Node.js 18+](https://nodejs.org/)
- [Inno Setup 6](https://jrsoftware.org/isdl.php) (gratis, valfritt — behövs för Setup.exe)

### Steg

```powershell
cd C:\path\to\sir-doge-ledger
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

Om du får "cannot be loaded because running scripts is disabled", använd kommandot ovan (med `-ExecutionPolicy Bypass`).

Resultat:

| Fil | Beskrivning |
|-----|-------------|
| `dist\installer\SirDogeLedger-Setup.exe` | **Installer** — det du ska kopiera till andra datorer |
| `dist\SirDogeLedger\` | Portabel mapp (utan installer) |

### Efter installation

- Programmet installeras under `Program Files\SirDoge Ledger` (eller användarens AppData om du saknar admin)
- Data sparas i `%LOCALAPPDATA%\sir-doge-ledger`
- Starta via Startmenyn → **SirDoge Ledger**

### SmartScreen-varning

Osignerad `.exe` kan visa Windows SmartScreen-varning. Klicka **Mer info** → **Kör ändå**, eller signera med ett code-signing-certifikat.

## Portabel körning (utan installer)

Om du bara kopierar mappen `dist\SirDogeLedger\` till USB:

```
SirDogeLedger.exe
```

Dubbelklick startar appen och öppnar http://127.0.0.1:8000 i webbläsaren. Lösenord krävs (prod-läge).

## Utveckling på Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_windows.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run_windows.ps1 prod
```

| Mode | URL |
|------|-----|
| Dev frontend | http://127.0.0.1:5173/ |
| Prod / API | http://127.0.0.1:8000/ |
