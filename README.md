# SirDoge Ledger

**Local finance & life admin. Fancy Doge. No cloud.**

Import bank exports, categorize every purchase, review recurrings with yearly costs, and track rent/docs/warranties — all on your machine.

GitHub repo name: **`sir-doge-ledger`**

## Features

- Bank CSV/Excel import with column mapping
- Auto-categorize purchases + unclear review queue
- Learn categories (once vs always)
- Recurring detection with kr/year review
- **Income vs spent charts** + net + category breakdown
- Life admin reminders (rent, warranties, expiry)
- **Always-on local API token** + CSRF protection (stricter than HomeSec dev mode)
- Opaque import sessions — raw file paths never sent to browser

## Security

- Binds to **127.0.0.1** only
- API token generated on start; browser exchanges `?token=` for HttpOnly cookie
- Mutating requests require `X-Sir-Doge` header (CSRF)
- Bank uploads stored with mode `0600`; deleted after import by default
- Data directory: `~/.local/share/sir-doge-ledger/` (mode `0700`)

**Sibling app:** [HomeSec Scanner](../homesec-scanner) — hacker Doge guards your network; SirDoge retired into finance.

## Requirements

- Python 3.11+ with `python3-venv`
- Node.js 18+ and npm

## Start

```bash
cd ~/Projects/sir-doge-ledger
chmod +x run.sh
./run.sh
```

Open the **frontend URL printed with `?token=...`** — required to authenticate your browser.

| Mode | URL |
|------|-----|
| Dev frontend | http://127.0.0.1:5173/?token=... |
| API health | http://127.0.0.1:8000/api/health |

Data: `~/.local/share/sir-doge-ledger/`

## Try without a real export

Import [`sample_data/sample_transactions.csv`](sample_data/sample_transactions.csv).

## Visual theme

| HomeSec Scanner | SirDoge Ledger |
|-----------------|----------------|
| Neon green terminal | Navy + off-white + gold |
| Matrix / CRT | Clean ledger panels |
| Guard Doge | Monocle banker Doge |
