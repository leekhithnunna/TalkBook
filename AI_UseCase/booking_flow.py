"""
Multi-turn slot filling for booking.
Tracks which fields are collected and asks for missing ones.
"""

REQUIRED_SLOTS = ["name", "email", "phone", "booking_type", "booking_date", "booking_time"]

SLOT_QUESTIONS = {
    "name": "What's your full name?",
    "email": "What's your email address?",
    "phone": "What's your phone number?",
    "booking_type": "What type of booking would you like? (e.g., Doctor, Hotel, Salon)",
    "booking_date": "What date would you prefer? (e.g., 2024-04-15)",
    "booking_time": "What time works for you? (e.g., 10:00 AM)",
}

def get_next_missing_slot(slots: dict) -> str | None:
    """Return the next slot that hasn't been filled yet."""
    for slot in REQUIRED_SLOTS:
        if not slots.get(slot):
            return slot
    return None

def is_booking_complete(slots: dict) -> bool:
    return all(slots.get(s) for s in REQUIRED_SLOTS)

def summarize_booking(slots: dict) -> str:
    type_icon = {"Doctor": "🏥", "Hotel": "🏨", "Salon": "💇", "Other": "📌"}.get(slots.get("booking_type", ""), "📋")
    return (
        f"Here's your booking summary:\n\n"
        f"- **Name:** {slots['name']}\n"
        f"- **Email:** {slots['email']}\n"
        f"- **Phone:** {slots['phone']}\n"
        f"- **Type:** {type_icon} {slots['booking_type']}\n"
        f"- **Date:** {slots['booking_date']}\n"
        f"- **Time:** {slots['booking_time']}\n\n"
        f"Shall I confirm this booking? Reply **yes** to confirm or **no** to cancel."
    )

import re

def extract_slot_from_reply(slot: str, text: str) -> str | None:
    """Simple extraction — for email validate format, otherwise return stripped text."""
    text = text.strip()
    if slot == "email":
        match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
        return match.group(0) if match else None
    if slot == "phone":
        match = re.search(r"[\d\s\-+()]{7,}", text)
        return match.group(0).strip() if match else None
    return text if text else None
