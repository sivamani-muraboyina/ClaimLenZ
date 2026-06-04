"""
ClaimLenZ — OPD Claim Adjudication Tool
AI-powered insurance claim processing built for Plum.
"""

import streamlit as st
from datetime import date, datetime, timedelta
import re
import pdfplumber
import io

# ─── Page config ────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="ClaimLenZ — OPD Adjudication · Plum",
    page_icon="🏥",
    layout="wide"
)

# ─── Constants ───────────────────────────────────────────────────────────────

NETWORK_HOSPITALS = ["apollo", "fortis", "max", "manipal", "narayana"]

WAITING_DAYS = {
    "diabetes": 90,
    "hypertension": 90,
    "maternity": 270,
    "pregnancy": 270,
    "joint replacement": 730,
    "pre-existing": 365,
}

# ─── Pure-Python rule checks (no LLM needed) ────────────────────────────────

def run_instant_checks(claim_amount: float, treatment_date: date) -> dict | None:
    """Return rejection dict immediately if hard rules are violated, else None."""
    days_since = (date.today() - treatment_date).days

    if claim_amount < 500:
        return {
            "decision": "REJECTED",
            "rejection_reasons": ["BELOW_MIN_AMOUNT"],
            "rejection_explainer": (
                f"Claim amount ₹{claim_amount:.0f} is below the minimum "
                "eligible claim amount of ₹500 under this policy."
            ),
            "next_steps": (
                "Claims below ₹500 are not eligible for reimbursement. "
                "Consolidate multiple small bills into a single claim if possible."
            ),
            "approved_amount": 0,
            "confidence_score": 1.0,
            "fraud_flags": [],
            "partial_rejection_items": [],
            "copay_deducted": 0,
            "network_discount": 0,
        }

    if days_since > 30:
        return {
            "decision": "REJECTED",
            "rejection_reasons": ["LATE_SUBMISSION"],
            "rejection_explainer": (
                f"Claim submitted {days_since} days after treatment. "
                "The submission deadline is 30 days from the date of treatment."
            ),
            "next_steps": (
                "Late submissions cannot be processed under this policy. "
                "Please submit future claims within 30 days of treatment."
            ),
            "approved_amount": 0,
            "confidence_score": 1.0,
            "fraud_flags": [],
            "partial_rejection_items": [],
            "copay_deducted": 0,
            "network_discount": 0,
        }

    return None  # pass — continue to LLM pipeline


def validate_doctor_reg(reg_number: str) -> bool:
    """Return True if doctor registration matches known valid formats."""
    if not reg_number:
        return False
    standard = re.match(r"^[A-Z]{2}/\d+/\d{4}$", reg_number)
    ayush = re.match(r"^AYUR/[A-Z]{2}/\d+/\d{4}$", reg_number)
    return bool(standard or ayush)


def calculate_final_amount(claim_amount: float, hospital_name: str) -> tuple[float, float, float]:
    """Apply per-claim cap, then network discount or co-pay. Returns (final, discount, copay)."""
    capped = min(claim_amount, 5000)
    h_lower = hospital_name.lower()
    is_network = any(h in h_lower for h in NETWORK_HOSPITALS)

    if is_network:
        discount = round(capped * 0.20)
        return capped - discount, discount, 0
    else:
        copay = round(capped * 0.10)
        return capped - copay, 0, copay


def get_eligibility_date(policy_start: date, diagnosis: str) -> str:
    """Return the date a member becomes eligible based on diagnosis waiting period."""
    d_lower = diagnosis.lower()
    days = 365  # default pre-existing
    for condition, wait in WAITING_DAYS.items():
        if condition in d_lower:
            days = wait
            break
    eligible = policy_start + timedelta(days=days)
    return eligible.strftime("%d %b %Y")


# ─── Document text extraction ────────────────────────────────────────────────

def extract_text_from_files(uploaded_files) -> str:
    """Read text from uploaded PDFs; note images as non-extractable."""
    all_text = ""
    for file in uploaded_files:
        all_text += f"\n\n--- DOCUMENT: {file.name} ---\n"
        if file.name.lower().endswith(".pdf"):
            try:
                with pdfplumber.open(io.BytesIO(file.read())) as pdf:
                    for page in pdf.pages:
                        all_text += page.extract_text() or ""
            except Exception as e:
                all_text += f"[Could not read PDF: {e}]"
        else:
            all_text += f"[Image file: {file.name} — visual document, text not extracted]"
    return all_text.strip() or "No document text could be extracted."


# ─── Decision card UI ────────────────────────────────────────────────────────

def show_decision_card(decision: dict, claim_amount: float, policy_start: date, extracted: dict):
    """Render the full adjudication result card in the right column."""
    d = decision.get("decision", "MANUAL_REVIEW")
    approved = decision.get("approved_amount", 0)
    explainer = decision.get("rejection_explainer", "")
    next_steps = decision.get("next_steps", "")
    confidence = decision.get("confidence_score", 0.0)
    reasons = decision.get("rejection_reasons", [])

    st.markdown("---")
    st.subheader("📋 Adjudication Result")

    # ── Main status banner
    if d == "APPROVED":
        st.success("✅ **Claim Approved**")
        c1, c2, c3 = st.columns(3)
        c1.metric("Claimed", f"₹{claim_amount:,.0f}")
        copay = decision.get("copay_deducted", 0)
        disc = decision.get("network_discount", 0)
        label = "Network Discount" if disc else "Co-pay Deducted"
        c2.metric(label, f"-₹{disc or copay:,.0f}")
        c3.metric("✅ Approved Amount", f"₹{approved:,.0f}", delta=f"-₹{claim_amount - approved:,.0f}")

    elif d == "REJECTED":
        st.error("❌ **Claim Rejected**")
        st.write(explainer)
        st.info(f"**Next steps:** {next_steps}")

        if "WAITING_PERIOD" in reasons:
            diag = extracted.get("diagnosis", {}).get("value", "") if extracted else ""
            eligible_date = get_eligibility_date(policy_start, diag)
            st.warning(f"📅 You become eligible for this condition from: **{eligible_date}**")

        if reasons:
            st.markdown("**Rejection codes:**")
            for r in reasons:
                st.code(r)

    elif d == "PARTIAL":
        st.warning("⚠️ **Partial Approval**")
        c1, c2 = st.columns(2)
        c1.metric("Claimed", f"₹{claim_amount:,.0f}")
        c2.metric("⚠️ Approved Amount", f"₹{approved:,.0f}")
        items = decision.get("partial_rejection_items", [])
        if items:
            st.markdown("**Items not covered:**")
            for item in items:
                st.markdown(f"  • {item}")
        if explainer:
            st.write(explainer)
        if next_steps:
            st.info(f"**Next steps:** {next_steps}")

    elif d == "MANUAL_REVIEW":
        st.info("🔍 **Sent for Manual Review**")
        flags = decision.get("fraud_flags", [])
        if flags:
            st.markdown("**Flags raised:**")
            for flag in flags:
                st.markdown(f"  • {flag}")
        if explainer:
            st.write(explainer)
        if next_steps:
            st.info(f"**Next steps:** {next_steps}")

    # ── Confidence bar
    st.markdown("---")
    st.markdown("**AI Confidence Score**")
    st.progress(float(confidence))
    st.caption(f"{confidence*100:.0f}% confidence")
    if confidence < 0.70:
        st.warning("⚠️ Low confidence — flagged for human verification")

    # ── Expandable: extracted fields
    with st.expander("📄 Extracted Document Fields"):
        if extracted:
            st.json(extracted)
        else:
            st.write("No fields extracted.")

    # ── Expandable: calculation breakdown
    with st.expander("📊 Calculation Breakdown"):
        cap = min(claim_amount, 5000)
        copay = decision.get("copay_deducted", 0)
        disc = decision.get("network_discount", 0)
        st.markdown(f"""
| Step | Amount |
|------|--------|
| Claimed amount | ₹{claim_amount:,.0f} |
| After ₹5,000 per-claim cap | ₹{cap:,.0f} |
| Network discount deducted | -₹{disc:,.0f} |
| Co-pay deducted (10%) | -₹{copay:,.0f} |
| **Final approved** | **₹{approved:,.0f}** |
        """)


# ─── Session state init ───────────────────────────────────────────────────────

if "claims_history" not in st.session_state:
    st.session_state.claims_history = []

# ─── Header ──────────────────────────────────────────────────────────────────

st.markdown(
    """
    <h1 style='margin-bottom:0'>🏥 ClaimLenZ</h1>
    <p style='color:gray;margin-top:2px'>
    AI-powered OPD Claim Adjudication &nbsp;·&nbsp; Plum Insurance
    </p>
    """,
    unsafe_allow_html=True,
)

col1, col2 = st.columns([4, 6])

# ─── LEFT COLUMN — Claim form ────────────────────────────────────────────────

with col1:
    st.markdown("### 📝 Submit Claim")

    with st.form("claim_form"):
        member_name = st.text_input("Member Name *", placeholder="e.g. Rajesh Kumar")
        member_id   = st.text_input("Member ID *",   placeholder="e.g. EMP001")

        c_a, c_b = st.columns(2)
        policy_start   = c_a.date_input("Policy Start Date", value=date(2024, 1, 1))
        treatment_date = c_b.date_input("Treatment Date",    value=date.today())

        claim_amount  = st.number_input("Claim Amount (₹) *", min_value=0.0, step=100.0, value=1500.0)
        hospital_name = st.text_input("Hospital / Clinic Name", placeholder="e.g. Apollo Hospitals")
        pre_auth      = st.checkbox("Pre-authorization obtained?")

        uploaded_files = st.file_uploader(
            "Upload Documents (prescription, bill, reports)",
            type=["pdf", "jpg", "jpeg", "png"],
            accept_multiple_files=True,
            help="PDF preferred for text extraction. Images accepted but text won't be parsed.",
        )

        submitted = st.form_submit_button(
            "⚡ Adjudicate Claim", type="primary", use_container_width=True
        )

    st.caption("*Required fields")

    # Policy reference card
    with st.expander("📜 Policy Quick Reference"):
        st.markdown("""
**Limits**
- Per-claim cap: ₹5,000
- Annual limit: ₹50,000
- Consultation: ₹2,000 | Pharmacy: ₹15,000
- Dental: ₹10,000 | Diagnostics: ₹10,000

**Co-pay**
- Non-network: 10% co-pay
- Network hospitals: 20% discount

**Waiting Periods**
- General: 30 days | Diabetes/HTN: 90 days
- Pre-existing: 1 year | Maternity: 270 days

**Network Hospitals**
Apollo · Fortis · Max · Manipal · Narayana
        """)

# ─── RIGHT COLUMN — Results ──────────────────────────────────────────────────

with col2:

    if submitted:
        # ── Basic validation
        if not member_name.strip() or not member_id.strip():
            st.error("Please fill in Member Name and Member ID.")
            st.stop()

        if not uploaded_files:
            st.warning("⚠️ No documents uploaded. Claim will likely be rejected for missing prescription.")

        # ── Step 1: Instant Python checks (no LLM)
        instant = run_instant_checks(claim_amount, treatment_date)
        if instant:
            show_decision_card(instant, claim_amount, policy_start, {})
            st.session_state.claims_history.append({
                "Time":         datetime.now().strftime("%H:%M:%S"),
                "Member":       member_name,
                "Claimed (₹)":  int(claim_amount),
                "Decision":     instant["decision"],
                "Approved (₹)": 0,
            })
            st.stop()

        # ── Step 2: Extract text from uploaded documents
        with st.spinner("📄 Reading uploaded documents..."):
            doc_text = extract_text_from_files(uploaded_files) if uploaded_files else "No documents provided."

        # ── Step 3: Groq Call 1 — extract fields
        with st.spinner("🔍 Extracting document fields with AI..."):
            from llm_client import extract_fields, get_decision as llm_get_decision
            extracted = extract_fields(doc_text)

        # ── Step 4: Python override — validate doctor reg format
        doc_reg = extracted.get("doctor_reg_number", {}).get("value", "")
        if doc_reg and not validate_doctor_reg(doc_reg):
            st.caption(f"⚠️ Doctor reg format unrecognised: `{doc_reg}` — confidence set to 0")
            extracted["doctor_reg_number"]["confidence"] = 0.0

        # ── Step 5: Build claim data dict for LLM
        days_since = (date.today() - treatment_date).days
        claim_data = {
            "member_name":    member_name,
            "member_id":      member_id,
            "policy_start":   str(policy_start),
            "treatment_date": str(treatment_date),
            "days_since":     days_since,
            "claim_amount":   claim_amount,
            "hospital_name":  hospital_name,
            "pre_auth":       pre_auth,
        }

        # ── Step 6: Groq Call 2 — adjudication decision
        with st.spinner("⚖️ Running adjudication engine..."):
            decision = llm_get_decision(extracted, claim_data)

        # ── Step 7: Python calculates final approved amount (overrides LLM)
        if decision.get("decision") in ["APPROVED", "PARTIAL"]:
            final, disc, copay = calculate_final_amount(claim_amount, hospital_name)
            decision["approved_amount"]  = final
            decision["network_discount"] = disc
            decision["copay_deducted"]   = copay

        # ── Step 8: Render decision card
        show_decision_card(decision, claim_amount, policy_start, extracted)

        # ── Step 9: Save to session history
        st.session_state.claims_history.append({
            "Time":         datetime.now().strftime("%H:%M:%S"),
            "Member":       member_name,
            "Claimed (₹)":  int(claim_amount),
            "Decision":     decision.get("decision", "—"),
            "Approved (₹)": int(decision.get("approved_amount", 0)),
        })

    else:
        # Placeholder when no claim submitted yet
        st.markdown(
            """
            <div style='
                border: 2px dashed #ccc;
                border-radius: 12px;
                padding: 60px 40px;
                text-align: center;
                color: #888;
                margin-top: 40px;
            '>
                <h3>🏥 ClaimIQ</h3>
                <p>Fill in the claim form and upload your documents.<br>
                The AI will adjudicate your claim in seconds.</p>
                <br>
                <p style='font-size:13px'>
                    Powered by Llama 3.3 70B via Groq · Built for Plum
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ─── Claims history table (full width, below columns) ────────────────────────

if st.session_state.claims_history:
    st.markdown("---")
    st.markdown("### 📊 Session Claims History")
    st.dataframe(
        st.session_state.claims_history,
        use_container_width=True,
        hide_index=True,
    )
