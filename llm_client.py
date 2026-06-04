"""
llm_client.py — Groq API calls for ClaimLenZ.
Two-stage pipeline: extract fields → adjudication decision.
"""

import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = None


def _get_client() -> Groq:
    """Lazily initialise the Groq client so missing keys surface clearly."""
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not found. "
                "Create a .env file with GROQ_API_KEY=<your_key> "
                "or set it in Streamlit Cloud secrets."
            )
        _client = Groq(api_key=api_key)
    return _client


def _call_groq(system_prompt: str, user_message: str) -> dict:
    """
    Send one chat completion request to Groq and parse JSON response.
    Falls back to MANUAL_REVIEW on any error.
    """
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.1,
            max_tokens=1500,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if model adds them
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        return json.loads(raw)

    except json.JSONDecodeError as e:
        return _fallback(f"JSON parse error: {e}")
    except Exception as e:
        return _fallback(str(e))


def _fallback(reason: str) -> dict:
    """Return a safe MANUAL_REVIEW dict when LLM call fails."""
    return {
        "decision": "MANUAL_REVIEW",
        "approved_amount": 0,
        "rejection_reasons": [],
        "rejection_explainer": f"AI processing error — manual review required. ({reason})",
        "next_steps": "Please resubmit your claim or contact support.",
        "partial_rejection_items": [],
        "copay_deducted": 0,
        "network_discount": 0,
        "fraud_flags": ["AI pipeline error"],
        "confidence_score": 0.0,
    }


# ─── Public API ──────────────────────────────────────────────────────────────

def extract_fields(document_text: str) -> dict:
    """Stage 1 — Extract structured fields from raw document text."""
    from prompts import EXTRACTION_SYSTEM, extraction_user
    return _call_groq(EXTRACTION_SYSTEM, extraction_user(document_text))


def get_decision(extracted_fields: dict, claim_data: dict) -> dict:
    """Stage 2 — Make adjudication decision from extracted fields + claim form data."""
    from prompts import DECISION_SYSTEM, decision_user
    return _call_groq(DECISION_SYSTEM, decision_user(extracted_fields, claim_data))
