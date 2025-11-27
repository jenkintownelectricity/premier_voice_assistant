"""
Twilio Integration for Premier Voice Assistant
Handles SMS, voice calls, and phone number management.
"""
import os
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")


def is_twilio_configured() -> bool:
    """Check if Twilio credentials are set."""
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN)


def get_twilio_client():
    """Get Twilio client instance."""
    if not is_twilio_configured():
        logger.warning("Twilio not configured")
        return None
    from twilio.rest import Client
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


class TwilioService:
    def __init__(self):
        self.client = get_twilio_client()
        self.default_from_number = TWILIO_PHONE_NUMBER

    @property
    def is_configured(self) -> bool:
        return self.client is not None

    def send_sms(self, to_number: str, message: str, from_number: Optional[str] = None) -> Dict[str, Any]:
        if not self.is_configured:
            return {"success": False, "error": "Twilio not configured"}
        try:
            from_num = from_number or self.default_from_number
            if not from_num:
                return {"success": False, "error": "No from_number configured"}
            msg = self.client.messages.create(body=message, from_=from_num, to=to_number)
            return {"success": True, "message_sid": msg.sid, "status": msg.status}
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return {"success": False, "error": str(e)}

    def send_verification_code(self, to_number: str, code: str) -> Dict[str, Any]:
        message = f"Your HIVE215 verification code is: {code}. It expires in 10 minutes."
        return self.send_sms(to_number, message)

    def initiate_call(self, to_number: str, from_number: Optional[str] = None,
                      webhook_url: Optional[str] = None) -> Dict[str, Any]:
        if not self.is_configured:
            return {"success": False, "error": "Twilio not configured"}
        try:
            from_num = from_number or self.default_from_number
            api_url = os.getenv("API_URL", "http://localhost:8000")
            call = self.client.calls.create(
                to=to_number,
                from_=from_num,
                url=webhook_url or f"{api_url}/twilio/voice/outbound",
                status_callback=f"{api_url}/twilio/voice/status",
                record=True
            )
            return {"success": True, "call_sid": call.sid, "status": call.status}
        except Exception as e:
            logger.error(f"Failed to initiate call: {e}")
            return {"success": False, "error": str(e)}


_twilio_service: Optional[TwilioService] = None


def get_twilio_service() -> TwilioService:
    global _twilio_service
    if _twilio_service is None:
        _twilio_service = TwilioService()
    return _twilio_service


def validate_twilio_config() -> List[str]:
    issues = []
    if not TWILIO_ACCOUNT_SID:
        issues.append("TWILIO_ACCOUNT_SID not set")
    if not TWILIO_AUTH_TOKEN:
        issues.append("TWILIO_AUTH_TOKEN not set")
    if not TWILIO_PHONE_NUMBER:
        issues.append("TWILIO_PHONE_NUMBER not set")
    return issues
