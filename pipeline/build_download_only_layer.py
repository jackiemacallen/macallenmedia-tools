import json, re, csv

# See the same note in build_month_layer.py -- SP is a scratch/working
# directory for this month's pulled data, not a real persistent path.
SP = "/path/to/this-months-scratch-directory"
REPO = "/Users/jgusc/Documents/GitHub/macallenmedia-tools"

dom2co = {}
for row in csv.DictReader(open(f"{SP}/domain-company.csv")):
    dom2co.setdefault(row["domain"], []).append(row["company"])

def load_companies_map(path):
    text = open(path, encoding="utf8").read()
    m = re.search(r'const COMPANIES = \{(.*?)\n\};', text, re.S)
    pairs = re.findall(r'"([^"]+)":"(target|extended)"', m.group(1))
    return dict(pairs)

COMPANIES_MAP = {
    "surfactants": load_companies_map(f"{SP}/pipeline/Econic_Surfactants_MQL_Dashboard_July2026.html"),
    "polyols": load_companies_map(f"{SP}/pipeline/Econic_Polyols_MQL_Dashboard_July2026.html"),
}

def normalize(name):
    n = (name or "").lower().strip()
    n = re.sub(r'[.,]', '', n)
    n = re.sub(r'\b(inc|ltd|llc|gmbh|corp|corporation|co|company|plc|sa|spa|ag|nv|group)\b\.?', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n

def lookup_company_status(product, company_name):
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
downloads = json.load(open(f"{SP}/pipeline/gated_downloads_jul_aug.json"))

SURF_ASSETS = {"Recreaire Brochure Download", "Future of Surfactants Presentation Download",
               "Keith ICIS 2025 Recreaire Presentation Download"}
POLY_ASSETS = {"PUD Applications Brochure", "Richard Europur 2026 Presentation",
               "UTech SEAsia", "Technobiz 2026 Presentation"}


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


def parse_contacts_block(text):
    m = re.search(r'const CONTACTS = \[', text)
    start = m.end() - 1
    depth = 0; i = start
    while True:
        ch = text[i]
        if ch == '[': depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0: end = i + 1; break
        i += 1
    block = text[start + 1:end - 1]
    contacts = []
    depth = 0; obj_start = None
    for idx, ch in enumerate(block):
        if ch == '{':
            if depth == 0: obj_start = idx
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                contacts.append(parse_one_contact(block[obj_start:idx + 1]))
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
    depth = 0; obj_start = None
    for idx, ch in enumerate(eng_block):
        if ch == '{':
            if depth == 0: obj_start = idx
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0: eng_entries.append(eng_block[obj_start:idx + 1])
    return {"name": field("name"), "initials": field("initials"), "title": field("title"),
            "company": field("company"), "email": field("email"), "note": field("note"),
            "status": field("status"), "engagements": eng_entries}


def format_contact(c):
    eng_lines = ",\n".join(f"      {e}" for e in c["engagements"])
    return (f'  {{name:"{c["name"]}",initials:"{c["initials"]}",title:"{c["title"]}",'
            f'company:"{c["company"]}",email:"{c["email"]}",note:"{c["note"]}",'
            f'status:"{c["status"]}",engagements:[\n{eng_lines}\n  ]}}')


def format_webform_entry(date, sources):
    month = date[:7]
    src = ", ".join(sources)
    return f'{{campaign_id:"web_form",month:"{month}",opens:0,clicks:0,web_form:true,date:"{date}",source:"{src}"}}'


def already_has_webform_date(engagements, date):
    return any(f'web_form:true,date:"{date}"' in e for e in engagements)


def build_august(product, july_path, out_path):
    text = open(july_path, encoding="utf8").read()
    contacts, start, end = parse_contacts_block(text)
    by_email = {c["email"].lower(): c for c in contacts}

    assets = SURF_ASSETS if product == "surfactants" else POLY_ASSETS
    aug_downloads_by_email = {}
    for r in downloads:
        if not r["date"].startswith("2026-08"):
            continue
        matches = [a for a in r["downloads"] if a in assets]
        if matches:
            aug_downloads_by_email.setdefault(r["email"].lower(), []).append((r["date"], matches))

    added, updated, skipped_no_company = [], [], []
    for email, entries in aug_downloads_by_email.items():
        c = by_email.get(email)
        if c is None:
            co, title, status = resolve_company_title_status(email, product)
            if co is None:
                skipped_no_company.append(email)
                continue
            name, initials = guess_name(email)
            eng = [format_webform_entry(date, matches) for date, matches in entries]
            c = {"name": name, "initials": initials, "title": title, "company": co,
                 "email": email, "note": "", "status": status, "engagements": eng}
            contacts.append(c)
            by_email[email] = c
            added.append((email, co, status))
        else:
            for date, matches in entries:
                if not already_has_webform_date(c["engagements"], date):
                    c["engagements"].append(format_webform_entry(date, matches))
                    updated.append((email, date))

    new_block_inner = "[\n" + ",\n".join(format_contact(c) for c in contacts) + "\n]"
    new_text = text[:start] + "const CONTACTS = " + new_block_inner + text[end:]

    # CONFIG updates: July -> August as current
    new_text = new_text.replace('const REPORT_PERIOD  = "July 2026";', 'const REPORT_PERIOD  = "August 2026";')
    new_text = new_text.replace('const CURRENT_MONTH  = "2026-07";', 'const CURRENT_MONTH  = "2026-08";')
    new_text = new_text.replace('const PREV_MONTH     = "2026-06";', 'const PREV_MONTH     = "2026-07";')

    # archive footer: add July link after June's
    july_file = "Econic_Surfactants_MQL_Dashboard_July2026.html" if product == "surfactants" else "Econic_Polyols_MQL_Dashboard_July2026.html"
    june_link_pat = re.compile(r'(<a class="archive-link" href="[^"]*June2026\.html">June 2026</a>)')
    new_text = june_link_pat.sub(lambda mm: mm.group(1) + f'\n  <a class="archive-link" href="{july_file}">July 2026</a>', new_text, count=1)

    open(out_path, "w", encoding="utf8").write(new_text)
    return len(contacts), added, updated, skipped_no_company


n1, added1, upd1, skip1 = build_august(
    "surfactants",
    f"{SP}/pipeline/Econic_Surfactants_MQL_Dashboard_July2026.html",
    f"{SP}/pipeline/Econic_Surfactants_MQL_Dashboard_LIVE_August2026.html")
print(f"SURFACTANTS August (new live): {n1} total contacts, {len(added1)} newly added, {len(upd1)} existing updates, {len(skip1)} skipped (no company match)")
for e, co, st in added1: print(f"   + {e} ({co}, {st})")
if skip1: print("   skipped:", skip1)

n2, added2, upd2, skip2 = build_august(
    "polyols",
    f"{SP}/pipeline/Econic_Polyols_MQL_Dashboard_July2026.html",
    f"{SP}/pipeline/Econic_Polyols_MQL_Dashboard_LIVE_August2026.html")
print(f"\nPOLYOLS August (new live): {n2} total contacts, {len(added2)} newly added, {len(upd2)} existing updates, {len(skip2)} skipped (no company match)")
for e, co, st in added2: print(f"   + {e} ({co}, {st})")
if skip2: print("   skipped:", skip2)
