"""
Twilio Telephony Provider

Implements TelephonyProvider interface for Twilio.
Supports voice calls via SIP trunk to LiveKit and SMS messaging.
"""

import hmac
import hashlib
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode

from backend.telephony.provider import (
    TelephonyProvider,
    ProviderConfig,
    CallResult,
    SMSResult,
    PhoneNumber,
    CallStatus,
    SMSStatus,
    CallDirection,
)

logger = logging.getLogger(__name__)

# SDK availability check
try:
    from twilio.rest import Client as TwilioClient
    from twilio.twiml.voice_response import VoiceResponse
    from twilio.request_validator import RequestValidator
    TWILIO_SDK_AVAILABLE = True
except ImportError:
    TWILIO_SDK_AVAILABLE = False
    logger.warning("Twilio SDK not installed. Run: pip install twilio")


class TwilioProvider(TelephonyProvider):
    """Twilio telephony provider implementation."""

    @property
    def provider_name(self) -> str:
        return "twilio"

    @property
    def is_configured(self) -> bool:
        if not TWILIO_SDK_AVAILABLE:
            return False
        return bool(
            self.config.account_sid
            and self.config.auth_token
        )

    def _get_client(self) -> Optional["TwilioClient"]:
        """Get or create Twilio client."""
        if not self.is_configured:
            return None
        if self._client is None:
            self._client = TwilioClient(
                self.config.account_sid,
                self.config.auth_token
            )
        return self._client

    async def validate_credentials(self) -> bool:
        """Validate Twilio credentials by fetching account info."""
        try:
            client = self._get_client()
            if not client:
                return False
            # Fetch account to verify credentials
            account = client.api.accounts(self.config.account_sid).fetch()
            return account.status == "active"
        except Exception as e:
            logger.error(f"Twilio credential validation failed: {e}")
            return False

    # =========================================================================
    # Voice Call Methods
    # =========================================================================

    async def initiate_call(
        self,
        to_number: str,
        from_number: Optional[str] = None,
        room_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CallResult:
        """Initiate an outbound call via Twilio."""
        client = self._get_client()
        if not client:
            return CallResult(
                success=False,
                error="Twilio not configured",
                status=CallStatus.FAILED
            )

        try:
            from_num = from_number or self.config.phone_number
            if not from_num:
                return CallResult(
                    success=False,
                    error="No from_number configured",
                    status=CallStatus.FAILED
                )

            # Generate room name if not provided
            if not room_name:
                import uuid
                room_name = f"phone-{uuid.uuid4().hex[:12]}"

            # Build webhook URL
            webhook_base = self.config.webhook_base_url
            webhook_url = f"{webhook_base}/telephony/twilio/voice/connect?room={room_name}"
            status_callback = f"{webhook_base}/telephony/twilio/voice/status"

            # Create the call
            call = client.calls.create(
                to=to_number,
                from_=from_num,
                url=webhook_url,
                status_callback=status_callback,
                status_callback_event=["completed", "failed", "busy", "no-answer"],
            )

            logger.info(f"Initiated Twilio call {call.sid} to {to_number}")

            return CallResult(
                success=True,
                call_id=call.sid,
                provider_call_id=call.sid,
                room_name=room_name,
                status=self._map_call_status(call.status),
                metadata={
                    "from_number": from_num,
                    "to_number": to_number,
                    **(metadata or {})
                }
            )

        except Exception as e:
            logger.error(f"Failed to initiate Twilio call: {e}")
            return CallResult(
                success=False,
                error=str(e),
                status=CallStatus.FAILED
            )

    def generate_call_response(
        self,
        room_name: str,
        caller_number: str,
        called_number: str,
        sip_uri: Optional[str] = None,
    ) -> str:
        """Generate TwiML response for connecting call to LiveKit."""
        response = VoiceResponse()

        sip_host = sip_uri or self.config.sip_uri
        if sip_host:
            # Connect to LiveKit via SIP
            full_sip_uri = f"sip:{room_name}@{sip_host}"
            dial = response.dial(
                caller_id=caller_number,
                timeout=30,
            )
            dial.sip(full_sip_uri, username="twilio")
            logger.info(f"Generated TwiML to connect to {full_sip_uri}")
        else:
            # Fallback message if SIP not configured
            response.say(
                "The AI assistant is not currently available. Please try again later.",
                voice="Polly.Joanna"
            )
            response.hangup()

        return str(response)

    async def end_call(self, call_id: str) -> bool:
        """End an active Twilio call."""
        client = self._get_client()
        if not client:
            return False

        try:
            client.calls(call_id).update(status="completed")
            logger.info(f"Ended Twilio call {call_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to end Twilio call {call_id}: {e}")
            return False

    async def get_call_status(self, call_id: str) -> Optional[CallStatus]:
        """Get the current status of a Twilio call."""
        client = self._get_client()
        if not client:
            return None

        try:
            call = client.calls(call_id).fetch()
            return self._map_call_status(call.status)
        except Exception as e:
            logger.error(f"Failed to get Twilio call status: {e}")
            return None

    def _map_call_status(self, twilio_status: str) -> CallStatus:
        """Map Twilio call status to standard CallStatus."""
        status_map = {
            "queued": CallStatus.INITIATING,
            "ringing": CallStatus.RINGING,
            "in-progress": CallStatus.IN_PROGRESS,
            "completed": CallStatus.COMPLETED,
            "failed": CallStatus.FAILED,
            "busy": CallStatus.BUSY,
            "no-answer": CallStatus.NO_ANSWER,
            "canceled": CallStatus.CANCELLED,
        }
        return status_map.get(twilio_status, CallStatus.INITIATING)

    # =========================================================================
    # SMS Methods
    # =========================================================================

    async def send_sms(
        self,
        to_number: str,
        message: str,
        from_number: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SMSResult:
        """Send an SMS via Twilio."""
        client = self._get_client()
        if not client:
            return SMSResult(
                success=False,
                error="Twilio not configured",
                status=SMSStatus.FAILED
            )

        try:
            from_num = from_number or self.config.phone_number
            if not from_num:
                return SMSResult(
                    success=False,
                    error="No from_number configured",
                    status=SMSStatus.FAILED
                )

            msg = client.messages.create(
                body=message,
                from_=from_num,
                to=to_number
            )

            logger.info(f"Sent Twilio SMS {msg.sid} to {to_number}")

            return SMSResult(
                success=True,
                message_id=msg.sid,
                provider_message_id=msg.sid,
                status=self._map_sms_status(msg.status),
                segments=msg.num_segments or 1,
                metadata={
                    "from_number": from_num,
                    "to_number": to_number,
                    **(metadata or {})
                }
            )

        except Exception as e:
            logger.error(f"Failed to send Twilio SMS: {e}")
            return SMSResult(
                success=False,
                error=str(e),
                status=SMSStatus.FAILED
            )

    async def get_sms_status(self, message_id: str) -> Optional[SMSStatus]:
        """Get the current status of a Twilio SMS."""
        client = self._get_client()
        if not client:
            return None

        try:
            msg = client.messages(message_id).fetch()
            return self._map_sms_status(msg.status)
        except Exception as e:
            logger.error(f"Failed to get Twilio SMS status: {e}")
            return None

    def _map_sms_status(self, twilio_status: str) -> SMSStatus:
        """Map Twilio SMS status to standard SMSStatus."""
        status_map = {
            "queued": SMSStatus.QUEUED,
            "sending": SMSStatus.SENDING,
            "sent": SMSStatus.SENT,
            "delivered": SMSStatus.DELIVERED,
            "failed": SMSStatus.FAILED,
            "undelivered": SMSStatus.UNDELIVERED,
        }
        return status_map.get(twilio_status, SMSStatus.QUEUED)

    # =========================================================================
    # Phone Number Methods
    # =========================================================================

    async def list_phone_numbers(self) -> List[PhoneNumber]:
        """List all Twilio phone numbers on the account."""
        client = self._get_client()
        if not client:
            return []

        try:
            numbers = client.incoming_phone_numbers.list()
            return [
                PhoneNumber(
                    number=num.phone_number,
                    provider=self.provider_name,
                    capabilities=self._get_capabilities(num),
                    friendly_name=num.friendly_name,
                    region=num.locality or num.region,
                    metadata={
                        "sid": num.sid,
                        "date_created": str(num.date_created),
                    }
                )
                for num in numbers
            ]
        except Exception as e:
            logger.error(f"Failed to list Twilio numbers: {e}")
            return []

    def _get_capabilities(self, num) -> List[str]:
        """Extract capabilities from Twilio number."""
        caps = []
        if hasattr(num, "capabilities"):
            if num.capabilities.get("voice"):
                caps.append("voice")
            if num.capabilities.get("sms"):
                caps.append("sms")
            if num.capabilities.get("mms"):
                caps.append("mms")
        return caps

    async def search_available_numbers(
        self,
        country: str = "US",
        area_code: Optional[str] = None,
        contains: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[PhoneNumber]:
        """Search for available Twilio phone numbers."""
        client = self._get_client()
        if not client:
            return []

        try:
            kwargs = {"limit": limit}
            if area_code:
                kwargs["area_code"] = area_code
            if contains:
                kwargs["contains"] = contains

            # Search based on capabilities
            caps = capabilities or ["voice", "sms"]
            if "voice" in caps:
                kwargs["voice_enabled"] = True
            if "sms" in caps:
                kwargs["sms_enabled"] = True

            numbers = client.available_phone_numbers(country).local.list(**kwargs)

            return [
                PhoneNumber(
                    number=num.phone_number,
                    provider=self.provider_name,
                    capabilities=caps,
                    friendly_name=num.friendly_name,
                    region=num.locality or num.region,
                )
                for num in numbers
            ]
        except Exception as e:
            logger.error(f"Failed to search Twilio numbers: {e}")
            return []

    async def purchase_number(self, number: str) -> Optional[PhoneNumber]:
        """Purchase a Twilio phone number."""
        client = self._get_client()
        if not client:
            return None

        try:
            purchased = client.incoming_phone_numbers.create(phone_number=number)
            logger.info(f"Purchased Twilio number {number}")

            return PhoneNumber(
                number=purchased.phone_number,
                provider=self.provider_name,
                capabilities=self._get_capabilities(purchased),
                friendly_name=purchased.friendly_name,
                metadata={"sid": purchased.sid}
            )
        except Exception as e:
            logger.error(f"Failed to purchase Twilio number {number}: {e}")
            return None

    async def release_number(self, number: str) -> bool:
        """Release a Twilio phone number."""
        client = self._get_client()
        if not client:
            return False

        try:
            # Find the number SID
            numbers = client.incoming_phone_numbers.list(phone_number=number)
            if not numbers:
                logger.warning(f"Number {number} not found")
                return False

            client.incoming_phone_numbers(numbers[0].sid).delete()
            logger.info(f"Released Twilio number {number}")
            return True
        except Exception as e:
            logger.error(f"Failed to release Twilio number {number}: {e}")
            return False

    # =========================================================================
    # Webhook Methods
    # =========================================================================

    def parse_webhook_call(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Twilio call webhook data."""
        return {
            "call_id": data.get("CallSid", ""),
            "from_number": data.get("From", ""),
            "to_number": data.get("To", ""),
            "direction": CallDirection.INBOUND if data.get("Direction") == "inbound" else CallDirection.OUTBOUND,
            "status": self._map_call_status(data.get("CallStatus", "")),
            "duration": int(data.get("CallDuration", 0)) if data.get("CallDuration") else None,
            "metadata": {
                "account_sid": data.get("AccountSid", ""),
                "api_version": data.get("ApiVersion", ""),
                "caller_name": data.get("CallerName", ""),
            }
        }

    def parse_webhook_sms(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Twilio SMS webhook data."""
        return {
            "message_id": data.get("MessageSid", ""),
            "from_number": data.get("From", ""),
            "to_number": data.get("To", ""),
            "body": data.get("Body", ""),
            "status": self._map_sms_status(data.get("SmsStatus", "")),
            "metadata": {
                "account_sid": data.get("AccountSid", ""),
                "num_segments": int(data.get("NumSegments", 1)),
                "num_media": int(data.get("NumMedia", 0)),
            }
        }

    def validate_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        url: Optional[str] = None,
    ) -> bool:
        """Validate Twilio webhook signature."""
        if not self.config.auth_token or not url:
            return False

        try:
            validator = RequestValidator(self.config.auth_token)
            # Twilio sends form data, so we need to decode and parse
            params = dict(pair.split("=") for pair in payload.decode().split("&") if "=" in pair)
            return validator.validate(url, params, signature)
        except Exception as e:
            logger.error(f"Twilio signature validation error: {e}")
            return False
