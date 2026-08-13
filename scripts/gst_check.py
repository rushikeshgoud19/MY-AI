"""Turn a pasted GST filing table into a sourced compliance report.

The GST portal is behind a CAPTCHA, which we do not bypass. A human opens
services.gst.gov.in/services/searchtp, solves it, clicks SHOW FILING TABLE, and
pastes the rows here. The CAPTCHA blocks automation; it does not block the work.

Usage:
    python scripts/gst_check.py <gstin> <monthly|qrmp> [--name "LEGAL NAME"] < paste.txt

Paste format - one row per line, tab or multi-space separated, as copied from the
portal. Return type is inferred from a heading line containing GSTR3B / GSTR-1:

    Filing details for GSTR3B
    2026-2027   June    20/07/2026  Filed
    2026-2027   May     19/06/2026  Filed
    Filing details for GSTR-1/IFF
    2026-2027   June    10/07/2026  Filed

Statutory due dates (monthly): GSTR-1 11th, GSTR-3B 20th of the following month.
QRMP: GSTR-1 13th, GSTR-3B 22nd or 24th depending on state - the script uses 22nd
and prints the caveat rather than guessing the state.

ASCII output only; the Windows console here is cp1252.
"""

import calendar
import re
import sys
from datetime import date, timedelta

DUE = {  # (return, frequency) -> day of month following the period
    ("GSTR-3B", "monthly"): 20,
    ("GSTR-1", "monthly"): 11,
    ("GSTR-3B", "qrmp"): 22,   # 22nd or 24th by state - caveated in output
    ("GSTR-1", "qrmp"): 13,
}

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})

# Indian FY runs April-March: Apr-Dec fall in the first year, Jan-Mar in the second.
def period_end(fy_start_year, month_no):
    year = fy_start_year if month_no >= 4 else fy_start_year + 1
    return date(year, month_no, calendar.monthrange(year, month_no)[1])


def due_date(period_last_day, ret, freq):
    day = DUE[(ret, freq)]
    y, m = period_last_day.year, period_last_day.month + 1
    if m > 12:
        m = 1
        y += 1
    return date(y, m, min(day, calendar.monthrange(y, m)[1]))


def parse(lines):
    """-> [ {ret, fy, month_no, month_name, filed_on, status, period_end} ]"""
    rows, ret = [], None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if re.search(r"GSTR-?3B", line, re.I) and not re.search(r"\d{2}/\d{2}/\d{4}", line):
            ret = "GSTR-3B"
            continue
        if re.search(r"GSTR-?1", line, re.I) and not re.search(r"\d{2}/\d{2}/\d{4}", line):
            ret = "GSTR-1"
            continue
        m = re.match(
            r"(\d{4})\s*[-/]\s*\d{4}\s+([A-Za-z]+)\s+(?:(\d{2}/\d{2}/\d{4})\s+)?(\w+)",
            line)
        if not m or not ret:
            continue
        fy, mon, filed, status = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
        if mon not in MONTHS:
            continue
        mn = MONTHS[mon]
        d = None
        if filed:
            dd, mm, yy = filed.split("/")
            d = date(int(yy), int(mm), int(dd))
        rows.append(dict(ret=ret, fy=int(fy), month_no=mn, month_name=mon.title(),
                         filed_on=d, status=status,
                         period_end=period_end(int(fy), mn)))
    return rows


def analyse(rows, freq, today):
    late, gaps = [], []
    by_ret = {}
    for r in rows:
        r["due"] = due_date(r["period_end"], r["ret"], freq)
        by_ret.setdefault(r["ret"], []).append(r)

    # Only reason about financial years actually queried. A period in an FY the
    # user never pulled is not "unfiled" - it is unknown, and reporting it as a
    # gap would be inventing a finding out of absent data.
    fys = {r["fy"] for r in rows}
    horizon = min(today, date(max(fys) + 1, 3, 31))
    floor = date(min(fys), 4, 30)

    for ret, rs in by_ret.items():
        rs.sort(key=lambda r: r["period_end"])
        for r in rs:
            if r["filed_on"] and r["status"].lower().startswith("filed"):
                delta = (r["filed_on"] - r["due"]).days
                r["days_late"] = delta
                if delta > 0:
                    late.append(r)
            else:
                r["days_late"] = None

        # gap detection: only for periods already past due
        if rs:
            seen = {(r["period_end"].year, r["period_end"].month) for r in rs}
            cur = rs[0]["period_end"]
            last = rs[-1]["period_end"]
            while cur <= last:
                if (cur.year, cur.month) not in seen and cur >= floor:
                    d = due_date(cur, ret, freq)
                    if d < horizon:
                        gaps.append((ret, cur, d))
                nxt = cur + timedelta(days=1)
                cur = date(nxt.year, nxt.month,
                           calendar.monthrange(nxt.year, nxt.month)[1])

        # missing recent periods after the last row
        if rs:
            cur = rs[-1]["period_end"]
            while True:
                nxt = cur + timedelta(days=1)
                cur = date(nxt.year, nxt.month,
                           calendar.monthrange(nxt.year, nxt.month)[1])
                d = due_date(cur, ret, freq)
                if d >= horizon or cur > horizon:
                    break
                gaps.append((ret, cur, d))
    return by_ret, late, gaps, sorted(fys), horizon


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    gstin, freq = sys.argv[1].strip().upper(), sys.argv[2].strip().lower()
    if freq not in ("monthly", "qrmp"):
        print("frequency must be 'monthly' or 'qrmp' (portal: SHOW RETURN FILING FREQUENCY)")
        return 1
    name = None
    if "--name" in sys.argv:
        name = sys.argv[sys.argv.index("--name") + 1]

    rows = parse(sys.stdin.read().splitlines())
    if not rows:
        print("No filing rows parsed. Paste the table exactly as copied from the "
              "portal, including the 'Filing details for GSTR3B' heading lines.\n"
              "No report produced - a report of blanks is worse than none.")
        return 2

    today = date.today()
    by_ret, late, gaps, fys, horizon = analyse(rows, freq, today)

    o = []
    o.append("# GST compliance check -- %s" % (name or gstin))
    o.append("")
    o.append("GSTIN: **%s** | Filing frequency: **%s** | Checked %s"
             % (gstin, freq, today.isoformat()))
    o.append("")
    o.append("Financial year(s) queried: **%s**. Nothing outside these years is "
             "reasoned about." % ", ".join("%d-%d" % (f, f + 1) for f in fys))
    o.append("")
    o.append("Source: GST portal, Search Taxpayer -> Show Filing Table "
             "(<https://services.gst.gov.in/services/searchtp>). Public record, "
             "read directly from the portal.")
    o.append("")

    # headline
    o.append("## What stands out")
    o.append("")
    if not late and not gaps:
        o.append("- **Nothing adverse found in the periods shown.** Every return "
                 "listed was filed, and none was filed after its statutory due "
                 "date. That is a result, not an absence of one.")
    if gaps:
        streak = len(gaps)
        o.append("- **%d return period(s) are past their due date with no filing "
                 "shown.** This is the condition that removes the invoices from "
                 "your GSTR-2B and puts input tax credit at risk." % streak)
        if streak >= 6:
            o.append("- **Six or more missing periods.** This is the threshold at "
                     "which invoices stop appearing in GSTR-2B altogether.")
    if late:
        worst = max(late, key=lambda r: r["days_late"])
        o.append("- **%d return(s) filed after the due date**, the worst by "
                 "**%d days** (%s %s, due %s, filed %s)."
                 % (len(late), worst["days_late"], worst["ret"], worst["month_name"],
                    worst["due"].isoformat(), worst["filed_on"].isoformat()))
    o.append("")

    for ret in sorted(by_ret):
        o.append("## %s" % ret)
        o.append("")
        o.append("| Tax period | Due | Filed | Status | Days late |")
        o.append("|---|---|---|---|---|")
        for r in by_ret[ret]:
            dl = r["days_late"]
            dls = "-" if dl is None else ("on time" if dl <= 0 else "**+%d**" % dl)
            o.append("| %s %d | %s | %s | %s | %s |"
                     % (r["month_name"], r["period_end"].year, r["due"].isoformat(),
                        r["filed_on"].isoformat() if r["filed_on"] else "not shown",
                        r["status"], dls))
        o.append("")

    if gaps:
        o.append("## Periods past due with no filing shown")
        o.append("")
        o.append("| Return | Tax period | Was due |")
        o.append("|---|---|---|")
        for ret, pe, d in sorted(gaps, key=lambda g: (g[0], g[1])):
            o.append("| %s | %s %d | %s |"
                     % (ret, calendar.month_name[pe.month], pe.year, d.isoformat()))
        o.append("")

    o.append("## Could not verify")
    o.append("")
    o.append("| Item | Why not |")
    o.append("|---|---|")
    o.append("| Whether a missing period was filed late and simply not shown | "
             "The table reflects what the portal returned for the financial years "
             "queried. **A blank is not proof of non-filing** |")
    o.append("| Periods outside the financial year(s) pulled | Only the years queried are "
             "covered. Nothing is claimed about any other year |")
    o.append("| Whether tax was actually paid | The table shows that a return was "
             "**filed**, not that liability was discharged |")
    o.append("| Whether your specific invoices appear in your GSTR-2B | That is in "
             "your own GST login, not in the public record |")
    if freq == "qrmp":
        o.append("| Exact QRMP GSTR-3B due date | **22nd or 24th by state.** This "
                 "report uses the 22nd. Any lateness of 1-2 days may be an artefact "
                 "of that, and is flagged rather than asserted |")
    o.append("")
    o.append("## What this is not")
    o.append("")
    o.append("Not tax advice, not a compliance opinion, and not a recommendation to "
             "transact or not transact. It reports what the public GST record shows "
             "and what it does not. Due dates used: GSTR-1 %dth, GSTR-3B %dth."
             % (DUE[("GSTR-1", freq)], DUE[("GSTR-3B", freq)]))
    print("\n".join(o).encode("ascii", "replace").decode("ascii"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
