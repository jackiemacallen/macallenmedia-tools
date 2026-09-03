# MQL dashboard build pipeline — current state

**This is a starting point to build from each month, not a push-button
automation.** It captures the logic that took real trial-and-error to get
right (see `CLAUDE.md` in the repo root for the full history of what went
wrong and why). Read that file's "Monthly update routine" and "Deciding which
dashboard a contact belongs on" sections first — this README is just the
mechanics.

## What's scriptable vs. what needs an interactive session

- **Mailchimp side is fully scriptable.** The API key lives at
  `~/.config/econic/mailchimp-api-key` (format `<hex>-us10`), used like:
  `curl -s -u "anystring:$(cat ~/.config/econic/mailchimp-api-key)" "https://us10.api.mailchimp.com/3.0/..."`.
  Campaign activity, gated-download interest data (see CLAUDE.md's "Gated
  downloads" section), and audience merge fields all pull this way.

- **Airtable side currently does not.** There is no standalone Airtable API
  key stored locally (the real one lives only in Netlify's environment,
  intentionally never in this repo). Refreshing `Domains`/`Companies` data,
  and checking `MQL Status Tracker` for `not-relevant` records, both require
  the Airtable MCP tool inside an interactive Claude session — this is the
  main reason the pipeline isn't a single unattended script yet. If someone
  wants to close this gap, the fix is either (a) a scoped Airtable token
  stored the same way as the Mailchimp key, used with plain `curl` against
  Airtable's REST API, or (b) accept that the monthly build always runs
  inside a Claude session with Airtable access.

## Scripts here

- **`build_month_layer.py`** — takes a live dashboard file + a month's deduped
  campaign engagement (`{email: {campaign_id: [opens, clicks]}}`) + a
  human-verified candidates list, and produces an updated dashboard file with
  new engagement layered onto existing contacts and new contacts added. This
  is the shape used for a month with real email campaigns. Read the file
  top-to-bottom before running — several inputs (the engagement dict, the
  candidates list, the domain/company CSVs) are expected to already exist as
  local files; it does not fetch them itself.

- **`build_download_only_layer.py`** — same idea, but for a month with no new
  email campaign, only gated-download (`web_form`) engagement. This is what
  built the August 2026 live file on top of July's archive.

Both scripts currently:
- Read company target/extended status from the *live dashboard's own*
  `COMPANIES` object as a fallback, but the correct source of truth is a
  freshly-pulled Airtable `Companies` table (see CLAUDE.md — the dashboard's
  embedded list can drift out of sync, as it did with Perstorp in Aug 2026).
  **Refresh the local `domain-company.csv` and a companies-status JSON from
  Airtable before running these scripts, every month** — don't reuse one from
  a previous month.
- Do NOT check Airtable's `MQL Status Tracker` for `not-relevant` records.
  Do this manually (or extend the script) before finalizing — see CLAUDE.md.
- Do NOT apply the individual-override rule (a person's own title/download
  overriding their company's default status for the other product) — that
  still needs a human judgment call each time it comes up, the same way it
  did for Marcelle Moeller and Joachim Lentz in Aug 2026.

## Verification

Never ship a build without opening it in a real browser first (a local
`python3 -m http.server` + checking both month-view and YTD-view). Pure code
review has produced false confidence on this project before, including once
this session (an auth-gate bug that pure code reading would not have caught
without actually loading the page).
