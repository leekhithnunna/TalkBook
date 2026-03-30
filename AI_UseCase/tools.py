"""
LangChain tool definitions used by the chat agent.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from langchain.tools import tool
from rag_pipeline import retrieve_context
from db.database import save_booking
from email_service import send_confirmation_email


@tool
def rag_tool(query: str) -> str:
    """Answer questions about services, policies, or general info using the knowledge base."""
    context = retrieve_context(query)
    if not context:
        return "I don't have specific information about that in my knowledge base."
    return context


@tool
def booking_tool(name: str, email: str, phone: str,
                 booking_type: str, booking_date: str, booking_time: str) -> str:
    """Save a confirmed booking to the database and send a confirmation email."""
    try:
        result = save_booking(name, email, phone, booking_type, booking_date, booking_time)
        booking_id = result["booking_id"]
        email_sent = send_confirmation_email(email, name, booking_id, booking_type, booking_date, booking_time)
        msg = f"Booking confirmed! Your Booking ID is #{booking_id}."
        if not email_sent:
            msg += " (Note: confirmation email could not be sent — please check email settings.)"
        return msg
    except Exception as e:
        return f"Booking saved but encountered an issue: {str(e)}"
