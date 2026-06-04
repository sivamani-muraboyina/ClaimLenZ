# 🏥 ClaimLenZ — OPD Claim Adjudication Tool

> AI-powered insurance claim processing built as part of Plum's AI Automation Engineer intern assignment.

![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35-red?style=flat-square&logo=streamlit)
![Groq](https://img.shields.io/badge/LLM-Groq%20LLaMA%203.3%2070B-orange?style=flat-square)
![pdfplumber](https://img.shields.io/badge/PDF-pdfplumber-green?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)

**Live demo:** [claimlenz-for-plum-by-siva.streamlit.app](https://claimlenz-for-plum-by-siva.streamlit.app)

---

## 📸 App Preview

### Claim Form
![ClaimLenZ Home](docs/screenshot_home.png)

### Adjudication Result
![ClaimLenZ Result](docs/screenshot_result.png)

---

## ✨ Features

- 📄 **PDF Document Parsing** — Extracts text from prescriptions and bills via pdfplumber
- 🔍 **Two-Stage LLM Pipeline** — Stage 1 extracts structured fields, Stage 2 adjudicates
- 🛡️ **Deterministic Rule Engine** — Python enforces all financial limits (no LLM hallucination on amounts)
- 🏥 **Network Hospital Detection** — Auto-applies 20% discount for Apollo, Fortis, Max, Manipal, Narayana
- ⏳ **Waiting Period Enforcement** — Diabetes, hypertension, pre-existing, maternity
- 🚨 **Fraud Detection** — Flags suspicious patterns for manual review
- 📊 **Confidence Scoring** — Low-confidence decisions auto-route to human review
- 🧾 **Session History** — Tracks all claims processed in the current session

---

## 🏗️ Architecture

```
Upload documents + fill claim form
           ↓
Python: instant checks
(amount < ₹500 or submission > 30 days late → instant reject)
           ↓
pdfplumber: extract text from PDFs
           ↓
Groq call 1 — LLaMA 3.3 70B
Extract structured fields:
doctor name, reg number, diagnosis, medicines, bill amount
           ↓
Python: validate doctor registration format (regex)
           ↓
Groq call 2 — LLaMA 3.3 70B
Adjudication decision following 10+ policy rules in priority order
(APPROVED / REJECTED / PARTIAL / MANUAL_REVIEW)
           ↓
Python: calculate final approved amount
per-claim cap → network discount or co-pay
           ↓
Decision card with plain-English explanation + breakdown
```

> Financial calculations — cap, co-pay, network discount — are done in Python, not by the LLM. This eliminates hallucination risk on any number that affects payout.

---

## 🧪 Test Cases

| ID | Scenario | Claimed | Expected |
|----|----------|---------|----------|
| TC001 | Viral fever consultation | ₹1,500 | ✅ Approved ₹1,350 |
| TC002 | Root canal + teeth whitening | ₹12,000 | ⚠️ Partial ₹8,000 |
| TC003 | Gastroenteritis, bill over cap | ₹7,500 | ⚠️ Partial ₹4,500 |
| TC004 | No prescription uploaded | ₹2,000 | ❌ Rejected |
| TC005 | Diabetes, day 44 of policy | ₹3,000 | ❌ Rejected — waiting period |
| TC006 | Ayurvedic Panchakarma | ₹4,000 | ✅ Approved ₹4,000 |
| TC007 | MRI, no pre-authorization | ₹15,000 | ❌ Rejected |
| TC008 | 3 claims on the same day | ₹4,800 | 🔍 Manual Review |
| TC009 | Weight loss treatment | ₹8,000 | ❌ Rejected |
| TC010 | Apollo Hospital (network) | ₹4,500 | ✅ Approved ₹3,600 |

Sample documents for TC001, TC002, TC005, TC009, TC010 are in `/Sample_docs`.

---

## 📋 Policy Rules

| Rule | Value |
|------|-------|
| Per-claim cap | ₹5,000 |
| Annual limit | ₹50,000 |
| Minimum claim | ₹500 |
| Submission window | 30 days from treatment |
| Non-network co-pay | 10% |
| Network discount | 20% (Apollo, Fortis, Max, Manipal, Narayana) |
| Consultation sub-limit | ₹2,000 |
| Pharmacy sub-limit | ₹15,000 |
| Diagnostics sub-limit | ₹10,000 |
| Dental sub-limit | ₹10,000 |
| Alternative medicine | ₹8,000 |

**Waiting periods** — Diabetes / Hypertension: 90 days · Maternity: 270 days · Pre-existing: 365 days · Joint replacement: 730 days

**Always excluded** — Cosmetic procedures, LASIK, weight loss/bariatric, IVF, HIV/AIDS treatment, vitamins (unless deficiency diagnosed), self-inflicted injuries, adventure sports

**Pre-auth required** — MRI and CT scans always require pre-authorization regardless of amount

---

## 🚀 Local Setup

```bash
git clone https://github.com/sivamani-muraboyina/ClaimLenZ.git
cd ClaimLenZ
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
cp .env.example .env         # add your GROQ_API_KEY
streamlit run app.py
```

Get a free Groq API key at [console.groq.com](https://console.groq.com) — no credit card required.

---

## 📁 Project Structure

```
ClaimLenZ/
├── app.py              # Streamlit UI + orchestration
├── llm_client.py       # Groq API calls (two-stage pipeline)
├── prompts.py          # System prompts + user message builders
├── Sample_docs/        # Test PDFs for all 10 test cases
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| LLM | Groq — LLaMA 3.3 70B Versatile |
| PDF extraction | pdfplumber |
| Rule engine | Python (deterministic) |
| Frontend | Streamlit |
| Environment | python-dotenv |

---

## 📐 Assumptions

- Network discount (20%) and non-network co-pay (10%) are mutually exclusive
- Per-claim cap of ₹5,000 triggers partial approval, not full rejection
- AYUSH doctor registration format (`AYUR/STATE/NUMBER/YEAR`) accepted alongside standard format
- Annual limit not tracked across sessions (requires a database)
- Image uploads accepted but text extraction only works on PDFs

---

## 🔮 Potential Improvements

- OCR for image documents (Tesseract / Google Vision API)
- Database for annual limit tracking across sessions (PostgreSQL / Supabase)
- Appeals workflow with human-in-the-loop review queue
- Multi-language support for Hindi, Telugu, Tamil prescriptions
- Admin panel for policy configuration without code changes
