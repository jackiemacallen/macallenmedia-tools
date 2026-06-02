# MacAllen Media Tools

Client-facing tools hosted at [tools.macallenmedia.com](https://tools.macallenmedia.com).

## Structure

```
/                              → Landing page (tools index)
/econic-surfactants/           → Econic Surfactants MQL Dashboard
/econic-polyols/               → Econic Polyols MQL Dashboard
```

## Updating a dashboard (monthly)

1. Open the relevant HTML file in this repo on GitHub
2. Click the pencil (Edit) icon
3. Make your changes (update REPORT_PERIOD, CURRENT_MONTH, PREV_MONTH, add new contacts/campaigns)
4. Click **Commit changes** — the site updates automatically within ~60 seconds

Or if editing locally:
1. Edit the file
2. `git add . && git commit -m "Update to June 2026" && git push`

## Archiving a month

Before updating to a new month:
1. In the relevant folder, duplicate the dashboard file and rename it, e.g. Econic_Surfactants_MQL_Dashboard_May2026.html
2. Add a link to it in the archive footer of the live dashboard
3. Then update the live file to the new month

## DNS

CNAME file in repo root points to tools.macallenmedia.com.
DNS CNAME record at your registrar should point to jackiemacallen.github.io.

## Google Apps Script

Deploy URL goes in the APPS_SCRIPT_URL constant at the top of each dashboard HTML file.
