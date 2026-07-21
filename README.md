# SirDoge Ledger

<p align="center">
  <img src="docs/sir-doge.png" alt="Sir Doge — private banker" width="420" />
</p>

**Local finance & life admin. Fancy Doge. No cloud.**

Import bank exports, categorize purchases, review subscriptions as yearly cost, set budgets, and track rent/docs/warranties — all on your machine.

Version: **0.4** · Repo: [`sir-doge-ledger`](https://github.com/gabriellofberg/sir-doge-ledger)

## Features

- **Bank import** — CSV/Excel with column mapping; optional sample CSV for demos
- **Auto-categorize** + unclear review queue; learn rules (once vs always)
- **Rules page** — view, edit, or disable learned category rules
- **Recurring detection** — kr/year review, cancel-by date, price-change alerts
- **Overview charts** — income vs spent, net, category breakdown + spending insights
- **Budgets & recommendations** — optional per-category limits; % of income tips when income is set
- **Life admin** — rent, warranties, expiry reminders; calendar export (`.ics`)
- **Your data** — CSV/JSON export, wipe-all (for demos), log out
- **Demo mode** — separate demo database from the login screen (real data untouched)
- **Swedish / English** — 🇸🇪 / 🇺🇸 toggle for the full UI
- **Light / dark theme** — deep charcoal dark mode (Settings)

## Security

| Mode | How you sign in |
|------|-----------------|
| **Dev** (`./run.sh`) | Open — no password (`SIR_DOGE_DEV=1`) |
| **Prod** (`./run.sh prod`) | Password on first visit; recovery key saved locally |

- Binds to **127.0.0.1** only
- Session cookie (HttpOnly, SameSite=strict) after login
- Mutating requests require `X-Sir-Doge` header (CSRF)
- Bank uploads mode `0600`; deleted after import by default
- Data directory (Linux/macOS): `~/.local/share/sir-doge-ledger/` (mode `0700`)
- Data directory (Windows): `%LOCALAPPDATA%\sir-doge-ledger`
- Recovery key (prod): `recovery-hint.txt` in the data folder
- Dev password reset: delete `auth.json` in the data folder, or use the recovery key

**Sibling app:** [HomeSec Scanner](../homesec-scanner) — hacker Doge guards your network; SirDoge retired into finance.

## Requirements

- Python 3.11+ with `python3-venv` (Linux/macOS) or venv on Windows
- Node.js 18+ and npm

## Start

### Linux / macOS

```bash
cd ~/Projects/sir-doge-ledger
chmod +x run.sh
./run.sh          # development (open auth + Vite)
./run.sh prod     # production build (password required)
```

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_windows.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run_windows.ps1 prod
```

| Mode | URL |
|------|-----|
| Dev frontend | http://127.0.0.1:5173/ |
| Prod / API | http://127.0.0.1:8000/ |
| Health | http://127.0.0.1:8000/api/health |

**Data:** Linux/macOS `~/.local/share/sir-doge-ledger/` · Windows `%LOCALAPPDATA%\sir-doge-ledger`

## Windows installer (.exe)

Build a portable bundle and `SirDogeLedger-Setup.exe` via GitHub Actions or locally on Windows — see [docs/BUILD_WINDOWS.md](docs/BUILD_WINDOWS.md).

## Quick tour

| Goal | Where |
|------|--------|
| Try the UI with fake data | Login → **Try demo** |
| Switch language | Sidebar flags 🇸🇪 / 🇺🇸 |
| Set income / budgets / theme | **Settings** |
| Fix learned categories | **Rules** |
| Load sample transactions | **Import** → Load sample CSV |
| Export or wipe before showing a friend | **Your data** |

## Try without a real export

1. **Import** → *Load sample CSV*, or  
2. Use file [`sample_data/sample_transactions.csv`](sample_data/sample_transactions.csv), or  
3. **Try demo** on the sign-in screen (isolated `demo.db`)

## Visual theme

| HomeSec Scanner | SirDoge Ledger |
|-----------------|----------------|
| Neon green terminal | Navy + off-white + gold (light) / deep charcoal (dark) |
| Matrix / CRT | Ledger panels + banker Doge hero |
| Guard Doge | Monocle banker Doge |
