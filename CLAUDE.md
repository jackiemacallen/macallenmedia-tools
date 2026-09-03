# MacAllen Media Tools — Project Context

## Communication style

Jackie is not a professional developer. Explain technical terms in plain English,
avoid unexplained jargon, and check in before anything hard to undo (overwriting
files, force-pushing, deleting data, deploying). Routine low-risk things — just do them.

## What this repo is

Client-facing tools for MacAllen Media & Public Affairs. The main work is the
**Econic MQL dashboards** — self-contained HTML pages that score Econic
Technologies' marketing contacts into Marketing Qualified Leads each month.

```
/                                → Tools landing page (MMPA-branded index)
/econic-surfactants/             → Surfactants MQL Dashboard  (DASHBOARD_ID econic-surfactants)
/econic-polyols/                 → Polyols MQL Dashboard      (DASHBOARD_ID econic-polyols)
/haus-formulations/              → Haus of Innovation Concept Formulation Generator (separate tool)
/netlify/functions/mql-status.js → Serverless function: dashboard ⇄ Airtable status writes
```

## Hosting — TWO hosts, and that split is deliberate

This surprises people. Do not "fix" it by consolidating without asking.

- `dashboards.macallenmedia.com` → **GitHub Pages** (`jackiemacallen.github.io`).
  This is where the dashboards are served. The repo `CNAME` file holds this.
- `tools.macallenmedia.com` → **Netlify** (site `jolly-taffy-96177e`), continuous
  deploy from GitHub `main`. This runs the serverless function, because GitHub
  Pages cannot run server code.

The dashboards call the function cross-origin at
`https://tools.macallenmedia.com/.netlify/functions/mql-status`.
The function sends permissive CORS headers, which is what makes that work.
The `README.md` still says the site lives at tools.macallenmedia.com — that is
stale; dashboards are on dashboards.*.

## How a dashboard works

Each dashboard is ONE self-contained HTML file (~1,200–1,700 lines): styles,
markup, and script inline. No build step. Edit the file, commit, push — live in ~60s.

- **Password gate** near the top: a `prompt()` checked against a hardcoded `PASS`,
  cached in `sessionStorage` under `mql_auth`. Client-side only — this deters
  casual access, it is not real security. Don't put anything truly sensitive here.
  **Trap:** the Surfactants dashboard's gate hides the whole page by default
  (`<style id="auth-hide">body{display:none!important}</style>`) and only
  reveals it once `prompt()` succeeds — if `prompt()` throws (any in-app
  preview/webview that blocks native popups will do this; confirmed this
  happens when a delivered file is opened outside a real browser tab), the
  page stays permanently blank with zero error message. Fixed by wrapping the
  `prompt()` call in try/catch and failing open (reveal content) rather than
  failing blank, since the gate is explicitly not real security anyway. The
  Polyols dashboard uses an *older, different* gate implementation that never
  hides the page by default, so it degrades gracefully without needing this
  fix — the two dashboards are not running identical gate code, worth knowing.
- **`CONFIG` block** (~line 250) is what changes monthly:
  `REPORT_PERIOD`, `CURRENT_MONTH`, `PREV_MONTH`, plus the `CAMPAIGNS` registry.
  In `CAMPAIGNS`, `month` is the campaign's **actual send month, not the export date**.
- **`SCORE` weights**: web_form 4, email_click_each 3, repeat_opens 2,
  multi_campaign_bonus 2.
- **`COMPANIES` map**: `"target"` = Simon's priority list (green),
  `"extended"` = industry-relevant (yellow).
- **`CONTACTS` array** (~line 345): the month's contact/engagement data, pasted in.
- **Status pills** (Emailed / Not relevant / In convo / Cleared) GET and POST to
  the Netlify function, which upserts into Airtable.

## Deciding which dashboard a contact belongs on

This is a **per-person** decision, never inferred from their employer. Many companies
(Covestro, Arkema, ThyssenKrupp, LANXESS, PCC Rokita...) are relevant to both product
lines as an organization, but an individual contact there almost always specializes in
one side, not both. Using "the company is on the target/extended list" as the inclusion
test was tried and overcounted candidates ~7x in a real check (51 proposed additions,
only 7 held up) — two of the false positives were contacts whose own job titles were
squarely polyols (TDI/polyether, acrylic monomers) despite working at a company that
also does surfactants.

The real rule, checked against live Mailchimp data (tags, `Contact Topic` merge field,
`Job Title` merge field) — **for Surfactants:**
1. Tagged `"Surfactants"` (or Contact Topic = "Surfactants") → include, done.
2. Not tagged → check what they subscribed/downloaded via — surfactants-related content?
3. Neither → job title keywords (surfactant, rinse aid, home/personal care, detergent,
   cleaning, I&I).

**For Polyols:**
1. **Tagged `"Surfactants"`? → excluded outright, stop.** There is no dedicated
   "Polyols" tag — the Surfactants tag is the disambiguator in both directions.
2. Not Surfactants-tagged → topic/download signal for polyols content (tags/topics:
   "All PU applications", "All Polyurethane Topics", "Flexible Foam", "Rigid Foam",
   "CASE", "Automotive").
3. Neither → job title keywords (polyol, polyurethane, TDI, polyether, isocyanate,
   MDI, foam, elastomer, acrylic monomer, coating, adhesive, sealant).

A contact with no tag, no topic, and a blank/generic title has **no signal either
way** — don't auto-add them to either dashboard. Surface them as a manual-check list
instead; this is exactly the judgment call Jackie already does by hand (Mailchimp
profile → LinkedIn) for anyone the automated tiers can't resolve.

**Trap:** Mailchimp's own Job Title field is often blank even when the real title is
already known — because the person is an *existing* contact on the other dashboard,
where their title was captured separately (e.g. during the original backfill). Checking
only Mailchimp's field before declaring "no signal" undercounts badly: one real pass
found 22 of 31 "no signal" people actually had a known title sitting in the existing
`CONTACTS` data the whole time. Always check the existing dashboard/directory data for
a known title before falling back to "no signal." If it's still blank there, check
LinkedIn (this is the step Jackie does by hand normally — don't skip it just because
Mailchimp's field is empty).

**Content-based resolution is also valid, on top of tag/topic/title.** If a campaign
or gated asset is inherently single-product by its own content (e.g. a presentation
titled around "polyols" or "surfactants", a press release about one product line only),
anyone who engaged with it resolves to that product without needing a tag — same
tier as topic/download signal. Check the actual campaign content
(`GET /campaigns/{id}/content`) or the gated asset's name, not just its label.

**A company's target/extended status still gates MQL dashboard inclusion — new or
existing contact, doesn't matter.** ("Barometer of interest" framing does NOT mean
including anyone who merely clicked something regardless of company — that was tried
and would have pulled in retirees, magazine editors, VCs, personal Gmail addresses.
Company gating stays; only "new vs. already-known contact" stops mattering.) The
`COMPANIES` object embedded in each live dashboard file is not always in sync with
Airtable's `Companies` table — Airtable is more current (Simon/Richard's additions
land there first). **Before resolving anyone's company each month, pull fresh from
Airtable's `Domains` and `Companies` tables — do not reuse a local CSV/cache from a
previous session.** A stale local domain→company cache caused several real contacts
(Perstorp, Dow, Sika, ThyssenKrupp) to be wrongly excluded from July 2026 even though
their companies were already correctly classified in Airtable.

**Individual override of a company's default status is allowed and expected** — Jackie
confirmed this explicitly: "some companies are relevant for both... any one person could
be interested in both depending on their job." If a specific person's own title or a
gated download they made points to the *other* product line than what their company is
marked for (including a company marked `n/a` for that product), add them to that
dashboard individually — do not change the company's own target/extended status in
Airtable to do it (that's a company-wide call for Simon/Richard, not something to
infer from one person). Put the reasoning directly in that contact's `note` field, e.g.
`"Added individually -- Company is n/a for Polyols, but her own title (...) is a direct
signal"`. Real examples: Marcelle Moeller (Dow — company is n/a for Polyols, her title
is "Global Sustainability Director Dow Polyurethanes"); Joachim Lentz (Perstorp —
company is n/a for Polyols, but he downloaded polyols content and his LinkedIn focus is
coatings/UV-curing chemistry).

**The extended list is at Jackie's discretion, and by extension within normal working
judgment when adding contacts** — it is not a fixed allowlist that only she or
Simon/Richard can expand. A clearly real, relevant company found through this process
(e.g. from a domain that resolves via Airtable, or a company an engaged contact
obviously works at) can be added to a product's extended list without asking first,
the same as any other routine low-risk judgment call.

## Gated downloads (`web_form` entries) — where the data actually lives

The specific asset someone downloaded is **not** in Mailchimp's `tags`, `merge_fields`,
`notes`, or `source` field — all four were checked directly and none carry it. It lives
in a **hidden interest category literally named "API Source"** (id `9edef5c7eb` on list
`29b2f1cbd9`). Each gated PDF/PPT is its own interest checkbox, flipped `true` on
download. Pull via `members.interests` on the members endpoint; decode IDs via
`GET /lists/{list_id}/interest-categories/9edef5c7eb/interests`. `timestamp_opt` gives an
exact, verified signup date — reliable for a contact with exactly one interest set, but
only dates the *first* download if several are set.

Watch for a cluster of synthetic-looking signup domains (`@laoia.com`, `@aghism.com`,
similar) arriving in same-day batches with real interest flags set. Could be genuine,
could be QA testing (Jackie tests these forms herself sometimes), could be a bot.
Surface for a human call rather than auto-including or auto-excluding.

## Airtable

Base `appunHL9v74gQm3fx` ("Econic MQL Tracker"), table **`MQL Status Tracker`**.
Fields used: Email, Status, Dashboard, Period, Updated At.

**The `Status` single-select must contain exactly these options:**
`emailed`, `not-relevant`, `in-convo`, `cleared`

These are raw slugs on purpose — the dashboard writes AND reads these exact
strings. Renaming them to pretty labels breaks saving and requires dashboard
code changes too.

### Silent write failures — FIXED as of Aug 2026, but know the history

`mql-status.js` used to return `{"success":true}` **even when the Airtable write
failed.** In July 2026 every save was silently failing because the Status options
were still Airtable's defaults (Todo / In progress / Done) and Airtable rejected
each write. Nothing in the UI indicated a problem. This is almost certainly why
Willis Muganda's "not relevant" click (made by Simon) never actually landed in
Airtable, even though the UI presumably showed it as saved at the time.

**Fixed:** `airtableFetch()` in `mql-status.js` now checks `res.ok` and throws a
real error instead of blindly returning whatever Airtable sent back. Both
dashboards' `saveStatus()` now checks the response and shows an `alert()` to
whoever clicked the pill if the save didn't actually go through, instead of
silently leaving a "saved-looking" pill that isn't. Verified live end-to-end
(both a real save and a deliberately-rejected write) on 2026-08-31 — confirmed
working, confirmed a rejected write no longer creates a phantom "success."
Still worth an occasional live spot-check (see verification pattern in git log
commit `f628833`) since nothing prevents this class of bug recurring differently.

Netlify env vars `AIRTABLE_TOKEN` and `AIRTABLE_BASE_ID` live in Netlify site
config, never in the repo.

### "Not relevant" is permanent — check before ever re-adding anyone

If Simon or Rich has ever marked a contact "not relevant" on a dashboard (Airtable
`MQL Status Tracker`, `Status` = `not-relevant`), they should never be silently
re-added, even if they show new engagement in a later month. Before finalizing a
month's build, query Airtable for all `not-relevant` records and drop those emails
from that dashboard's `CONTACTS`, regardless of what new engagement they show.
This is not yet enforced by any script — it's a manual check each month until
someone builds it into the pipeline (see Housekeeping below).

## Monthly update routine

1. **Refresh company/domain data from Airtable first** — pull fresh from the
   `Domains` and `Companies` tables (base `appunHL9v74gQm3fx`), don't reuse a
   cached CSV from a previous session. This is the single most important step;
   skipping it caused real contacts to be wrongly excluded in Aug 2026 (see
   above).
2. Pull the month's Mailchimp campaign activity (`/reports/{id}/email-activity`)
   and gated-download interest data (see "Gated downloads" above). Dedupe click
   bursts by collapsing identical-timestamp events (bot/scanner artifact).
3. Classify each engaged/downloaded contact per "Deciding which dashboard a
   contact belongs on" above — tag → topic/download → title → LinkedIn →
   content-based campaign/asset resolution. Only include a contact whose company
   resolves to target/extended on that product's list (or apply an individual
   override with a documented reason, per that section).
4. Check Airtable for `not-relevant` records and exclude those emails, even if
   they show new engagement (see above).
5. Duplicate the live dashboard → `Econic_<Product>_MQL_Dashboard_<Month><Year>.html`
   (this becomes the frozen archive of the month that's ending)
6. Add that file to the **archive footer** links in the new live dashboard
7. Update the live file: `REPORT_PERIOD`, `CURRENT_MONTH`, `PREV_MONTH`,
   new `CAMPAIGNS` entries, new `CONTACTS` data (existing contacts get new
   engagement rows appended, never delete old rows; new contacts get a fresh
   contact block)
8. **Verify in a real browser before delivering** — a local `python3 -m
   http.server` + checking both month-view and YTD-view render real data with
   no console errors (see Verification discipline below; the auth-gate bug
   below is exactly the kind of thing pure code review misses).
9. Commit and push to `main` (or edit on GitHub directly)

This is not yet a single push-button script — it's a documented sequence
someone (Claude or otherwise) walks through by hand each month. The actual
Python pipeline code that implements steps 1-4 lives in `pipeline/` in this
repo (not a scratchpad — scratchpads don't survive between sessions) as a
starting point to build from, not a finished automation.

## Verification discipline

Dashboards are browser JS with real fonts and layout. Before calling a change done,
open the actual file in a real browser (headless Chromium / Puppeteer is fine) and
confirm it renders and the numbers are right. Reasoning about the code alone has
produced false confidence on MMPA projects before.

## Housekeeping notes

- Loose copies of these dashboards exist in `~/Downloads`, `~/Desktop/Downloads`,
  `~/Downloads/site-deploy`, and `macallenmedia-tools 2`. **This git repo is the
  source of truth** — those are stale snapshots, don't edit them.
- Reference docs in `~/Downloads`: `MQL_Contact_Classification_Methodology.md`,
  `MQL_Function_Deployment_Summary.md`, `COWORK_DEPLOY_MQL_FUNCTION.md`.
- Branch `backup-local-jun1-2026` preserves an old diverged local commit
  (Aug 2026 cleanup). Safe to delete once you're confident nothing's needed from it.
