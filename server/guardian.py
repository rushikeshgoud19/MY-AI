"""
Z1 GUARDIAN — Fraud Shield for Mizune (Phase Z1).

Protects Master Rushi from fake recruiter scams, UPI phishing, OTP theft,
and fraudulent registration fee demands in Gmail and WhatsApp.

Principles:
1. PRECISION OVER RECALL: False positives are strictly worse than misses.
2. Law 4: Warn only. Never auto-delete, auto-reply to senders, block, or click links.
3. Specificity: Warnings state exact reasons, never generic "suspicious".
4. Zero Attacker HTTP Fetch: Attacker-controlled links are analyzed statically.
"""

import os
import re
import sqlite3
import time
from typing import Dict, Any, List, Tuple
from .config import log_info, mizune_now

DB_PATH = os.path.join(".data", "guardian.db")

HIGH_TRUST_DOMAINS = {
    "linkedin.com", "em.linkedin.com", "security-noreply@linkedin.com",
    "naukri.com", "naukricampus.com", "devpost.com", "jobright.ai",
    "humanjudge.com", "myemployment.com", "leetcode.com", "upwork.com",
    "cursor.com", "mail.cursor.com", "google.com", "github.com",
    "toptal.com", "cerebralvalley.ai", "ollama.com", "xbox.com",
    "e.xbox.com", "usesprout.com", "vibeprospect.com", "microsoft.com",
    "amazon.com", "apple.com", "remote-rocketship.com"
}

GENERIC_MAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "mail.ru", "protonmail.com"}

MAJOR_CORPS = ["amazon", "tcs", "tata consultancy", "infosys", "wipro", "google", "microsoft", "accenture", "cognizant", "deloitte", "hcl", "tech mahindra"]

SHORTENER_DOMAINS = ["bit.ly", "tinyurl.com", "is.gd", "cutt.ly", "t.co", "rb.gy", "goo.gl", "ow.ly"]


def _db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS threats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel TEXT,
        sender TEXT,
        excerpt TEXT,
        verdict TEXT,
        confidence REAL,
        reason TEXT,
        seen_at TEXT,
        action_taken TEXT
    )""")
    return con


def _extract_domain(email_str: str) -> str:
    if not email_str:
        return ""
    m = re.search(r"@([\w\.-]+\.[\w]+)", email_str.lower())
    if m:
        return m.group(1).strip()
    return ""


def evaluate_rules(sender: str, text: str, subject: str = "") -> Tuple[int, List[str]]:
    """Evaluate deterministic fraud rules over email/message content."""
    score = 0
    reasons = []
    
    combined = f"{subject} {text}".strip()
    combined_lower = combined.lower()
    sender_lower = (sender or "").lower()
    domain = _extract_domain(sender_lower)

    # Check high trust domain exemption
    is_high_trust = any(domain == d or domain.endswith("." + d) or d in sender_lower for d in HIGH_TRUST_DOMAINS)

    # ── Rule 1: Candidate Fee Demand (The Cardinal Employer Rule) ──
    # A legitimate employer NEVER asks a job candidate to pay money or a deposit for a job/assessment.
    fee_patterns = [
        r"\b(pay|deposit|transfer|send)\b.*?\b(₹|\$|rs\.?|inr|usd|\d{3,5})\b.*?\b(registration|assessment|portal|security|interview|processing|fee|deposit)",
        r"\b(registration|assessment|portal|security|refundable|processing)\s+(fee|deposit|charge|cost)\b",
        r"\b(pay|deposit)\s+(₹|\$|rs\.?|inr|\d+)\b",
        r"\brefundable\s+security\s+deposit\b",
        r"\bpay\s+for\s+(the\s+)?(assessment|portal|interview|offer\s+letter|training)\b"
    ]
    
    fee_matched = False
    for pat in fee_patterns:
        if re.search(pat, combined_lower, re.IGNORECASE):
            fee_matched = True
            break

    # CONTEXT GATE (added after a real false positive 2026-07-23: his COLLEGE asking
    # for an exam fee scored 80/THREAT). The cardinal rule is "an EMPLOYER never asks a
    # CANDIDATE for money" — it is NOT "nobody may ask for money". Legitimate fee
    # demands are everywhere in a student's inbox (exam/tuition/hostel/utility bills).
    # So the fee rule only fires in a HIRING context, and never from an institution.
    JOB_CONTEXT = ("shortlist", "selected", "candidate", "interview", "recruit", "hiring",
                   "job", "position", "vacancy", "offer letter", "placement", "onboarding",
                   "work from home", "part time", "internship", "assessment portal")
    INSTITUTION_TLDS = (".ac.in", ".edu", ".edu.in", ".gov.in", ".nic.in", ".ac.uk")
    in_job_context = any(k in combined_lower for k in JOB_CONTEXT)
    from_institution = any(domain.endswith(t) for t in INSTITUTION_TLDS)

    if fee_matched and from_institution:
        fee_matched = False          # colleges/universities legitimately charge fees
    if fee_matched and not in_job_context:
        fee_matched = False          # a bill is not a scam; needs the hiring frame

    if fee_matched:
        score += 80
        reasons.append("Demands candidate payment, registration fee, or security deposit for a job/assessment")

    # ── Rule 2: Corporate Recruiter Impersonation via Generic Email ──
    if not fee_matched and domain in GENERIC_MAIL_DOMAINS:
        for corp in MAJOR_CORPS:
            if corp in combined_lower and any(w in combined_lower for w in ["shortlisted", "selected", "interview", "job offer", "hiring"]):
                score += 40
                reasons.append(f"Claims to represent {corp.title()} but sent from generic free email (@{domain})")
                break

    # Lookalike domains (e.g. amaz0n-jobs, tcs-careers-portal)
    if not is_high_trust and domain and not domain in GENERIC_MAIL_DOMAINS:
        for corp in ["amaz0n", "tcs-job", "naukri-hr", "infosys-hire"]:
            if corp in domain:
                score += 50
                reasons.append(f"Sent from suspicious lookalike domain (@{domain})")
                break

    # ── Rule 3: Phishing, OTP, Account Block & KYC Urgency ──
    otp_pattern = r"\b(share|enter|send|provide)\b.*?\b(otp|pin|cvv|password)\b"
    kyc_pattern = r"\b(kyc|account|bank)\b.*?\b(block|suspend|expire|deactivate|freeze)\b|\bupdate\s+kyc\b"
    
    if re.search(otp_pattern, combined_lower):
        score += 80
        reasons.append("Requests secret OTP, PIN, password, or credential sharing")
    elif re.search(kyc_pattern, combined_lower):
        score += 60
        reasons.append("Urgent threat of account block or expired KYC requiring action")

    # ── Rule 4: Shortened URL in Financial / Urgent Context ──
    if not is_high_trust:
        for s_dom in SHORTENER_DOMAINS:
            if s_dom in combined_lower and any(kw in combined_lower for kw in ["pay", "kyc", "verify", "urgent", "offer", "shortlisted"]):
                score += 30
                reasons.append(f"Contains shortened URL ({s_dom}) in an urgent or job/financial context")
                break

    # ── High Trust Mitigation ──
    # If sent by trusted platforms (LinkedIn, Naukri, Devpost, etc.) and NO fee demand was detected,
    # suppress generic keyword hits to prevent false positives.
    if is_high_trust and not fee_matched:
        score = 0
        reasons = []

    return score, reasons


def analyze_message(channel: str, sender: str, text: str, subject: str = "") -> Dict[str, Any]:
    """Analyze incoming email/message, compute threat score, and handle escalation."""
    try:
        score, reasons = evaluate_rules(sender, text, subject)
        
        if score >= 75:
            verdict = "THREAT"
            confidence = min(0.85 + (score / 500.0), 0.99)
        elif score >= 40:
            verdict = "SUSPICIOUS"
            confidence = 0.70
        else:
            verdict = "SAFE"
            confidence = 0.95

        reason_str = "; ".join(reasons) if reasons else "No fraud indicators detected"
        excerpt = f"{subject}: {text}" if subject else text
        excerpt_clean = excerpt.strip()[:200].replace("\n", " ")
        
        action_taken = "NONE"
        
        con = _db()
        cursor = con.cursor()
        
        # Immediate alert only for score >= 75 (THREAT)
        if verdict == "THREAT":
            action_taken = "ALERTED"
            try:
                from server.commands import whatsapp_automation
                alert_text = (
                    f"⚠️ GUARDIAN FRAUD WARNING ⚠️\n"
                    f"Master, a suspicious message was flagged:\n"
                    f"• Channel: {channel.upper()}\n"
                    f"• Sender: {sender[:50]}\n"
                    f"• Reason: {reason_str}\n"
                    f"• Excerpt: \"{excerpt_clean[:120]}\"\n"
                    f"\nRule: Legitimate employers and banks NEVER ask for money, deposits, or OTPs!"
                )
                whatsapp_automation("Master", alert_text)
                log_info(f"[GUARDIAN] High threat alerted to Master: {reason_str}")
            except Exception as e:
                log_info(f"[GUARDIAN] Alert dispatch failed: {e}")
        elif verdict == "SUSPICIOUS":
            action_taken = "LOGGED"
            log_info(f"[GUARDIAN] Logged suspicious item ({score}/100): {reason_str}")

        cursor.execute("""INSERT INTO threats 
            (channel, sender, excerpt, verdict, confidence, reason, seen_at, action_taken)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (channel, sender, excerpt_clean, verdict, confidence, reason_str, mizune_now().isoformat(), action_taken))
        con.commit()
        con.close()

        return {
            "verdict": verdict,
            "score": score,
            "confidence": confidence,
            "reason": reason_str,
            "action_taken": action_taken
        }
    except Exception as e:
        log_info(f"[GUARDIAN] Exception during analysis: {e}")
        return {"verdict": "SAFE", "score": 0, "confidence": 0.0, "reason": f"Error: {e}", "action_taken": "NONE"}


def investigate_query(query: str) -> str:
    """Manual tool handler for 'check_legit' command."""
    if not query or not query.strip():
        return "Please provide an email snippet, message, or URL to analyze, Master."
    
    score, reasons = evaluate_rules("manual_query", query, "")
    
    if score >= 75:
        verdict = "🚨 HIGH THREAT (SCAM / FRAUD DETECTED)"
    elif score >= 40:
        verdict = "⚠️ SUSPICIOUS (PROCEED WITH CAUTION)"
    else:
        verdict = "✅ LIKELY SAFE"

    reason_text = "\n".join(f"- {r}" for r in reasons) if reasons else "- No obvious fraud markers found."
    
    return (
        f"🛡️ GUARDIAN ANALYSIS REPORT 🛡️\n\n"
        f"Verdict: {verdict}\n"
        f"Risk Score: {score}/100\n\n"
        f"Key Findings:\n{reason_text}\n\n"
        f"Mizune's Safety Advice:\n"
        f"• Never pay any deposit, portal fee, or assessment fee for a job.\n"
        f"• Never share OTPs, PINs, or bank passwords.\n"
        f"• Verify recruiters directly on official company career pages."
    )


def get_recent_threats(limit: int = 10) -> List[Tuple]:
    """Retrieve recent threats for reports or briefing incorporation."""
    if not os.path.exists(DB_PATH):
        return []
    try:
        con = _db()
        rows = con.execute("SELECT id, channel, sender, verdict, reason, seen_at FROM threats WHERE verdict IN ('THREAT', 'SUSPICIOUS') ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        con.close()
        return rows
    except Exception:
        return []
