"""
Plivo Telephony Provider

Implements TelephonyProvider interface for Plivo.
Supports voice calls via SIP trunk to LiveKit and SMS messaging.

Plivo uses XML for voice call control (similar to TwiML).
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

PLIVO_API_BASE = "https://api.plivo.com/v1/Account"


class PlivoProvider(TelephonyProvider):
    """Plivo telephony provider implementation."""

    @property
    def provider_name(self) -> str:
        return "plivo"

    @property
    def is_configured(self) -> bool:
        return bool(self.config.account_sid and self.config.auth_token)

    def _get_auth(self) -> tuple:
        """Get HTTP Basic Auth tuple for Plivo."""
        return (self.config.account_sid, self.config.auth_token)

    def _get_base_url(self) -> str:
        """Get the base API URL for this account."""
        return f"{PLIVO_API_BASE}/{self.config.account_sid}"

    async def validate_credentials(self) -> bool:
        """Validate Plivo credentials by fetching account details."""
        if not self.is_configured:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._get_base_url()}/",
                    auth=self._get_auth(),
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Plivo credential validation failed: {e}")
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
        """Initiate an outbound call via Plivo."""
        if not self.is_configured:
            return CallResult(
                success=False,
                error="Plivo not configured",
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
            answer_url = f"{webhook_base}/telephony/plivo/voice/connect?room={room_name}"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._get_base_url()}/Call/",
                    auth=self._get_auth(),
                    json={
                        "from": from_num,
                        "to": to_number,
                        "answer_url": answer_url,
                        "answer_method": "POST",
                    },
                    timeout=30.0
                )

                if response.status_code not in (200, 201, 202):
                    error_msg = response.json().get("error", "Unknown error")
                    return CallResult(
                        success=False,
                        error=error_msg,
                        status=CallStatus.FAILED
                    )

                data = response.json()
                call_uuid = data.get("request_uuid", "")

                logger.info(f"Initiated Plivo call {call_uuid} to {to_number}")

                return CallResult(
                    success=True,
                    call_id=call_uuid,
                    provider_call_id=call_uuid,
                    room_name=room_name,
                    status=CallStatus.INITIATING,
                    metadata={
                        "from_number": from_num,
                        "to_number": to_number,
                        **(metadata or {})
                    }
                )

        except Exception as e:
            logger.error(f"Failed to initiate Plivo call: {e}")
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
        """Generate Plivo XML response for connecting call to LiveKit."""
        sip_host = sip_uri or self.config.sip_uri

        if sip_host:
            # Plivo XML to connect to LiveKit via SIP
            full_sip_uri = f"sip:{room_name}@{sip_host}"
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial callerId="{caller_number}" timeout="30">
        <User>{full_sip_uri}</User>
    </Dial>
</Response>"""
            logger.info(f"Generated Plivo XML to connect to {full_sip_uri}")
        else:
            # Fallback message if SIP not configured
            xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak voice="WOMAN">The AI assistant is not currently available. Please try again later.</Speak>
    <Hangup/>
</Response>"""

        return xml

    async def end_call(self, call_id: str) -> bool:
        """End an active Plivo call."""
        if not self.is_configured:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self._get_base_url()}/Call/{call_id}/",
                    auth=self._get_auth(),
                    timeout=10.0
                )
                success = response.status_code in (200, 204)
                if success:
                    logger.info(f"Ended Plivo call {call_id}")
                return success
        except Exception as e:
            logger.error(f"Failed to end Plivo call {call_id}: {e}")
            return False

    async def get_call_status(self, call_id: str) -> Optional[CallStatus]:
        """Get the current status of a Plivo call."""
        if not self.is_configured:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._get_base_url()}/Call/{call_id}/",
                    auth=self._get_auth(),
                    timeout=10.0
                )
                if response.status_code != 200:
                    return None

                data = response.json()
                return self._map_call_status(data.get("call_status", ""))
        except Exception as e:
            logger.error(f"Failed to get Plivo call status: {e}")
            return None

    def _map_call_status(self, plivo_status: str) -> CallStatus:
        """Map Plivo call status to standard CallStatus."""
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
        return status_map.get(plivo_status, CallStatus.INITIATING)

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
        """Send an SMS via Plivo."""
        if not self.is_configured:
            return SMSResult(
                success=False,
                error="Plivo not configured",
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
                    f"{self._get_base_url()}/Message/",
                    auth=self._get_auth(),
                    json={
                        "src": from_num,
                        "dst": to_number,
                        "text": message,
                    },
                    timeout=30.0
                )

                if response.status_code not in (200, 201, 202):
                    error_msg = response.json().get("error", "Unknown error")
                    return SMSResult(
                        success=False,
                        error=error_msg,
                        status=SMSStatus.FAILED
                    )

                data = response.json()
                message_uuid = data.get("message_uuid", [""])[0]

                logger.info(f"Sent Plivo SMS {message_uuid} to {to_number}")

                return SMSResult(
                    success=True,
                    message_id=message_uuid,
                    provider_message_id=message_uuid,
                    status=SMSStatus.QUEUED,
                    metadata={
                        "from_number": from_num,
                        "to_number": to_number,
                        **(metadata or {})
                    }
                )

        except Exception as e:
            logger.error(f"Failed to send Plivo SMS: {e}")
            return SMSResult(
                success=False,
                error=str(e),
                status=SMSStatus.FAILED
            )

    async def get_sms_status(self, message_id: str) -> Optional[SMSStatus]:
        """Get the current status of a Plivo SMS."""
        if not self.is_configured:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._get_base_url()}/Message/{message_id}/",
                    auth=self._get_auth(),
                    timeout=10.0
                )
                if response.status_code != 200:
                    return None

                data = response.json()
                return self._map_sms_status(data.get("message_state", ""))
        except Exception as e:
            logger.error(f"Failed to get Plivo SMS status: {e}")
            return None

    def _map_sms_status(self, plivo_status: str) -> SMSStatus:
        """Map Plivo SMS status to standard SMSStatus."""
        status_map = {
            "queued": SMSStatus.QUEUED,
            "sending": SMSStatus.SENDING,
            "sent": SMSStatus.SENT,
            "delivered": SMSStatus.DELIVERED,
            "failed": SMSStatus.FAILED,
            "undelivered": SMSStatus.UNDELIVERED,
        }
        return status_map.get(plivo_status, SMSStatus.QUEUED)

    # =========================================================================
    # Phone Number Methods
    # =========================================================================

    async def list_phone_numbers(self) -> List[PhoneNumber]:
        """List all Plivo phone numbers on the account."""
        if not self.is_configured:
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._get_base_url()}/Number/",
                    auth=self._get_auth(),
                    timeout=30.0
                )
                if response.status_code != 200:
                    return []

                data = response.json().get("objects", [])
                return [
                    PhoneNumber(
                        number=num.get("number", ""),
                        provider=self.provider_name,
                        capabilities=self._get_capabilities(num),
                        friendly_name=num.get("alias", ""),
                        region=num.get("region", ""),
                        monthly_cost=float(num.get("monthly_rental_rate", 0)),
                        metadata={
                            "resource_uri": num.get("resource_uri", ""),
                        }
                    )
                    for num in data
                ]
        except Exception as e:
            logger.error(f"Failed to list Plivo numbers: {e}")
            return []

    def _get_capabilities(self, num: Dict[str, Any]) -> List[str]:
        """Extract capabilities from Plivo number."""
        caps = []
        if num.get("voice_enabled"):
            caps.append("voice")
        if num.get("sms_enabled"):
            caps.append("sms")
        if num.get("mms_enabled"):
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
        """Search for available Plivo phone numbers."""
        if not self.is_configured:
            return []

        try:
            params = {
                "country_iso": country,
                "limit": limit,
            }
            if area_code:
                params["pattern"] = f"{area_code}"
            if contains:
                params["pattern"] = contains

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._get_base_url()}/PhoneNumber/",
                    auth=self._get_auth(),
                    params=params,
                    timeout=30.0
                )
                if response.status_code != 200:
                    return []

                data = response.json().get("objects", [])
                return [
                    PhoneNumber(
                        number=num.get("number", ""),
                        provider=self.provider_name,
                        capabilities=capabilities or ["voice", "sms"],
                        region=num.get("region", ""),
                        monthly_cost=float(num.get("monthly_rental_rate", 0)),
                    )
                    for num in data
                ]
        except Exception as e:
            logger.error(f"Failed to search Plivo numbers: {e}")
            return []

    async def purchase_number(self, number: str) -> Optional[PhoneNumber]:
        """Purchase a Plivo phone number."""
        if not self.is_configured:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._get_base_url()}/PhoneNumber/{number}/",
                    auth=self._get_auth(),
                    timeout=30.0
                )
                if response.status_code not in (200, 201):
                    return None

                logger.info(f"Purchased Plivo number {number}")

                return PhoneNumber(
                    number=number,
                    provider=self.provider_name,
                    capabilities=["voice", "sms"],
                )
        except Exception as e:
            logger.error(f"Failed to purchase Plivo number {number}: {e}")
            return None

    async def release_number(self, number: str) -> bool:
        """Release a Plivo phone number."""
        if not self.is_configured:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self._get_base_url()}/Number/{number}/",
                    auth=self._get_auth(),
                    timeout=30.0
                )
                success = response.status_code in (200, 204)
                if success:
                    logger.info(f"Released Plivo number {number}")
                return success
        except Exception as e:
            logger.error(f"Failed to release Plivo number {number}: {e}")
            return False

    # =========================================================================
    # Webhook Methods
    # =========================================================================

    def parse_webhook_call(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Plivo call webhook data."""
        return {
            "call_id": data.get("CallUUID", ""),
            "from_number": data.get("From", ""),
            "to_number": data.get("To", ""),
            "direction": CallDirection.INBOUND if data.get("Direction") == "inbound" else CallDirection.OUTBOUND,
            "status": self._map_call_status(data.get("CallStatus", "")),
            "duration": int(data.get("Duration", 0)) if data.get("Duration") else None,
            "metadata": {
                "event": data.get("Event", ""),
                "call_type": data.get("CallType", ""),
            }
        }

    def parse_webhook_sms(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Plivo SMS webhook data."""
        return {
            "message_id": data.get("MessageUUID", ""),
            "from_number": data.get("From", ""),
            "to_number": data.get("To", ""),
            "body": data.get("Text", ""),
            "status": self._map_sms_status(data.get("Status", "")),
            "metadata": {
                "type": data.get("Type", ""),
                "total_amount": data.get("TotalAmount", ""),
            }
        }

    def validate_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        url: Optional[str] = None,
    ) -> bool:
        """Validate Plivo webhook signature."""
        if not self.config.auth_token or not url:
            return False

        try:
            # Plivo signature validation
            expected = base64.b64encode(
                hmac.new(
                    self.config.auth_token.encode(),
                    url.encode(),
                    hashlib.sha256
                ).digest()
            ).decode()
            return hmac.compare_digest(signature, expected)
        except Exception as e:
            logger.error(f"Plivo signature validation error: {e}")
            return False
