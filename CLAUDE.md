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
a known title before falling back to "no signal."

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

### Known trap — silent write failures

`mql-status.js` returns `{"success":true}` **even when the Airtable write fails.**
In July 2026 every save was silently failing because the Status options were still
Airtable's defaults (Todo / In progress / Done) and Airtable rejected each write.
Nothing in the UI indicated a problem.

So: when a save "works" but no data appears, do not trust the success response —
check the Airtable record directly. (Making the function surface real errors is a
worthwhile fix if asked.)

Netlify env vars `AIRTABLE_TOKEN` and `AIRTABLE_BASE_ID` live in Netlify site
config, never in the repo.

## Monthly update routine

1. Duplicate the live dashboard → `Econic_<Product>_MQL_Dashboard_<Month><Year>.html`
2. Add that file to the **archive footer** links in the live dashboard
3. Update the live file: `REPORT_PERIOD`, `CURRENT_MONTH`, `PREV_MONTH`,
   new `CAMPAIGNS` entries, new `CONTACTS` data
4. Commit and push to `main` (or edit on GitHub directly)

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
