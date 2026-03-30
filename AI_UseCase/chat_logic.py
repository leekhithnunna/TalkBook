"""
Core chat orchestration for TalkBook.
Handles: booking flow, general RAG, PDF-only chat.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from models.llm import get_llm
from rag_pipeline import retrieve_context, retrieve_from_pdf
from booking_flow import (
    get_next_missing_slot, is_booking_complete,
    summarize_booking, extract_slot_from_reply, SLOT_QUESTIONS
)
from db.database import save_booking
from email_service import send_confirmation_email
from config.config import MAX_HISTORY

BOOKING_KEYWORDS = [
    "book", "booking", "appointment", "reserve", "reservation",
    "schedule", "slot", "want to book", "i need a booking",
    "make a booking", "set an appointment",
]

SYSTEM_PROMPT = """You are TalkBook, a friendly AI booking assistant.
You help users:
1. Answer general questions using your knowledge base.
2. Make bookings step-by-step (Doctor, Hotel, Salon, etc.).

Be warm, concise, and professional. Ask one question at a time during booking."""

PDF_SYSTEM_PROMPT = """You are TalkBook PDF Assistant.
Answer questions ONLY based on the provided document context.
If the answer is not in the document, say: "I couldn't find that in the uploaded document."
Do not use outside knowledge."""


def detect_booking_intent(text: str) -> bool:
    return any(kw in text.lower() for kw in BOOKING_KEYWORDS)


def _build_llm_messages(system: str, context: str, history: list, query: str) -> list:
    msgs = [SystemMessage(content=system)]
    if context:
        msgs.append(SystemMessage(content=f"Context:\n{context}"))
    for m in history[-MAX_HISTORY:]:
        if m["role"] == "user":
            msgs.append(HumanMessage(content=m["content"]))
        else:
            msgs.append(AIMessage(content=m["content"]))
    msgs.append(HumanMessage(content=query))
    return msgs


def get_general_response(query: str, history: list) -> str:
    context = retrieve_context(query)
    llm     = get_llm()
    msgs    = _build_llm_messages(SYSTEM_PROMPT, context, history, query)
    return llm.invoke(msgs).content


def get_pdf_response(query: str, history: list) -> str:
    context = retrieve_from_pdf(query)
    if not context:
        return "I couldn't find that in the uploaded document. Please make sure you've uploaded a relevant PDF."
    llm  = get_llm()
    msgs = _build_llm_messages(PDF_SYSTEM_PROMPT, context, history, query)
    return llm.invoke(msgs).content


def process_message(user_input: str, session: dict) -> str:
    """
    Main chat entry point for the general assistant.
    session keys used: messages, booking_slots, booking_active, awaiting_confirmation, user
    """
    messages            = session.setdefault("messages", [])
    slots               = session.setdefault("booking_slots", {})
    booking_active      = session.get("booking_active", False)
    awaiting_confirm    = session.get("awaiting_confirmation", False)
    user                = session.get("user")  # dict with id, name, email, role

    # ── Confirmation step ─────────────────────────────────────────────────────
    if awaiting_confirm:
        if user_input.strip().lower() in ("yes", "y", "confirm", "ok", "sure", "yep", "yeah"):
            try:
                user_id = user["id"] if user else None
                result  = save_booking(
                    slots["name"], slots["email"], slots["phone"],
                    slots["booking_type"], slots["booking_date"], slots["booking_time"],
                    user_id=user_id
                )
                bid  = result["booking_id"]
                bref = result["booking_ref"]
                # Always send to the signed-in user's email (not just the booking field)
                send_to = user["email"] if user else slots["email"]
                email_ok, email_err = send_confirmation_email(
                    send_to, slots["name"], bref,
                    slots["booking_type"], slots["booking_date"], slots["booking_time"]
                )
                session.update({"booking_active": False, "awaiting_confirmation": False, "booking_slots": {}})
                email_note = (
                    f"\n\n✅ Confirmation email sent to **{send_to}**."
                    if email_ok else
                    f"\n\n⚠️ Email not sent: {email_err}"
                )
                return (
                    f"Your booking is confirmed!\n\n"
                    f"**Booking ID:** `{bref}`\n"
                    f"**Type:** {slots['booking_type']}\n"
                    f"**Date:** {slots['booking_date']} at {slots['booking_time']}"
                    f"{email_note}"
                )
            except Exception as e:
                session["awaiting_confirmation"] = False
                return f"There was an error saving your booking: {str(e)}. Please try again."
        else:
            session.update({"booking_active": False, "awaiting_confirmation": False, "booking_slots": {}})
            return "No problem! Booking cancelled. Is there anything else I can help you with?"

    # ── Active slot filling ───────────────────────────────────────────────────
    if booking_active:
        next_slot = get_next_missing_slot(slots)

        if next_slot:
            # Special case: if name+email are pre-filled and we're waiting for phone,
            # check if user said "yes" (confirm details) or typed something else
            if next_slot == "phone":
                lower = user_input.strip().lower()
                if lower in ("yes", "y", "ok", "correct", "sure", "yep", "yeah", "right"):
                    # Confirmed — just ask for phone
                    return SLOT_QUESTIONS["phone"]
                # Check if they typed a new name (no digits, not an email)
                import re as _re
                if not _re.search(r"[\d@]", user_input.strip()) and len(user_input.strip()) > 1:
                    # Treat as a name correction
                    slots["name"] = user_input.strip()
                    return f"Got it! Name updated to **{slots['name']}**. {SLOT_QUESTIONS['phone']}"

            extracted = extract_slot_from_reply(next_slot, user_input)
            if extracted:
                slots[next_slot] = extracted
            else:
                return f"I didn't quite catch that. {SLOT_QUESTIONS[next_slot]}"

        if is_booking_complete(slots):
            session["awaiting_confirmation"] = True
            session["booking_active"]        = False
            return summarize_booking(slots)
        return SLOT_QUESTIONS[get_next_missing_slot(slots)]

    # ── New booking intent ────────────────────────────────────────────────────
    if detect_booking_intent(user_input):
        session["booking_active"]  = True
        session["booking_slots"]   = {}

        # If logged in, confirm pre-filled details with the user instead of silently skipping
        if user:
            prefill_name  = user.get("name", "")
            prefill_email = user.get("email", "")
            session["booking_slots"]["name"]  = prefill_name
            session["booking_slots"]["email"] = prefill_email
            return (
                f"I'd be happy to help you book! 🎉\n\n"
                f"I'll use your account details:\n"
                f"- **Name:** {prefill_name}\n"
                f"- **Email:** {prefill_email}\n\n"
                f"Is that correct? If yes, {SLOT_QUESTIONS['phone']} "
                f"(Or type a different name to change it)"
            )

        next_slot = get_next_missing_slot(session["booking_slots"])
        return f"I'd be happy to help you book! {SLOT_QUESTIONS[next_slot]}"

    # ── General LLM + RAG ─────────────────────────────────────────────────────
    return get_general_response(user_input, messages)
