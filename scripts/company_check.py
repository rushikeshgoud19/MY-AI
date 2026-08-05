"""Produce a sourced counterparty report for one company.

Usage:
    python scripts/company_check.py uk 11998471
    python scripts/company_check.py au 33051775556
    python scripts/company_check.py in U74120MH2011PTC220022 [slug]

Prints markdown to stdout. Every field carries the URL it came from; anything the
register does not show is listed under "Could not verify" rather than omitted.

Durations are recomputed here from the dates on the record. That is deliberate: the
Indian provider's own "age of company" figure was wrong on 3 of 3 companies tested
(docs/company/demo/sample-report.md), so no displayed duration is trusted.

ASCII output only -- the Windows console this runs on is cp1252 and non-ASCII
stdout kills the run mid-report.
"""

import calendar
import html
import re
import sys
import urllib.request
from datetime import date

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
TIMEOUT = 30

SOURCES = {
    "uk": ("Companies House",
           "https://find-and-update.company-information.service.gov.uk/company/{id}",
           "the official UK register -- not a mirror"),
    "au": ("Australian Business Register",
           "https://abr.business.gov.au/ABN/View?abn={id}",
           "the official Australian register -- not a mirror"),
    "in": ("ZaubaCorp",
           "https://www.zaubacorp.com/company/{slug}/{id}",
           "a third-party MIRROR of MCA data; mca.gov.in itself returns HTTP 403"),
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "replace")


def text_of(raw):
    t = re.sub(r"(?is)<(script|style|nav|footer)[^>]*>.*?</\1>", " ", raw)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t))


def ascii_only(s):
    return s.encode("ascii", "replace").decode("ascii")


def grab(t, pattern, group=1):
    m = re.search(pattern, t, re.I)
    return m.group(group).strip() if m else None


def elapsed(start, end):
    """Calendar difference. Returns 'Xy Ym Zd', or None if start is None."""
    if not start:
        return None
    y, m, d = end.year - start.year, end.month - start.month, end.day - start.day
    if d < 0:
        m -= 1
        pm = (end.month - 1) or 12
        py = end.year if end.month > 1 else end.year - 1
        d += calendar.monthrange(py, pm)[1]
    if m < 0:
        y -= 1
        m += 12
    return "%dy %dm %dd" % (y, m, d)


MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
# Registers mix "01 Nov 1999" and "1 November 1999". Missing the abbreviations made
# durations vanish silently, which is the worst possible failure here -- a missing
# row reads as "not applicable" rather than "the parser broke".
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})


def parse_date(s):
    """'16 May 2019' or '2011-07-21' -> date. None if unparseable."""
    if not s:
        return None
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if m and m.group(2).lower() in MONTHS:
        return date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def check_uk(cid, url):
    t = text_of(fetch(url))
    f = {
        "Company name": grab(t, r"Company Overview for ([^(]{2,80})\("),
        "Company number": cid,
        "Status": grab(t, r"Company status\s*(.{3,70}?)\s*Company type"),
        "Company type": grab(t, r"Company type\s*(.{3,50}?)\s*Incorporated"),
        "Incorporated": grab(t, r"Incorporated on\s*(\d{1,2} \w+ \d{4})"),
        "Registered office": grab(t, r"Registered office address\s*(.{5,120}?)\s*Company status"),
        "Nature of business (SIC)": grab(t, r"Nature of business \(SIC\)\s*(.{3,90}?)\s*(?:Tell us|Previous)"),
    }
    flags, unverified = [], []

    if re.search(r"strike off", t, re.I) and f["Status"]:
        flags.append("The register shows a **proposal to strike off**. Note that the "
                     "status field can still read 'Active' alongside it.")

    acc = grab(t, r"Accounts overdue\s*(.{3,90}?)\s*(?:Warning|Confirmation)")
    if acc:
        due = parse_date(re.sub(r".*due by", "", acc))
        first = "first" if re.search(r"first accounts", acc, re.I) else "latest"
        over = elapsed(due, date.today())
        flags.append("**Accounts overdue** -- %s. Overdue by **%s**.%s"
                     % (acc, over or "unknown",
                        "  These are the company's FIRST accounts: none have ever been filed."
                        if first == "first" else ""))
        unverified.append(("Any accounts, turnover or financial position",
                           "None filed -- nothing exists to retrieve"))

    if re.search(r"Confirmation statement overdue", t, re.I):
        cs = grab(t, r"Next statement date\s*(.{3,60}?)\s*Last statement")
        due = parse_date(re.sub(r".*due by", "", cs or ""))
        flags.append("**Confirmation statement overdue** -- %s. Overdue by **%s**."
                     % (cs or "date not parsed", elapsed(due, date.today()) or "unknown"))

    inc = parse_date(f["Incorporated"])
    if inc:
        f["Age (recomputed)"] = elapsed(inc, date.today())

    unverified += [
        ("Directors and persons of significant control",
         "Available on the register; deliberately excluded -- named individuals"),
        ("Whether the company trades, has staff, or a website", "No source consulted"),
        ("Charges, insolvency history or litigation", "Out of scope of this check"),
    ]
    return f, flags, unverified


def check_au(cid, url):
    t = text_of(fetch(url))
    f = {
        "Entity name": grab(t, r"Entity name:\s*(.{2,80}?)\s*ABN status"),
        "ABN": cid,
        "ABN status": grab(t, r"ABN status:\s*(.{2,60}?)\s*Entity type"),
        "Entity type": grab(t, r"Entity type:\s*(.{2,60}?)\s*Goods"),
        "GST": grab(t, r"Goods & Services Tax \(GST\):\s*(.{2,60}?)\s*Main business"),
        "Main business location": grab(t, r"Main business location:\s*([A-Z]{2,3}\s*\d{4})"),
        "ABN last updated": grab(t, r"ABN last updated:\s*(\d{1,2} \w+ \d{4})"),
        "Record extracted": grab(t, r"Record extracted:\s*(\d{1,2} \w+ \d{4})"),
    }
    flags = []
    active_from = parse_date(re.sub(r".*from", "", f["ABN status"] or ""))
    if active_from:
        f["ABN active for (recomputed)"] = elapsed(active_from, date.today())
    stale = parse_date(f["ABN last updated"])
    if stale:
        f["Record last updated (recomputed)"] = elapsed(stale, date.today()) + " ago"
        if (date.today() - stale).days > 730:
            flags.append("The ABN record has not been updated in over two years. "
                         "That is not itself a finding, but it limits how current "
                         "any of the above is.")
    if f["ABN status"] and "cancel" in f["ABN status"].lower():
        flags.append("**ABN is cancelled.**")
    unverified = [
        ("Company officers / directors",
         "ABN Lookup does not carry them; ASIC does, and was not consulted"),
        ("Financial position", "Not published via ABN Lookup"),
        ("Whether the entity trades or has staff", "No source consulted"),
        ("ACN-level company status (ASIC)", "Not checked -- ABN Lookup is not ASIC"),
    ]
    return f, flags, unverified


def check_in(cid, url):
    t = text_of(fetch(url))
    f = {
        "Company name": grab(t, r"Company Information\s*(.{3,90}?)\s*\(CIN"),
        "CIN": cid,
        "Status": grab(t, r"Status\s*(.{3,40}?)\s*ROC"),
        "ROC": grab(t, r"ROC\s+ROC\s+([A-Za-z]+(?:\s+[A-Za-z]+)??)\s+Registration"),
        "Class": grab(t, r"Class of Company\s*(\w+)"),
        "Incorporated": grab(t, r"Date of Incorporation\s*(\d{4}-\d{2}-\d{2})"),
        "Activity": grab(t, r"NIC Description:\s*(.{5,90}?)\s*(?:\[|Registered)"),
        "Data as on": grab(t, r"As on:\s*(\d{4}-\d{2}-\d{2})"),
        "Last AGM": grab(t, r"Last Annual General Meeting\s*(\d{4}-\d{2}-\d{2})"),
        "Last balance sheet": grab(t, r"Date of Last Filed Balance Sheet\s*(\d{4}-\d{2}-\d{2})"),
    }
    flags = []
    inc = parse_date(f["Incorporated"])
    if inc:
        f["Age (recomputed)"] = elapsed(inc, date.today())
    shown = grab(t, r"Age of Company\s*(.{3,40}?)\s*Activity")
    if shown:
        f["Age as DISPLAYED by source"] = shown + "  <- not trusted; see note"
        flags.append("The source displays its own 'age of company'. It was wrong on "
                     "3 of 3 companies tested, so the recomputed figure above is "
                     "the one to use.")
    if f["Status"] and "strike" in f["Status"].lower():
        flags.append("**Status is Strike Off.**")
    agm = parse_date(f["Last AGM"])
    if agm:
        gap = elapsed(agm, date.today())
        f["Since last AGM (recomputed)"] = gap
        if (date.today() - agm).days > 550:
            flags.append("**Last AGM was %s ago.** Indian companies are generally "
                         "required to hold one annually; a gap this size is worth a "
                         "question." % gap)
    unverified = [
        ("MCA as primary source", "mca.gov.in returns HTTP 403. This report rests on "
                                  "a MIRROR of MCA data, not MCA itself"),
        ("Email address", "Redacted at source"),
        ("Financials / total assets", "Behind the provider's paywall"),
        ("Directors", "Retrievable; deliberately excluded -- named individuals"),
        ("Whether a strike-off was appealed or the company restored", "Not checked"),
    ]
    return f, flags, unverified


CHECKS = {"uk": check_uk, "au": check_au, "in": check_in}


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in CHECKS:
        print(__doc__)
        return 1
    juris, cid = sys.argv[1], sys.argv[2]
    slug = sys.argv[3] if len(sys.argv) > 3 else "company"
    name, tmpl, caveat = SOURCES[juris]
    url = tmpl.format(id=cid, slug=slug)

    try:
        fields, flags, unverified = CHECKS[juris](cid, url)
    except Exception as e:
        print("FETCH FAILED: %s\n\nCould not reach %s. No report produced -- a report "
              "of blanks is worse than none." % (e, url))
        return 2

    out = []
    title = fields.get("Company name") or fields.get("Entity name") or cid
    out.append("# Counterparty check -- %s" % title)
    out.append("")
    out.append("Checked %s - source: **%s** (%s)" % (date.today().isoformat(), name, caveat))
    out.append("")
    if flags:
        out.append("## What stands out")
        out.append("")
        for fl in flags:
            out.append("- " + fl)
        out.append("")
    out.append("## What the record says")
    out.append("")
    out.append("| Field | Value |")
    out.append("|---|---|")
    for k, v in fields.items():
        if v:
            out.append("| %s | %s |" % (k, v))
    out.append("")
    out.append("Source: <%s>" % url)
    out.append("")
    out.append("All durations above were recomputed from the dates on the record, "
               "not copied from any displayed summary.")
    out.append("")
    out.append("## Could not verify")
    out.append("")
    out.append("| Item | Why not |")
    out.append("|---|---|")
    for item, why in unverified:
        out.append("| %s | %s |" % (item, why))
    out.append("")
    out.append("## What this is not")
    out.append("")
    out.append("Not a credit opinion, not a KYC or compliance determination, not an "
               "accusation, and not advice on whether to transact. It reports what the "
               "public register says and what it does not. Companies only -- never "
               "private individuals.")
    print(ascii_only("\n".join(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
