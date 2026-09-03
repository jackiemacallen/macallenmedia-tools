import json, re, csv, sys, datetime

# SP is a scratch/working directory for this month's pulled data (Mailchimp
# activity exports, freshly-refreshed domain-company.csv, candidates list --
# see pipeline/README.md). It will NOT be the path below, which was this
# script's original session scratchpad and no longer exists -- point this at
# wherever you're keeping the current month's working files.
SP = "/path/to/this-months-scratch-directory"
REPO = "/Users/jgusc/Documents/GitHub/macallenmedia-tools"

# ---------- shared data ----------
dom2co = {}
for row in csv.DictReader(open(f"{SP}/domain-company.csv")):
    dom2co.setdefault(row["domain"], []).append(row["company"])

def load_companies_map(path):
    text = open(path, encoding="utf8").read()
    m = re.search(r'const COMPANIES = \{(.*?)\n\};', text, re.S)
    pairs = re.findall(r'"([^"]+)":"(target|extended)"', m.group(1))
    return dict(pairs)

REPO_SURF = f"{REPO}/econic-surfactants/Econic_Surfactants_MQL_Dashboard.html"
REPO_POLY = f"{REPO}/econic-polyols/Econic_Polyols_MQL_Dashboard.html"
COMPANIES_MAP = {
    "surfactants": load_companies_map(REPO_SURF),
    "polyols": load_companies_map(REPO_POLY),
}

def normalize(name):
    n = (name or "").lower().strip()
    n = re.sub(r'[.,]', '', n)
    n = re.sub(r'\b(inc|ltd|llc|gmbh|corp|corporation|co|company|plc|sa|spa|ag|nv|group)\b\.?', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n

def lookup_company_status(product, company_name):
    """Returns (canonical_company_name, status) if the company is on the
    target/extended list for this product, else (None, None) -- gates
    dashboard inclusion. This is the MQL dashboard rule: only contacts at
    a company on the target or extended list qualify, new or existing."""
    cmap = COMPANIES_MAP[product]
    if not company_name:
        return None, None
    if company_name in cmap:
        return company_name, cmap[company_name]
    norm_target = normalize(company_name)
    for k, v in cmap.items():
        if normalize(k) == norm_target:
            return k, v
    return None, None

directory = json.load(open(f"{SP}/contact-directory.json"))["contacts"]
dir_by_email = {c["email"].lower(): c for c in directory}

mc = json.load(open("/tmp/mc_members.json"))
mc_members = {m["email_address"].lower(): m for m in mc["members"]}

july_eng = json.load(open(f"{SP}/pipeline/july_engagement_deduped.json"))
downloads = json.load(open(f"{SP}/pipeline/gated_downloads_jul_aug.json"))

SURF_ASSETS = {"Recreaire Brochure Download", "Future of Surfactants Presentation Download",
               "Keith ICIS 2025 Recreaire Presentation Download"}
POLY_ASSETS = {"PUD Applications Brochure", "Richard Europur 2026 Presentation",
               "UTech SEAsia", "Technobiz 2026 Presentation"}

JULY_CAMPAIGN_FOR_PRODUCT = {"surfactants": "supply_chain_jul", "polyols": "polyols_jul"}
JULY_CAMPAIGN_LABEL = {
    "supply_chain_jul": {"surfactants": "After Hormuz: Feedstock Article (Simon)"},
    "polyols_jul": {"polyols": "TechnoBiz/APUA Polyols Presentation"},
}


def guess_name(email):
    m = mc_members.get(email.lower())
    if m:
        fn = (m.get("merge_fields", {}).get("FNAME") or "").strip()
        ln = (m.get("merge_fields", {}).get("LNAME") or "").strip()
        if fn or ln:
            name = f"{fn} {ln}".strip()
            initials = "".join(p[0].upper() for p in name.split() if p)[:2]
            return name, initials or "??"
    d = dir_by_email.get(email.lower())
    if d and d.get("name"):
        name = d["name"]
        initials = "".join(p[0].upper() for p in name.split() if p)[:2]
        return name, initials or "??"
    local = email.split("@")[0]
    parts = re.split(r"[._]", local)
    parts = [p for p in parts if p and not p.isdigit()]
    if len(parts) >= 2:
        name = " ".join(p.capitalize() for p in parts)
        initials = "".join(p[0].upper() for p in parts[:2])
    elif parts:
        name = parts[0].capitalize()
        initials = parts[0][:2].upper()
    else:
        name, initials = email, "??"
    return name, initials


def resolve_company_title_status(email, product):
    """Returns (company, title, status) or (None, None, None) if this
    person's company isn't on the product's target/extended list -- the
    MQL dashboard gate. New and existing contacts are treated identically:
    what matters is the company, not how long they've been known."""
    domain = email.split("@")[-1].lower()
    m = mc_members.get(email.lower(), {})
    mf = m.get("merge_fields", {})
    d = dir_by_email.get(email.lower())

    candidates = []
    companies = dom2co.get(domain, [])
    if companies:
        candidates.append(companies[0])
    if d and d.get("company"):
        candidates.append(d["company"])
    if mf.get("MMERGE6", "").strip():
        candidates.append(mf.get("MMERGE6").strip())

    for cand in candidates:
        canonical, status = lookup_company_status(product, cand)
        if canonical:
            title = (d["title"] if d and d.get("title") else "") or mf.get("MMERGE7", "").strip()
            return canonical, title, status

    return None, None, None


# ---------- balanced-brace contact parsing (preserves any engagement field shape) ----------
def parse_contacts_block(text):
    m = re.search(r'const CONTACTS = \[', text)
    start = m.end() - 1  # position of the [
    depth = 0
    i = start
    while True:
        ch = text[i]
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1
    block = text[start + 1:end - 1]

    contacts = []
    depth = 0
    obj_start = None
    for idx, ch in enumerate(block):
        if ch == '{':
            if depth == 0:
                obj_start = idx
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                raw = block[obj_start:idx + 1]
                contacts.append(parse_one_contact(raw))
    full_start = m.start()
    full_end = m.start() + (end - start) + len("const CONTACTS = ")
    # recompute exact absolute span of "const CONTACTS = [...]"
    abs_start = m.start()
    abs_end = abs_start + len("const CONTACTS = ") + (end - start)
    return contacts, abs_start, abs_end


def parse_one_contact(raw):
    def field(name):
        mm = re.search(rf'{name}:"((?:[^"\\]|\\.)*)"', raw)
        return mm.group(1) if mm else ""

    eng_match = re.search(r'engagements:\[(.*)\]\s*\}$', raw, re.S)
    eng_block = eng_match.group(1) if eng_match else ""
    eng_entries = []
    depth = 0
    obj_start = None
    for idx, ch in enumerate(eng_block):
        if ch == '{':
            if depth == 0:
                obj_start = idx
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                eng_entries.append(eng_block[obj_start:idx + 1])
    return {
        "name": field("name"), "initials": field("initials"), "title": field("title"),
        "company": field("company"), "email": field("email"), "note": field("note"),
        "status": field("status"), "engagements": eng_entries,
    }


def format_contact(c):
    eng_lines = ",\n".join(f"      {e}" for e in c["engagements"])
    return (f'  {{name:"{c["name"]}",initials:"{c["initials"]}",title:"{c["title"]}",'
            f'company:"{c["company"]}",email:"{c["email"]}",note:"{c["note"]}",'
            f'status:"{c["status"]}",engagements:[\n{eng_lines}\n  ]}}')


def format_camp_entry(sid, month, opens, clicks):
    return f'{{campaign_id:"{sid}",month:"{month}",opens:{opens},clicks:{clicks}}}'


def format_webform_entry(date, sources):
    month = date[:7]
    src = ", ".join(sources)
    return f'{{campaign_id:"web_form",month:"{month}",opens:0,clicks:0,web_form:true,date:"{date}",source:"{src}"}}'


def already_has_campaign(engagements, sid):
    return any(f'campaign_id:"{sid}"' in e for e in engagements)


def already_has_webform_date(engagements, date):
    return any(f'web_form:true,date:"{date}"' in e for e in engagements)


# ---------- July layer ----------
def build_july(product, live_path, out_path):
    text = open(live_path, encoding="utf8").read()
    contacts, start, end = parse_contacts_block(text)
    by_email = {c["email"].lower(): c for c in contacts}

    sid = JULY_CAMPAIGN_FOR_PRODUCT[product]
    other_sid = JULY_CAMPAIGN_FOR_PRODUCT["polyols" if product == "surfactants" else "surfactants"]
    assets = SURF_ASSETS if product == "surfactants" else POLY_ASSETS

    touched = set()
    added, updated, skipped_no_company = [], [], []

    # 1. campaign engagement signal
    for email, camps in july_eng.items():
        if sid in camps and (camps[sid][0] > 0 or camps[sid][1] > 0):
            touched.add(email)

    # 2. July-dated download signal
    july_downloads_by_email = {}
    for r in downloads:
        if not r["date"].startswith("2026-07"):
            continue
        matches = [a for a in r["downloads"] if a in assets]
        if matches:
            touched.add(r["email"].lower())
            july_downloads_by_email.setdefault(r["email"].lower(), []).append((r["date"], matches))

    for email in sorted(touched):
        c = by_email.get(email)
        new_entries = []
        opens = clicks = 0
        if email in july_eng and sid in july_eng[email]:
            opens, clicks = july_eng[email][sid]
        if email in july_downloads_by_email:
            for date, matches in july_downloads_by_email[email]:
                new_entries.append(("web_form", date, matches))
        has_campaign_eng = opens > 0 or clicks > 0

        if c is None:
            co, title, status = resolve_company_title_status(email, product)
            if co is None:
                skipped_no_company.append(email)
                continue
            name, initials = guess_name(email)
            eng = []
            if has_campaign_eng:
                eng.append(format_camp_entry(sid, "2026-07", opens, clicks))
            for _, date, matches in new_entries:
                eng.append(format_webform_entry(date, matches))
            c = {"name": name, "initials": initials, "title": title, "company": co,
                 "email": email, "note": "", "status": status, "engagements": eng}
            contacts.append(c)
            by_email[email] = c
            added.append((email, co, status))
        else:
            if has_campaign_eng and not already_has_campaign(c["engagements"], sid):
                c["engagements"].append(format_camp_entry(sid, "2026-07", opens, clicks))
                updated.append((email, "campaign"))
            for _, date, matches in new_entries:
                if not already_has_webform_date(c["engagements"], date):
                    c["engagements"].append(format_webform_entry(date, matches))
                    updated.append((email, "download"))

    new_block_inner = "[\n" + ",\n".join(format_contact(c) for c in contacts) + "\n]"
    new_text = text[:start] + "const CONTACTS = " + new_block_inner + text[end:]
    open(out_path, "w", encoding="utf8").write(new_text)
    return len(contacts), added, updated, skipped_no_company


n1, added1, upd1, skip1 = build_july(
    "surfactants", REPO_SURF,
    f"{SP}/pipeline/Econic_Surfactants_MQL_Dashboard_July2026.html")
print(f"SURFACTANTS July: {n1} total contacts, {len(added1)} newly added, {len(upd1)} existing-contact updates, {len(skip1)} skipped (no target/extended company match)")
for e, co, st in added1:
    print(f"   + {e}  ({co}, {st})")

n2, added2, upd2, skip2 = build_july(
    "polyols", REPO_POLY,
    f"{SP}/pipeline/Econic_Polyols_MQL_Dashboard_July2026.html")
print(f"\nPOLYOLS July: {n2} total contacts, {len(added2)} newly added, {len(upd2)} existing-contact updates, {len(skip2)} skipped (no target/extended company match)")
for e, co, st in added2:
    print(f"   + {e}  ({co}, {st})")

json.dump({"surf_skipped": skip1, "poly_skipped": skip2}, open(f"{SP}/pipeline/july_skipped_no_company.json", "w"), indent=1)
