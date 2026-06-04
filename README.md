# ClaimLenZ

AI-powered OPD insurance claim adjudication tool built as part of Plum's AI Automation Engineer intern assignment.

**Live demo:** [claimlenz.streamlit.app](https://sivamani-muraboyina-claimlenz.streamlit.app) &nbsp;·&nbsp; **Stack:** Python · Streamlit · Groq (Llama 3.3 70B) · pdfplumber

---

## Overview

ClaimLenZ automates the adjudication of Outpatient Department (OPD) insurance claims. Upload a prescription and bill PDF, fill in claim details, and the system returns a decision with a plain-English explanation — in under 10 seconds.

Decisions: **Approved · Rejected · Partial Approval · Manual Review**

---

## How it works

```
Upload documents + fill claim form
           ↓
Python: instant checks (amount < ₹500, submission > 30 days late)
           ↓
pdfplumber: extract text from PDFs
           ↓
Groq call 1 — extract structured fields
(doctor, registration number, diagnosis, medicines, bill amount)
           ↓
Python: validate doctor registration format (regex)
           ↓
Groq call 2 — adjudication decision
(applies 10+ policy rules in priority order)
           ↓
Python: calculate final approved amount
(per-claim cap → network discount or co-pay)
           ↓
Decision card with explanation + breakdown
```

Financial calculations — cap, co-pay, network discount — are done in Python, not by the LLM. This eliminates hallucination risk on any number that affects payout.

---

## Policy rules

| Rule | Value |
|------|-------|
| Per-claim cap | ₹5,000 |
| Annual limit | ₹50,000 |
| Minimum claim | ₹500 |
| Submission window | 30 days from treatment |
| Non-network hospital co-pay | 10% |
| Network hospital discount | 20% (Apollo, Fortis, Max, Manipal, Narayana) |
| Consultation sub-limit | ₹2,000 |
| Pharmacy sub-limit | ₹15,000 |
| Diagnostics sub-limit | ₹10,000 |
| Dental sub-limit | ₹10,000 |
| Alternative medicine sub-limit | ₹8,000 |

**Waiting periods** — Diabetes/Hypertension: 90 days · Maternity: 270 days · Pre-existing: 365 days · Joint replacement: 730 days

**Always excluded** — Cosmetic procedures, LASIK, weight loss/bariatric, IVF, HIV/AIDS treatment, vitamins (unless deficiency diagnosed), self-inflicted injuries, adventure sports injuries

**Pre-authorization required** — MRI and CT scans always require pre-auth, regardless of amount

---

## Test cases

| ID | Scenario | Claimed | Expected |
|----|----------|---------|----------|
| TC001 | Viral fever consultation | ₹1,500 | Approved ₹1,350 |
| TC002 | Root canal + teeth whitening | ₹12,000 | Partial ₹8,000 |
| TC003 | Gastroenteritis, bill over cap | ₹7,500 | Partial ₹4,500 |
| TC004 | No prescription uploaded | ₹2,000 | Rejected |
| TC005 | Diabetes, day 44 of policy | ₹3,000 | Rejected — waiting period |
| TC006 | Ayurvedic Panchakarma | ₹4,000 | Approved ₹4,000 |
| TC007 | MRI, no pre-authorization | ₹15,000 | Rejected |
| TC008 | 3 claims on the same day | ₹4,800 | Manual Review |
| TC009 | Weight loss treatment | ₹8,000 | Rejected |
| TC010 | Apollo Hospital (network) | ₹4,500 | Approved ₹3,600 |

Sample documents for TC001, TC002, TC005, TC009, TC010 are in `/Sample_docs`.

---

## Local setup

```bash
git clone https://github.com/sivamani-muraboyina/ClaimLenZ.git
cd ClaimLenZ
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
pip install -r requirements.txt
cp .env.example .env            # add your GROQ_API_KEY
streamlit run app.py
```

Get a free Groq API key at [console.groq.com](https://console.groq.com) — no credit card required.

---

## Assumptions

- Network discount and non-network co-pay are mutually exclusive
- Per-claim cap triggers partial approval, not full rejection
- AYUSH doctor registration format (`AYUR/STATE/NUMBER/YEAR`) is accepted alongside standard format (`KA/45678/2015`)
- Annual limit is not tracked across sessions (requires a database)
- Image uploads are accepted but text extraction only works on PDFs

---

## Potential improvements

- OCR for image documents (Tesseract / Google Vision API)
- Database for annual limit tracking across sessions (PostgreSQL / Supabase)
- Appeals workflow with a human-in-the-loop review queue
- Multi-language support for Hindi, Telugu, Tamil prescriptions
- Admin panel for policy configuration without code changes
