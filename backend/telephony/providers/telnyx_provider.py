"""
Telnyx Telephony Provider

Implements TelephonyProvider interface for Telnyx.
Supports voice calls via SIP trunk to LiveKit and SMS messaging.

Telnyx uses TeXML (similar to TwiML) for voice call control.
"""

import hmac
import hashlib
import base64
import json
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

TELNYX_API_BASE = "https://api.telnyx.com/v2"


class TelnyxProvider(TelephonyProvider):
    """Telnyx telephony provider implementation."""

    @property
    def provider_name(self) -> str:
        return "telnyx"

    @property
    def is_configured(self) -> bool:
        return bool(self.config.api_key)

    def _get_headers(self) -> Dict[str, str]:
        """Get API headers for Telnyx requests."""
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    async def validate_credentials(self) -> bool:
        """Validate Telnyx credentials by fetching account balance."""
        if not self.is_configured:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{TELNYX_API_BASE}/balance",
                    headers=self._get_headers(),
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Telnyx credential validation failed: {e}")
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
        """Initiate an outbound call via Telnyx."""
        if not self.is_configured:
            return CallResult(
                success=False,
                error="Telnyx not configured",
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
            webhook_url = f"{webhook_base}/telephony/telnyx/voice/connect?room={room_name}"

            # Create call via Telnyx API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{TELNYX_API_BASE}/calls",
                    headers=self._get_headers(),
                    json={
                        "connection_id": self.config.extra.get("connection_id", ""),
                        "to": to_number,
                        "from": from_num,
                        "webhook_url": webhook_url,
                        "webhook_url_method": "POST",
                    },
                    timeout=30.0
                )

                if response.status_code not in (200, 201):
                    error_msg = response.json().get("errors", [{}])[0].get("detail", "Unknown error")
                    return CallResult(
                        success=False,
                        error=error_msg,
                        status=CallStatus.FAILED
                    )

                data = response.json().get("data", {})
                call_control_id = data.get("call_control_id", "")

                logger.info(f"Initiated Telnyx call {call_control_id} to {to_number}")

                return CallResult(
                    success=True,
                    call_id=call_control_id,
                    provider_call_id=call_control_id,
                    room_name=room_name,
                    status=CallStatus.INITIATING,
                    metadata={
                        "from_number": from_num,
                        "to_number": to_number,
                        "call_leg_id": data.get("call_leg_id", ""),
                        **(metadata or {})
                    }
                )

        except Exception as e:
            logger.error(f"Failed to initiate Telnyx call: {e}")
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
        """Generate TeXML response for connecting call to LiveKit."""
        sip_host = sip_uri or self.config.sip_uri

        if sip_host:
            # TeXML to connect to LiveKit via SIP
            full_sip_uri = f"sip:{room_name}@{sip_host}"
            texml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial callerId="{caller_number}" timeout="30">
        <Sip>{full_sip_uri}</Sip>
    </Dial>
</Response>"""
            logger.info(f"Generated TeXML to connect to {full_sip_uri}")
        else:
            # Fallback message if SIP not configured
            texml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">The AI assistant is not currently available. Please try again later.</Say>
    <Hangup/>
</Response>"""

        return texml

    async def end_call(self, call_id: str) -> bool:
        """End an active Telnyx call."""
        if not self.is_configured:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{TELNYX_API_BASE}/calls/{call_id}/actions/hangup",
                    headers=self._get_headers(),
                    timeout=10.0
                )
                success = response.status_code == 200
                if success:
                    logger.info(f"Ended Telnyx call {call_id}")
                return success
        except Exception as e:
            logger.error(f"Failed to end Telnyx call {call_id}: {e}")
            return False

    async def get_call_status(self, call_id: str) -> Optional[CallStatus]:
        """Get the current status of a Telnyx call."""
        if not self.is_configured:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{TELNYX_API_BASE}/calls/{call_id}",
                    headers=self._get_headers(),
                    timeout=10.0
                )
                if response.status_code != 200:
                    return None

                data = response.json().get("data", {})
                return self._map_call_status(data.get("state", ""))
        except Exception as e:
            logger.error(f"Failed to get Telnyx call status: {e}")
            return None

    def _map_call_status(self, telnyx_status: str) -> CallStatus:
        """Map Telnyx call status to standard CallStatus."""
        status_map = {
            "parked": CallStatus.INITIATING,
            "bridging": CallStatus.RINGING,
            "active": CallStatus.IN_PROGRESS,
            "hangup": CallStatus.COMPLETED,
            "failed": CallStatus.FAILED,
        }
        return status_map.get(telnyx_status, CallStatus.INITIATING)

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
        """Send an SMS via Telnyx."""
        if not self.is_configured:
            return SMSResult(
                success=False,
                error="Telnyx not configured",
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
                    f"{TELNYX_API_BASE}/messages",
                    headers=self._get_headers(),
                    json={
                        "from": from_num,
                        "to": to_number,
                        "text": message,
                        "type": "SMS",
                    },
                    timeout=30.0
                )

                if response.status_code not in (200, 201):
                    error_msg = response.json().get("errors", [{}])[0].get("detail", "Unknown error")
                    return SMSResult(
                        success=False,
                        error=error_msg,
                        status=SMSStatus.FAILED
                    )

                data = response.json().get("data", {})
                message_id = data.get("id", "")

                logger.info(f"Sent Telnyx SMS {message_id} to {to_number}")

                return SMSResult(
                    success=True,
                    message_id=message_id,
                    provider_message_id=message_id,
                    status=SMSStatus.QUEUED,
                    segments=data.get("parts", 1),
                    metadata={
                        "from_number": from_num,
                        "to_number": to_number,
                        **(metadata or {})
                    }
                )

        except Exception as e:
            logger.error(f"Failed to send Telnyx SMS: {e}")
            return SMSResult(
                success=False,
                error=str(e),
                status=SMSStatus.FAILED
            )

    async def get_sms_status(self, message_id: str) -> Optional[SMSStatus]:
        """Get the current status of a Telnyx SMS."""
        if not self.is_configured:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{TELNYX_API_BASE}/messages/{message_id}",
                    headers=self._get_headers(),
                    timeout=10.0
                )
                if response.status_code != 200:
                    return None

                data = response.json().get("data", {})
                return self._map_sms_status(data.get("to", [{}])[0].get("status", ""))
        except Exception as e:
            logger.error(f"Failed to get Telnyx SMS status: {e}")
            return None

    def _map_sms_status(self, telnyx_status: str) -> SMSStatus:
        """Map Telnyx SMS status to standard SMSStatus."""
        status_map = {
            "queued": SMSStatus.QUEUED,
            "sending": SMSStatus.SENDING,
            "sent": SMSStatus.SENT,
            "delivered": SMSStatus.DELIVERED,
            "delivery_failed": SMSStatus.FAILED,
            "sending_failed": SMSStatus.FAILED,
        }
        return status_map.get(telnyx_status, SMSStatus.QUEUED)

    # =========================================================================
    # Phone Number Methods
    # =========================================================================

    async def list_phone_numbers(self) -> List[PhoneNumber]:
        """List all Telnyx phone numbers on the account."""
        if not self.is_configured:
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{TELNYX_API_BASE}/phone_numbers",
                    headers=self._get_headers(),
                    timeout=30.0
                )
                if response.status_code != 200:
                    return []

                data = response.json().get("data", [])
                return [
                    PhoneNumber(
                        number=num.get("phone_number", ""),
                        provider=self.provider_name,
                        capabilities=self._get_capabilities(num),
                        friendly_name=num.get("connection_name", ""),
                        metadata={
                            "id": num.get("id", ""),
                            "status": num.get("status", ""),
                        }
                    )
                    for num in data
                ]
        except Exception as e:
            logger.error(f"Failed to list Telnyx numbers: {e}")
            return []

    def _get_capabilities(self, num: Dict[str, Any]) -> List[str]:
        """Extract capabilities from Telnyx number."""
        caps = []
        if num.get("messaging_profile_id"):
            caps.append("sms")
        if num.get("connection_id"):
            caps.append("voice")
        return caps if caps else ["voice", "sms"]

    async def search_available_numbers(
        self,
        country: str = "US",
        area_code: Optional[str] = None,
        contains: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[PhoneNumber]:
        """Search for available Telnyx phone numbers."""
        if not self.is_configured:
            return []

        try:
            params = {
                "filter[country_code]": country,
                "filter[limit]": limit,
            }
            if area_code:
                params["filter[national_destination_code]"] = area_code
            if contains:
                params["filter[phone_number][contains]"] = contains

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{TELNYX_API_BASE}/available_phone_numbers",
                    headers=self._get_headers(),
                    params=params,
                    timeout=30.0
                )
                if response.status_code != 200:
                    return []

                data = response.json().get("data", [])
                return [
                    PhoneNumber(
                        number=num.get("phone_number", ""),
                        provider=self.provider_name,
                        capabilities=capabilities or ["voice", "sms"],
                        region=num.get("region_information", [{}])[0].get("region_name", ""),
                        monthly_cost=float(num.get("cost_information", {}).get("monthly_cost", 0)),
                    )
                    for num in data
                ]
        except Exception as e:
            logger.error(f"Failed to search Telnyx numbers: {e}")
            return []

    async def purchase_number(self, number: str) -> Optional[PhoneNumber]:
        """Purchase a Telnyx phone number."""
        if not self.is_configured:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{TELNYX_API_BASE}/number_orders",
                    headers=self._get_headers(),
                    json={
                        "phone_numbers": [{"phone_number": number}],
                    },
                    timeout=30.0
                )
                if response.status_code not in (200, 201):
                    return None

                logger.info(f"Purchased Telnyx number {number}")

                return PhoneNumber(
                    number=number,
                    provider=self.provider_name,
                    capabilities=["voice", "sms"],
                )
        except Exception as e:
            logger.error(f"Failed to purchase Telnyx number {number}: {e}")
            return None

    async def release_number(self, number: str) -> bool:
        """Release a Telnyx phone number."""
        if not self.is_configured:
            return False

        try:
            # First find the number ID
            numbers = await self.list_phone_numbers()
            number_data = next((n for n in numbers if n.number == number), None)
            if not number_data or not number_data.metadata.get("id"):
                return False

            number_id = number_data.metadata["id"]

            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{TELNYX_API_BASE}/phone_numbers/{number_id}",
                    headers=self._get_headers(),
                    timeout=30.0
                )
                success = response.status_code in (200, 204)
                if success:
                    logger.info(f"Released Telnyx number {number}")
                return success
        except Exception as e:
            logger.error(f"Failed to release Telnyx number {number}: {e}")
            return False

    # =========================================================================
    # Webhook Methods
    # =========================================================================

    def parse_webhook_call(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Telnyx call webhook data."""
        payload = data.get("data", {}).get("payload", {})
        return {
            "call_id": payload.get("call_control_id", ""),
            "from_number": payload.get("from", ""),
            "to_number": payload.get("to", ""),
            "direction": CallDirection.INBOUND if payload.get("direction") == "incoming" else CallDirection.OUTBOUND,
            "status": self._map_call_status(payload.get("state", "")),
            "duration": None,  # Telnyx provides duration in hangup event
            "metadata": {
                "call_leg_id": payload.get("call_leg_id", ""),
                "connection_id": payload.get("connection_id", ""),
                "event_type": data.get("data", {}).get("event_type", ""),
            }
        }

    def parse_webhook_sms(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Telnyx SMS webhook data."""
        payload = data.get("data", {}).get("payload", {})
        return {
            "message_id": payload.get("id", ""),
            "from_number": payload.get("from", {}).get("phone_number", ""),
            "to_number": payload.get("to", [{}])[0].get("phone_number", ""),
            "body": payload.get("text", ""),
            "status": self._map_sms_status(payload.get("to", [{}])[0].get("status", "")),
            "metadata": {
                "event_type": data.get("data", {}).get("event_type", ""),
                "record_type": data.get("data", {}).get("record_type", ""),
            }
        }

    def validate_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        url: Optional[str] = None,
    ) -> bool:
        """Validate Telnyx webhook signature."""
        # Telnyx uses a public key for signature verification
        # This is a simplified version; production should use proper verification
        if not signature:
            return False

        try:
            # Telnyx provides signature in header: telnyx-signature-ed25519
            # Full implementation requires ed25519 signature verification
            # For now, basic presence check
            return len(signature) > 0
        except Exception as e:
            logger.error(f"Telnyx signature validation error: {e}")
            return False
