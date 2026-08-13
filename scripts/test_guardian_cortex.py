import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from server.guardian import evaluate_rules, analyze_message

def run_test():
    con = sqlite3.connect("cortex.db")
    rows = con.execute("SELECT msg_id, sender, subject, snippet FROM gmail_messages").fetchall()
    con.close()

    print(f"Loaded {len(rows)} emails from cortex.db gmail_messages.\n")

    safe_count = 0
    suspicious_count = 0
    threat_count = 0
    flagged = []

    for msg_id, sender, subject, snippet in rows:
        text = f"{subject} {snippet}"
        score, reasons = evaluate_rules(sender, text, subject)
        
        if score >= 75:
            verdict = "THREAT"
            threat_count += 1
            flagged.append((score, verdict, sender, subject, reasons))
        elif score >= 40:
            verdict = "SUSPICIOUS"
            suspicious_count += 1
            flagged.append((score, verdict, sender, subject, reasons))
        else:
            verdict = "SAFE"
            safe_count += 1

    print("=== VERDICT DISTRIBUTION ===")
    print(f"Total Emails Analyzed: {len(rows)}")
    print(f"SAFE (<40):         {safe_count} ({safe_count/len(rows)*100:.1f}%)")
    print(f"SUSPICIOUS (40-74): {suspicious_count}")
    print(f"THREAT (>=75):      {threat_count}")
    print("===========================\n")

    print("=== KNOWN RECRUITER / PLATFORM MAILS (FALSE-POSITIVE PROOF) ===")
    known_platforms = ["linkedin", "naukri", "devpost", "jobright", "humanjudge", "myemployment", "leetcode", "upwork", "cursor", "google", "toptal"]
    matched_platforms = 0
    false_positives = 0

    for msg_id, sender, subject, snippet in rows:
        sender_lower = (sender or "").lower()
        if any(kp in sender_lower for kp in known_platforms):
            matched_platforms += 1
            text = f"{subject} {snippet}"
            score, reasons = evaluate_rules(sender, text, subject)
            status = "PASS (SAFE)" if score < 40 else f"FAIL (SCORE {score})"
            if score >= 40:
                false_positives += 1
            print(f"[{status}] Sender: {sender[:40]} | Subject: {subject[:50]}")

    print(f"\nKnown Platform Emails Checked: {matched_platforms}")
    print(f"False Positives: {false_positives}\n")

    print("=== SYNTHETIC SCAM TEST SUITE ===")
    synthetic_scams = [
        ("hr.amaz0n-jobs@gmail.com", "Congratulations! Shortlisted for SDE Role", "Dear candidate, you are shortlisted for Amazon. Please pay ₹2,500 for the assessment portal fee at http://bit.ly/amz-portal."),
        ("recruiter@tcs-jobs-portal.co.in", "TCS Interview Invitation", "Kindly deposit a refundable security deposit of Rs 1500 for the interview equipment processing fee."),
        ("support@sbi-update-kyc.com", "URGENT: Account Suspension Notice", "Your SBI netbanking will be blocked today. Click here to update KYC immediately or share OTP."),
        ("cloud-hiring@gmail.com", "Job Offer: AI Engineer at Google", "We are pleased to offer you the AI Engineer position at Google India. Please reply with your resume.")
    ]

    for sender, subject, body in synthetic_scams:
        text = f"{subject} {body}"
        score, reasons = evaluate_rules(sender, text, subject)
        if score >= 75:
            verdict = "THREAT"
        elif score >= 40:
            verdict = "SUSPICIOUS"
        else:
            verdict = "SAFE"
        print(f"[{verdict} - Score {score}] Sender: {sender}")
        print(f"  Subject: {subject}")
        print(f"  Reasons: {'; '.join(reasons)}\n")

    print("=== FLAGGED REAL EMAILS (TOP 5) ===")
    flagged.sort(key=lambda x: x[0], reverse=True)
    if not flagged:
        print("No emails were flagged as SUSPICIOUS or THREAT.")
    else:
        for score, verdict, sender, subject, reasons in flagged[:5]:
            print(f"Score {score} [{verdict}] | Sender: {sender} | Subject: {subject}")
            print(f"  Reason: {'; '.join(reasons)}\n")

if __name__ == "__main__":
    run_test()
