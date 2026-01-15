"""
Twilio Integration for Premier Voice Assistant

Handles SMS, voice calls, and phone number management.
Includes LiveKit SIP integration for connecting phone calls to AI agents.

Architecture:
┌──────────────────────────────────────────────────────────────────┐
│  Phone Call → Twilio → SIP Trunk → LiveKit Server → Agent       │
│                           │                                      │
│  User dials your Twilio number                                   │
│  Twilio connects via SIP to LiveKit                              │
│  LiveKit routes to the appropriate agent                         │
│  Agent handles the call like any other participant               │
└──────────────────────────────────────────────────────────────────┘

Setup:
1. Configure Twilio SIP Trunk to point to your LiveKit server
2. Set environment variables: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
3. Configure LiveKit SIP settings in your LiveKit Cloud dashboard
"""
import os
import logging
import uuid
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
LIVEKIT_SIP_URI = os.getenv("LIVEKIT_SIP_URI", "")  # e.g., "your-project.livekit.cloud"

# Twilio SDK
try:
    from twilio.rest import Client as TwilioClient
    from twilio.twiml.voice_response import VoiceResponse
    from twilio.twiml.messaging_response import MessagingResponse
    from twilio.request_validator import RequestValidator
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logger.warning("Twilio SDK not installed. Run: pip install twilio")

# Supabase for call logging
try:
    from backend.supabase_client import get_supabase
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False


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


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class TwilioStatus(BaseModel):
    """Twilio service status."""
    enabled: bool
    configured: bool
    phone_number: Optional[str] = None
    sip_configured: bool = False
    message: str


class OutboundCallRequest(BaseModel):
    """Request to initiate an outbound call."""
    to_number: str
    assistant_id: str
    user_id: str
    metadata: Optional[Dict[str, Any]] = None


class SMSSendRequest(BaseModel):
    """Request to send an SMS."""
    to_number: str
    message: str
    assistant_id: Optional[str] = None
    user_id: Optional[str] = None


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/status", response_model=TwilioStatus)
async def get_twilio_status():
    """Check Twilio service status and configuration."""
    if not TWILIO_AVAILABLE:
        return TwilioStatus(
            enabled=False,
            configured=False,
            message="Twilio SDK not installed. Run: pip install twilio"
        )

    issues = validate_twilio_config()
    if issues:
        return TwilioStatus(
            enabled=False,
            configured=False,
            message=f"Missing: {', '.join(issues)}"
        )

    return TwilioStatus(
        enabled=True,
        configured=True,
        phone_number=TWILIO_PHONE_NUMBER,
        sip_configured=bool(LIVEKIT_SIP_URI),
        message="Twilio is configured and ready"
    )


@router.post("/voice/incoming")
async def handle_incoming_call(request: Request):
    """
    Webhook for incoming Twilio calls.

    Configure this URL in your Twilio phone number settings:
    https://your-domain.com/twilio/voice/incoming

    This connects the call to LiveKit via SIP.
    """
    if not TWILIO_AVAILABLE:
        raise HTTPException(status_code=503, detail="Twilio not configured")

    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid", "")
        from_number = form_data.get("From", "")
        to_number = form_data.get("To", "")

        logger.info(f"Incoming call: {call_sid} from {from_number} to {to_number}")

        # Generate room name for this call
        room_name = f"phone-{uuid.uuid4().hex[:12]}"

        # Log the call
        if SUPABASE_AVAILABLE:
            try:
                supabase = get_supabase().client
                supabase.table("va_call_logs").insert({
                    "call_type": "phone",
                    "status": "connecting",
                    "started_at": datetime.utcnow().isoformat(),
                    "metadata": {
                        "room_name": room_name,
                        "call_sid": call_sid,
                        "from_number": from_number,
                        "to_number": to_number,
                        "transport": "sip",
                        "direction": "inbound",
                    }
                }).execute()
            except Exception as e:
                logger.error(f"Failed to create call log: {e}")

        # Build TwiML response
        response = VoiceResponse()

        if LIVEKIT_SIP_URI:
            # Connect to LiveKit via SIP
            sip_uri = f"sip:{room_name}@{LIVEKIT_SIP_URI}"
            dial = response.dial(
                caller_id=from_number,
                timeout=30,
                action="/twilio/voice/status",
            )
            dial.sip(sip_uri, username="twilio")
            logger.info(f"Connecting call {call_sid} to LiveKit room {room_name}")
        else:
            # Fallback: just say something
            response.say(
                "Hello! Your call has been received. The AI agent is not currently available. "
                "Please try again later or contact us via the web interface.",
                voice="Polly.Joanna"
            )
            response.hangup()

        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        logger.error(f"Failed to handle incoming call: {e}")
        response = VoiceResponse()
        response.say("We're sorry, we couldn't connect your call. Please try again later.", voice="Polly.Joanna")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")


@router.post("/voice/status")
async def handle_call_status(request: Request):
    """Webhook for call status updates."""
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid", "")
        call_status = form_data.get("CallStatus", "")
        call_duration = form_data.get("CallDuration", "0")

        logger.info(f"Call status: {call_sid} - {call_status} ({call_duration}s)")

        # Note: Updating call logs by call_sid would require a DB function or query

        response = VoiceResponse()
        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        logger.error(f"Failed to handle call status: {e}")
        return Response(content="<Response/>", media_type="application/xml")


@router.post("/call/outbound")
async def initiate_outbound_call(request: OutboundCallRequest):
    """Initiate an outbound phone call to a number."""
    if not is_twilio_configured():
        raise HTTPException(status_code=503, detail="Twilio is not configured")

    try:
        client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        room_name = f"phone-{uuid.uuid4().hex[:12]}"
        api_url = os.getenv("API_BASE_URL", os.getenv("API_URL", ""))

        call = client.calls.create(
            to=request.to_number,
            from_=TWILIO_PHONE_NUMBER,
            url=f"{api_url}/twilio/voice/outbound-connect?room={room_name}",
            status_callback=f"{api_url}/twilio/voice/status",
            status_callback_event=["completed", "failed", "busy", "no-answer"],
        )

        # Log the call
        call_id = None
        if SUPABASE_AVAILABLE:
            try:
                supabase = get_supabase().client
                result = supabase.table("va_call_logs").insert({
                    "user_id": request.user_id,
                    "assistant_id": request.assistant_id,
                    "call_type": "phone",
                    "status": "initiating",
                    "started_at": datetime.utcnow().isoformat(),
                    "metadata": {
                        "room_name": room_name,
                        "call_sid": call.sid,
                        "to_number": request.to_number,
                        "direction": "outbound",
                        "transport": "sip",
                        **(request.metadata or {}),
                    }
                }).execute()
                call_id = result.data[0]["id"] if result.data else None
            except Exception as e:
                logger.error(f"Failed to create call log: {e}")

        return {
            "success": True,
            "call_sid": call.sid,
            "room_name": room_name,
            "call_id": call_id,
            "status": call.status,
        }

    except Exception as e:
        logger.error(f"Failed to initiate outbound call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice/outbound-connect")
async def handle_outbound_connect(request: Request, room: str):
    """TwiML for outbound calls - connects to LiveKit when answered."""
    if not TWILIO_AVAILABLE:
        raise HTTPException(status_code=503, detail="Twilio not configured")

    try:
        response = VoiceResponse()

        if LIVEKIT_SIP_URI:
            sip_uri = f"sip:{room}@{LIVEKIT_SIP_URI}"
            dial = response.dial(timeout=30)
            dial.sip(sip_uri)
            logger.info(f"Connecting outbound call to room {room}")
        else:
            response.say("The AI agent is not available. Please try again later.", voice="Polly.Joanna")
            response.hangup()

        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        logger.error(f"Failed to connect outbound call: {e}")
        response = VoiceResponse()
        response.say("We couldn't connect your call. Please try again.")
        return Response(content=str(response), media_type="application/xml")


# ============================================================================
# SMS ENDPOINTS
# ============================================================================

@router.post("/sms/incoming")
async def handle_incoming_sms(request: Request):
    """
    Webhook for incoming SMS messages.

    Configure this URL in your Twilio phone number settings:
    https://your-domain.com/twilio/sms/incoming
    """
    if not TWILIO_AVAILABLE:
        raise HTTPException(status_code=503, detail="Twilio not configured")

    try:
        form_data = await request.form()
        from_number = form_data.get("From", "")
        to_number = form_data.get("To", "")
        message_body = form_data.get("Body", "")
        message_sid = form_data.get("MessageSid", "")

        logger.info(f"Incoming SMS from {from_number}: {message_body[:50]}...")

        # Generate AI response
        ai_response = await _generate_sms_response(message_body, from_number)

        # Log the SMS
        if SUPABASE_AVAILABLE:
            try:
                supabase = get_supabase().client
                supabase.table("va_sms_logs").insert({
                    "phone_number": from_number,
                    "direction": "inbound",
                    "message": message_body,
                    "response": ai_response,
                    "message_sid": message_sid,
                    "created_at": datetime.utcnow().isoformat(),
                }).execute()
            except Exception as e:
                logger.error(f"Failed to log SMS: {e}")

        # Return TwiML response
        response = MessagingResponse()
        response.message(ai_response)

        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        logger.error(f"Failed to handle incoming SMS: {e}")
        response = MessagingResponse()
        response.message("Sorry, I couldn't process your message. Please try again.")
        return Response(content=str(response), media_type="application/xml")


@router.post("/sms/send")
async def send_sms_endpoint(request: SMSSendRequest):
    """Send an SMS message via Twilio."""
    if not is_twilio_configured():
        raise HTTPException(status_code=503, detail="Twilio is not configured")

    service = get_twilio_service()
    result = service.send_sms(request.to_number, request.message)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to send SMS"))

    # Log the SMS
    if SUPABASE_AVAILABLE:
        try:
            supabase = get_supabase().client
            supabase.table("va_sms_logs").insert({
                "user_id": request.user_id,
                "assistant_id": request.assistant_id,
                "phone_number": request.to_number,
                "direction": "outbound",
                "message": request.message,
                "message_sid": result.get("message_sid"),
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
        except Exception as e:
            logger.error(f"Failed to log SMS: {e}")

    return result


async def _generate_sms_response(message: str, phone_number: str) -> str:
    """Generate an AI response for SMS using Brain client."""
    try:
        from backend.brain_client import FastBrainClient
        brain_url = os.getenv("FAST_BRAIN_URL", "")

        if brain_url:
            brain = FastBrainClient(
                base_url=brain_url,
                default_skill="sms",
            )

            if await brain.is_healthy():
                response_parts = []
                async for token in brain.stream(message, skill="sms"):
                    response_parts.append(token)
                response = "".join(response_parts)
                await brain.close()
                # Truncate to SMS limit (160 chars for single SMS)
                return response[:160] if len(response) > 160 else response

    except Exception as e:
        logger.warning(f"Brain client not available for SMS: {e}")

    # Fallback response
    return "Thanks for your message! I'm an AI assistant. For full conversations, please use our web app at hive215.com"
