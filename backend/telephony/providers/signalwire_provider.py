"""
SignalWire Telephony Provider

Implements TelephonyProvider interface for SignalWire.
Supports voice calls via SIP trunk to LiveKit and SMS messaging.

SignalWire uses a Twilio-compatible API with LaML (Language Markup Language).
"""

import hmac
import hashlib
import base64
import logging
from typing import Optional, Dict, Any, List

import httpx

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


class SignalWireProvider(TelephonyProvider):
    """SignalWire telephony provider implementation."""

    @property
    def provider_name(self) -> str:
        return "signalwire"

    @property
    def is_configured(self) -> bool:
        return bool(
            self.config.account_sid
            and self.config.auth_token
            and self.config.extra.get("space_url")
        )

    def _get_base_url(self) -> str:
        """Get SignalWire space API URL."""
        space_url = self.config.extra.get("space_url", "")
        return f"https://{space_url}/api/laml/2010-04-01/Accounts/{self.config.account_sid}"

    def _get_auth(self) -> tuple:
        """Get HTTP Basic Auth tuple for SignalWire."""
        return (self.config.account_sid, self.config.auth_token)

    async def validate_credentials(self) -> bool:
        """Validate SignalWire credentials by fetching account info."""
        if not self.is_configured:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._get_base_url()}.json",
                    auth=self._get_auth(),
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"SignalWire credential validation failed: {e}")
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
        """Initiate an outbound call via SignalWire."""
        if not self.is_configured:
            return CallResult(
                success=False,
                error="SignalWire not configured",
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
            webhook_url = f"{webhook_base}/telephony/signalwire/voice/connect?room={room_name}"
            status_callback = f"{webhook_base}/telephony/signalwire/voice/status"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._get_base_url()}/Calls.json",
                    auth=self._get_auth(),
                    data={
                        "To": to_number,
                        "From": from_num,
                        "Url": webhook_url,
                        "StatusCallback": status_callback,
                        "StatusCallbackEvent": ["completed", "failed", "busy", "no-answer"],
                    },
                    timeout=30.0
                )

                if response.status_code not in (200, 201):
                    error_msg = response.json().get("message", "Unknown error")
                    return CallResult(
                        success=False,
                        error=error_msg,
                        status=CallStatus.FAILED
                    )

                data = response.json()
                call_sid = data.get("sid", "")

                logger.info(f"Initiated SignalWire call {call_sid} to {to_number}")

                return CallResult(
                    success=True,
                    call_id=call_sid,
                    provider_call_id=call_sid,
                    room_name=room_name,
                    status=self._map_call_status(data.get("status", "")),
                    metadata={
                        "from_number": from_num,
                        "to_number": to_number,
                        **(metadata or {})
                    }
                )

        except Exception as e:
            logger.error(f"Failed to initiate SignalWire call: {e}")
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
        """Generate LaML response for connecting call to LiveKit."""
        sip_host = sip_uri or self.config.sip_uri

        if sip_host:
            # LaML (Twilio-compatible) to connect to LiveKit via SIP
            full_sip_uri = f"sip:{room_name}@{sip_host}"
            laml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial callerId="{caller_number}" timeout="30">
        <Sip>{full_sip_uri}</Sip>
    </Dial>
</Response>"""
            logger.info(f"Generated LaML to connect to {full_sip_uri}")
        else:
            # Fallback message if SIP not configured
            laml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">The AI assistant is not currently available. Please try again later.</Say>
    <Hangup/>
</Response>"""

        return laml

    async def end_call(self, call_id: str) -> bool:
        """End an active SignalWire call."""
        if not self.is_configured:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._get_base_url()}/Calls/{call_id}.json",
                    auth=self._get_auth(),
                    data={"Status": "completed"},
                    timeout=10.0
                )
                success = response.status_code == 200
                if success:
                    logger.info(f"Ended SignalWire call {call_id}")
                return success
        except Exception as e:
            logger.error(f"Failed to end SignalWire call {call_id}: {e}")
            return False

    async def get_call_status(self, call_id: str) -> Optional[CallStatus]:
        """Get the current status of a SignalWire call."""
        if not self.is_configured:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._get_base_url()}/Calls/{call_id}.json",
                    auth=self._get_auth(),
                    timeout=10.0
                )
                if response.status_code != 200:
                    return None

                data = response.json()
                return self._map_call_status(data.get("status", ""))
        except Exception as e:
            logger.error(f"Failed to get SignalWire call status: {e}")
            return None

    def _map_call_status(self, sw_status: str) -> CallStatus:
        """Map SignalWire call status to standard CallStatus."""
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
        return status_map.get(sw_status, CallStatus.INITIATING)

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
        """Send an SMS via SignalWire."""
        if not self.is_configured:
            return SMSResult(
                success=False,
                error="SignalWire not configured",
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

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._get_base_url()}/Messages.json",
                    auth=self._get_auth(),
                    data={
                        "From": from_num,
                        "To": to_number,
                        "Body": message,
                    },
                    timeout=30.0
                )

                if response.status_code not in (200, 201):
                    error_msg = response.json().get("message", "Unknown error")
                    return SMSResult(
                        success=False,
                        error=error_msg,
                        status=SMSStatus.FAILED
                    )

                data = response.json()
                message_sid = data.get("sid", "")

                logger.info(f"Sent SignalWire SMS {message_sid} to {to_number}")

                return SMSResult(
                    success=True,
                    message_id=message_sid,
                    provider_message_id=message_sid,
                    status=self._map_sms_status(data.get("status", "")),
                    segments=data.get("num_segments", 1),
                    metadata={
                        "from_number": from_num,
                        "to_number": to_number,
                        **(metadata or {})
                    }
                )

        except Exception as e:
            logger.error(f"Failed to send SignalWire SMS: {e}")
            return SMSResult(
                success=False,
                error=str(e),
                status=SMSStatus.FAILED
            )

    async def get_sms_status(self, message_id: str) -> Optional[SMSStatus]:
        """Get the current status of a SignalWire SMS."""
        if not self.is_configured:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._get_base_url()}/Messages/{message_id}.json",
                    auth=self._get_auth(),
                    timeout=10.0
                )
                if response.status_code != 200:
                    return None

                data = response.json()
                return self._map_sms_status(data.get("status", ""))
        except Exception as e:
            logger.error(f"Failed to get SignalWire SMS status: {e}")
            return None

    def _map_sms_status(self, sw_status: str) -> SMSStatus:
        """Map SignalWire SMS status to standard SMSStatus."""
        status_map = {
            "queued": SMSStatus.QUEUED,
            "sending": SMSStatus.SENDING,
            "sent": SMSStatus.SENT,
            "delivered": SMSStatus.DELIVERED,
            "failed": SMSStatus.FAILED,
            "undelivered": SMSStatus.UNDELIVERED,
        }
        return status_map.get(sw_status, SMSStatus.QUEUED)

    # =========================================================================
    # Phone Number Methods
    # =========================================================================

    async def list_phone_numbers(self) -> List[PhoneNumber]:
        """List all SignalWire phone numbers on the account."""
        if not self.is_configured:
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._get_base_url()}/IncomingPhoneNumbers.json",
                    auth=self._get_auth(),
                    timeout=30.0
                )
                if response.status_code != 200:
                    return []

                data = response.json().get("incoming_phone_numbers", [])
                return [
                    PhoneNumber(
                        number=num.get("phone_number", ""),
                        provider=self.provider_name,
                        capabilities=self._get_capabilities(num),
                        friendly_name=num.get("friendly_name", ""),
                        region=num.get("locality", ""),
                        metadata={
                            "sid": num.get("sid", ""),
                        }
                    )
                    for num in data
                ]
        except Exception as e:
            logger.error(f"Failed to list SignalWire numbers: {e}")
            return []

    def _get_capabilities(self, num: Dict[str, Any]) -> List[str]:
        """Extract capabilities from SignalWire number."""
        caps = []
        capabilities = num.get("capabilities", {})
        if capabilities.get("voice"):
            caps.append("voice")
        if capabilities.get("sms"):
            caps.append("sms")
        if capabilities.get("mms"):
            caps.append("mms")
        return caps if caps else ["voice", "sms"]

    async def search_available_numbers(
        self,
        country: str = "US",
        area_code: Optional[str] = None,
        contains: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[PhoneNumber]:
        """Search for available SignalWire phone numbers."""
        if not self.is_configured:
            return []

        try:
            params = {"PageSize": limit}
            if area_code:
                params["AreaCode"] = area_code
            if contains:
                params["Contains"] = contains

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._get_base_url()}/AvailablePhoneNumbers/{country}/Local.json",
                    auth=self._get_auth(),
                    params=params,
                    timeout=30.0
                )
                if response.status_code != 200:
                    return []

                data = response.json().get("available_phone_numbers", [])
                return [
                    PhoneNumber(
                        number=num.get("phone_number", ""),
                        provider=self.provider_name,
                        capabilities=capabilities or ["voice", "sms"],
                        friendly_name=num.get("friendly_name", ""),
                        region=num.get("locality", ""),
                    )
                    for num in data
                ]
        except Exception as e:
            logger.error(f"Failed to search SignalWire numbers: {e}")
            return []

    async def purchase_number(self, number: str) -> Optional[PhoneNumber]:
        """Purchase a SignalWire phone number."""
        if not self.is_configured:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._get_base_url()}/IncomingPhoneNumbers.json",
                    auth=self._get_auth(),
                    data={"PhoneNumber": number},
                    timeout=30.0
                )
                if response.status_code not in (200, 201):
                    return None

                data = response.json()
                logger.info(f"Purchased SignalWire number {number}")

                return PhoneNumber(
                    number=data.get("phone_number", number),
                    provider=self.provider_name,
                    capabilities=self._get_capabilities(data),
                    friendly_name=data.get("friendly_name", ""),
                    metadata={"sid": data.get("sid", "")}
                )
        except Exception as e:
            logger.error(f"Failed to purchase SignalWire number {number}: {e}")
            return None

    async def release_number(self, number: str) -> bool:
        """Release a SignalWire phone number."""
        if not self.is_configured:
            return False

        try:
            # First find the number SID
            numbers = await self.list_phone_numbers()
            number_data = next((n for n in numbers if n.number == number), None)
            if not number_data or not number_data.metadata.get("sid"):
                return False

            sid = number_data.metadata["sid"]

            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self._get_base_url()}/IncomingPhoneNumbers/{sid}.json",
                    auth=self._get_auth(),
                    timeout=30.0
                )
                success = response.status_code in (200, 204)
                if success:
                    logger.info(f"Released SignalWire number {number}")
                return success
        except Exception as e:
            logger.error(f"Failed to release SignalWire number {number}: {e}")
            return False

    # =========================================================================
    # Webhook Methods
    # =========================================================================

    def parse_webhook_call(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse SignalWire call webhook data (Twilio-compatible)."""
        return {
            "call_id": data.get("CallSid", ""),
            "from_number": data.get("From", ""),
            "to_number": data.get("To", ""),
            "direction": CallDirection.INBOUND if data.get("Direction") == "inbound" else CallDirection.OUTBOUND,
            "status": self._map_call_status(data.get("CallStatus", "")),
            "duration": int(data.get("CallDuration", 0)) if data.get("CallDuration") else None,
            "metadata": {
                "account_sid": data.get("AccountSid", ""),
            }
        }

    def parse_webhook_sms(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse SignalWire SMS webhook data (Twilio-compatible)."""
        return {
            "message_id": data.get("MessageSid", ""),
            "from_number": data.get("From", ""),
            "to_number": data.get("To", ""),
            "body": data.get("Body", ""),
            "status": self._map_sms_status(data.get("SmsStatus", "")),
            "metadata": {
                "account_sid": data.get("AccountSid", ""),
                "num_segments": int(data.get("NumSegments", 1)),
            }
        }

    def validate_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        url: Optional[str] = None,
    ) -> bool:
        """Validate SignalWire webhook signature (Twilio-compatible)."""
        if not self.config.auth_token or not url:
            return False

        try:
            # SignalWire uses same validation as Twilio
            params = dict(pair.split("=") for pair in payload.decode().split("&") if "=" in pair)
            sorted_params = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            data_to_sign = url + sorted_params

            expected = base64.b64encode(
                hmac.new(
                    self.config.auth_token.encode(),
                    data_to_sign.encode(),
                    hashlib.sha1
                ).digest()
            ).decode()

            return hmac.compare_digest(signature, expected)
        except Exception as e:
            logger.error(f"SignalWire signature validation error: {e}")
            return False
