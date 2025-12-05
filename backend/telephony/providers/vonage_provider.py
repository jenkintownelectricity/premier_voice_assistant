"""
Vonage (formerly Nexmo) Telephony Provider

Implements TelephonyProvider interface for Vonage.
Supports voice calls via SIP trunk to LiveKit and SMS messaging.

Vonage uses NCCO (Nexmo Call Control Objects) JSON for voice call control.
"""

import hmac
import hashlib
import jwt
import time
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

VONAGE_API_BASE = "https://api.nexmo.com"
VONAGE_REST_BASE = "https://rest.nexmo.com"


class VonageProvider(TelephonyProvider):
    """Vonage telephony provider implementation."""

    @property
    def provider_name(self) -> str:
        return "vonage"

    @property
    def is_configured(self) -> bool:
        return bool(self.config.api_key and self.config.api_secret)

    def _get_auth_params(self) -> Dict[str, str]:
        """Get query params for Vonage REST API authentication."""
        return {
            "api_key": self.config.api_key,
            "api_secret": self.config.api_secret,
        }

    def _get_jwt_headers(self) -> Dict[str, str]:
        """Get headers with JWT for Vonage Voice API."""
        # Vonage Voice API uses JWT authentication
        # For simplicity, using API key/secret; production should use app JWT
        return {
            "Content-Type": "application/json",
        }

    async def validate_credentials(self) -> bool:
        """Validate Vonage credentials by fetching account balance."""
        if not self.is_configured:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{VONAGE_REST_BASE}/account/get-balance",
                    params=self._get_auth_params(),
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Vonage credential validation failed: {e}")
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
        """Initiate an outbound call via Vonage."""
        if not self.is_configured:
            return CallResult(
                success=False,
                error="Vonage not configured",
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
            answer_url = f"{webhook_base}/telephony/vonage/voice/connect?room={room_name}"
            event_url = f"{webhook_base}/telephony/vonage/voice/status"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{VONAGE_API_BASE}/v1/calls",
                    headers=self._get_jwt_headers(),
                    params=self._get_auth_params(),
                    json={
                        "to": [{"type": "phone", "number": to_number.replace("+", "")}],
                        "from": {"type": "phone", "number": from_num.replace("+", "")},
                        "answer_url": [answer_url],
                        "event_url": [event_url],
                    },
                    timeout=30.0
                )

                if response.status_code not in (200, 201):
                    error_msg = response.json().get("title", "Unknown error")
                    return CallResult(
                        success=False,
                        error=error_msg,
                        status=CallStatus.FAILED
                    )

                data = response.json()
                call_uuid = data.get("uuid", "")

                logger.info(f"Initiated Vonage call {call_uuid} to {to_number}")

                return CallResult(
                    success=True,
                    call_id=call_uuid,
                    provider_call_id=call_uuid,
                    room_name=room_name,
                    status=self._map_call_status(data.get("status", "")),
                    metadata={
                        "from_number": from_num,
                        "to_number": to_number,
                        "conversation_uuid": data.get("conversation_uuid", ""),
                        **(metadata or {})
                    }
                )

        except Exception as e:
            logger.error(f"Failed to initiate Vonage call: {e}")
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
        """Generate NCCO JSON response for connecting call to LiveKit."""
        import json as json_module

        sip_host = sip_uri or self.config.sip_uri

        if sip_host:
            # NCCO to connect to LiveKit via SIP
            full_sip_uri = f"sip:{room_name}@{sip_host}"
            ncco = [
                {
                    "action": "connect",
                    "timeout": 30,
                    "from": caller_number,
                    "endpoint": [
                        {
                            "type": "sip",
                            "uri": full_sip_uri,
                        }
                    ]
                }
            ]
            logger.info(f"Generated NCCO to connect to {full_sip_uri}")
        else:
            # Fallback message if SIP not configured
            ncco = [
                {
                    "action": "talk",
                    "text": "The AI assistant is not currently available. Please try again later.",
                    "voiceName": "Amy"
                }
            ]

        return json_module.dumps(ncco)

    async def end_call(self, call_id: str) -> bool:
        """End an active Vonage call."""
        if not self.is_configured:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{VONAGE_API_BASE}/v1/calls/{call_id}",
                    headers=self._get_jwt_headers(),
                    params=self._get_auth_params(),
                    json={"action": "hangup"},
                    timeout=10.0
                )
                success = response.status_code in (200, 204)
                if success:
                    logger.info(f"Ended Vonage call {call_id}")
                return success
        except Exception as e:
            logger.error(f"Failed to end Vonage call {call_id}: {e}")
            return False

    async def get_call_status(self, call_id: str) -> Optional[CallStatus]:
        """Get the current status of a Vonage call."""
        if not self.is_configured:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{VONAGE_API_BASE}/v1/calls/{call_id}",
                    headers=self._get_jwt_headers(),
                    params=self._get_auth_params(),
                    timeout=10.0
                )
                if response.status_code != 200:
                    return None

                data = response.json()
                return self._map_call_status(data.get("status", ""))
        except Exception as e:
            logger.error(f"Failed to get Vonage call status: {e}")
            return None

    def _map_call_status(self, vonage_status: str) -> CallStatus:
        """Map Vonage call status to standard CallStatus."""
        status_map = {
            "started": CallStatus.INITIATING,
            "ringing": CallStatus.RINGING,
            "answered": CallStatus.IN_PROGRESS,
            "completed": CallStatus.COMPLETED,
            "failed": CallStatus.FAILED,
            "busy": CallStatus.BUSY,
            "timeout": CallStatus.NO_ANSWER,
            "cancelled": CallStatus.CANCELLED,
            "rejected": CallStatus.FAILED,
        }
        return status_map.get(vonage_status, CallStatus.INITIATING)

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
        """Send an SMS via Vonage."""
        if not self.is_configured:
            return SMSResult(
                success=False,
                error="Vonage not configured",
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

            # Use Messages API (newer) or SMS API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{VONAGE_REST_BASE}/sms/json",
                    data={
                        **self._get_auth_params(),
                        "from": from_num,
                        "to": to_number.replace("+", ""),
                        "text": message,
                    },
                    timeout=30.0
                )

                data = response.json()
                messages = data.get("messages", [])

                if not messages or messages[0].get("status") != "0":
                    error_msg = messages[0].get("error-text", "Unknown error") if messages else "No response"
                    return SMSResult(
                        success=False,
                        error=error_msg,
                        status=SMSStatus.FAILED
                    )

                message_id = messages[0].get("message-id", "")

                logger.info(f"Sent Vonage SMS {message_id} to {to_number}")

                return SMSResult(
                    success=True,
                    message_id=message_id,
                    provider_message_id=message_id,
                    status=SMSStatus.SENT,
                    segments=len(messages),
                    metadata={
                        "from_number": from_num,
                        "to_number": to_number,
                        "remaining_balance": messages[0].get("remaining-balance", ""),
                        **(metadata or {})
                    }
                )

        except Exception as e:
            logger.error(f"Failed to send Vonage SMS: {e}")
            return SMSResult(
                success=False,
                error=str(e),
                status=SMSStatus.FAILED
            )

    async def get_sms_status(self, message_id: str) -> Optional[SMSStatus]:
        """Get the current status of a Vonage SMS."""
        # Vonage requires webhook for delivery receipts
        # Cannot query message status directly via API
        logger.warning("Vonage SMS status check requires webhook; returning None")
        return None

    def _map_sms_status(self, vonage_status: str) -> SMSStatus:
        """Map Vonage SMS status to standard SMSStatus."""
        status_map = {
            "submitted": SMSStatus.QUEUED,
            "delivered": SMSStatus.DELIVERED,
            "expired": SMSStatus.FAILED,
            "failed": SMSStatus.FAILED,
            "rejected": SMSStatus.FAILED,
            "accepted": SMSStatus.SENT,
            "buffered": SMSStatus.QUEUED,
        }
        return status_map.get(vonage_status, SMSStatus.QUEUED)

    # =========================================================================
    # Phone Number Methods
    # =========================================================================

    async def list_phone_numbers(self) -> List[PhoneNumber]:
        """List all Vonage phone numbers on the account."""
        if not self.is_configured:
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{VONAGE_REST_BASE}/account/numbers",
                    params=self._get_auth_params(),
                    timeout=30.0
                )
                if response.status_code != 200:
                    return []

                data = response.json().get("numbers", [])
                return [
                    PhoneNumber(
                        number=num.get("msisdn", ""),
                        provider=self.provider_name,
                        capabilities=self._get_capabilities(num),
                        friendly_name=num.get("app_id", ""),
                        region=num.get("country", ""),
                        metadata={
                            "type": num.get("type", ""),
                        }
                    )
                    for num in data
                ]
        except Exception as e:
            logger.error(f"Failed to list Vonage numbers: {e}")
            return []

    def _get_capabilities(self, num: Dict[str, Any]) -> List[str]:
        """Extract capabilities from Vonage number."""
        caps = []
        features = num.get("features", [])
        if "VOICE" in features:
            caps.append("voice")
        if "SMS" in features:
            caps.append("sms")
        if "MMS" in features:
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
        """Search for available Vonage phone numbers."""
        if not self.is_configured:
            return []

        try:
            params = {
                **self._get_auth_params(),
                "country": country,
                "size": limit,
            }
            if area_code:
                params["pattern"] = area_code
            if contains:
                params["pattern"] = contains
            if capabilities:
                if "voice" in capabilities:
                    params["features"] = "VOICE"
                if "sms" in capabilities:
                    params["features"] = "SMS"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{VONAGE_REST_BASE}/number/search",
                    params=params,
                    timeout=30.0
                )
                if response.status_code != 200:
                    return []

                data = response.json().get("numbers", [])
                return [
                    PhoneNumber(
                        number=num.get("msisdn", ""),
                        provider=self.provider_name,
                        capabilities=capabilities or ["voice", "sms"],
                        region=num.get("country", ""),
                        monthly_cost=float(num.get("cost", 0)),
                    )
                    for num in data
                ]
        except Exception as e:
            logger.error(f"Failed to search Vonage numbers: {e}")
            return []

    async def purchase_number(self, number: str) -> Optional[PhoneNumber]:
        """Purchase a Vonage phone number."""
        if not self.is_configured:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{VONAGE_REST_BASE}/number/buy",
                    data={
                        **self._get_auth_params(),
                        "country": "US",  # Required; caller should provide
                        "msisdn": number.replace("+", ""),
                    },
                    timeout=30.0
                )
                if response.status_code not in (200, 201):
                    return None

                logger.info(f"Purchased Vonage number {number}")

                return PhoneNumber(
                    number=number,
                    provider=self.provider_name,
                    capabilities=["voice", "sms"],
                )
        except Exception as e:
            logger.error(f"Failed to purchase Vonage number {number}: {e}")
            return None

    async def release_number(self, number: str) -> bool:
        """Release a Vonage phone number."""
        if not self.is_configured:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{VONAGE_REST_BASE}/number/cancel",
                    data={
                        **self._get_auth_params(),
                        "country": "US",
                        "msisdn": number.replace("+", ""),
                    },
                    timeout=30.0
                )
                success = response.status_code in (200, 204)
                if success:
                    logger.info(f"Released Vonage number {number}")
                return success
        except Exception as e:
            logger.error(f"Failed to release Vonage number {number}: {e}")
            return False

    # =========================================================================
    # Webhook Methods
    # =========================================================================

    def parse_webhook_call(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Vonage call webhook data."""
        return {
            "call_id": data.get("uuid", ""),
            "from_number": data.get("from", ""),
            "to_number": data.get("to", ""),
            "direction": CallDirection.INBOUND if data.get("direction") == "inbound" else CallDirection.OUTBOUND,
            "status": self._map_call_status(data.get("status", "")),
            "duration": int(data.get("duration", 0)) if data.get("duration") else None,
            "metadata": {
                "conversation_uuid": data.get("conversation_uuid", ""),
                "timestamp": data.get("timestamp", ""),
            }
        }

    def parse_webhook_sms(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Vonage SMS webhook data."""
        return {
            "message_id": data.get("messageId", ""),
            "from_number": data.get("msisdn", ""),
            "to_number": data.get("to", ""),
            "body": data.get("text", ""),
            "status": self._map_sms_status(data.get("status", "")),
            "metadata": {
                "network_code": data.get("network-code", ""),
                "message_timestamp": data.get("message-timestamp", ""),
            }
        }

    def validate_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        url: Optional[str] = None,
    ) -> bool:
        """Validate Vonage webhook signature."""
        if not self.config.api_secret:
            return False

        try:
            # Vonage uses SHA256 HMAC
            expected = hmac.new(
                self.config.api_secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(signature, expected)
        except Exception as e:
            logger.error(f"Vonage signature validation error: {e}")
            return False
