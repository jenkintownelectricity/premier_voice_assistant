"""
VoIP.ms Telephony Provider

Implements TelephonyProvider interface for VoIP.ms.
Supports voice calls via SIP and SMS messaging.

VoIP.ms uses a REST API with query parameters for authentication.
Note: VoIP.ms is primarily a SIP provider without advanced call control.
"""

import hmac
import hashlib
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode

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

VOIPMS_API_BASE = "https://voip.ms/api/v1/rest.php"


class VoIPMSProvider(TelephonyProvider):
    """VoIP.ms telephony provider implementation."""

    @property
    def provider_name(self) -> str:
        return "voipms"

    @property
    def is_configured(self) -> bool:
        return bool(
            self.config.extra.get("api_username")
            and self.config.api_key  # API password
        )

    def _get_base_params(self) -> Dict[str, str]:
        """Get base query params for VoIP.ms API."""
        return {
            "api_username": self.config.extra.get("api_username", ""),
            "api_password": self.config.api_key or "",
        }

    async def _make_request(self, method: str, **params) -> Optional[Dict[str, Any]]:
        """Make a request to VoIP.ms API."""
        try:
            all_params = {
                **self._get_base_params(),
                "method": method,
                **params
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    VOIPMS_API_BASE,
                    params=all_params,
                    timeout=30.0
                )

                if response.status_code != 200:
                    return None

                data = response.json()
                if data.get("status") != "success":
                    logger.error(f"VoIP.ms API error: {data.get('status')}")
                    return None

                return data
        except Exception as e:
            logger.error(f"VoIP.ms API request failed: {e}")
            return None

    async def validate_credentials(self) -> bool:
        """Validate VoIP.ms credentials by fetching account balance."""
        if not self.is_configured:
            return False

        result = await self._make_request("getBalance")
        return result is not None

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
        """
        Initiate an outbound call via VoIP.ms.

        Note: VoIP.ms doesn't have a direct call initiation API like Twilio.
        Calls are made through SIP endpoints. This implementation uses
        the callback feature to connect calls.
        """
        if not self.is_configured:
            return CallResult(
                success=False,
                error="VoIP.ms not configured",
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

            # VoIP.ms uses callback service for outbound calls
            # This requires setting up a callback DID in the portal
            callback_did = self.config.extra.get("callback_did", from_num)

            result = await self._make_request(
                "sendCallback",
                did=callback_did.replace("+1", "").replace("+", ""),
                number=to_number.replace("+1", "").replace("+", ""),
            )

            if not result:
                return CallResult(
                    success=False,
                    error="Failed to initiate callback",
                    status=CallStatus.FAILED
                )

            logger.info(f"Initiated VoIP.ms callback to {to_number}")

            return CallResult(
                success=True,
                call_id=f"voipms-{room_name}",
                provider_call_id=result.get("callback_id", ""),
                room_name=room_name,
                status=CallStatus.INITIATING,
                metadata={
                    "from_number": from_num,
                    "to_number": to_number,
                    "callback_type": "callback",
                    **(metadata or {})
                }
            )

        except Exception as e:
            logger.error(f"Failed to initiate VoIP.ms call: {e}")
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
        """
        Generate call response for VoIP.ms.

        VoIP.ms doesn't use TwiML/NCCO style responses.
        Instead, routing is configured in the portal via IVR or direct SIP.

        This returns a minimal XML for compatibility.
        """
        sip_host = sip_uri or self.config.sip_uri

        if sip_host:
            # Return SIP URI info for manual configuration
            full_sip_uri = f"sip:{room_name}@{sip_host}"
            logger.info(f"VoIP.ms: Route call to {full_sip_uri} via portal configuration")
            # VoIP.ms uses portal-based routing; return info as comment
            return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- VoIP.ms: Configure routing in portal to forward to {full_sip_uri} -->
<Response>
    <Redirect>{full_sip_uri}</Redirect>
</Response>"""
        else:
            return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Hangup/>
</Response>"""

    async def end_call(self, call_id: str) -> bool:
        """
        End an active VoIP.ms call.

        VoIP.ms doesn't provide direct call control API.
        Calls are managed at the SIP level.
        """
        logger.warning("VoIP.ms doesn't support programmatic call termination")
        return False

    async def get_call_status(self, call_id: str) -> Optional[CallStatus]:
        """
        Get the current status of a VoIP.ms call.

        VoIP.ms doesn't provide real-time call status API.
        """
        logger.warning("VoIP.ms doesn't support real-time call status")
        return None

    def _map_call_status(self, status: str) -> CallStatus:
        """Map VoIP.ms call status to standard CallStatus."""
        # VoIP.ms CDR statuses
        status_map = {
            "ANSWERED": CallStatus.COMPLETED,
            "NO ANSWER": CallStatus.NO_ANSWER,
            "BUSY": CallStatus.BUSY,
            "FAILED": CallStatus.FAILED,
            "CONGESTION": CallStatus.FAILED,
        }
        return status_map.get(status.upper(), CallStatus.INITIATING)

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
        """Send an SMS via VoIP.ms."""
        if not self.is_configured:
            return SMSResult(
                success=False,
                error="VoIP.ms not configured",
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

            # VoIP.ms SMS requires the DID (without country code for US/CA)
            did = from_num.replace("+1", "").replace("+", "")
            dst = to_number.replace("+1", "").replace("+", "")

            result = await self._make_request(
                "sendSMS",
                did=did,
                dst=dst,
                message=message,
            )

            if not result:
                return SMSResult(
                    success=False,
                    error="Failed to send SMS",
                    status=SMSStatus.FAILED
                )

            sms_id = result.get("sms", "")

            logger.info(f"Sent VoIP.ms SMS {sms_id} to {to_number}")

            return SMSResult(
                success=True,
                message_id=sms_id,
                provider_message_id=sms_id,
                status=SMSStatus.SENT,
                metadata={
                    "from_number": from_num,
                    "to_number": to_number,
                    **(metadata or {})
                }
            )

        except Exception as e:
            logger.error(f"Failed to send VoIP.ms SMS: {e}")
            return SMSResult(
                success=False,
                error=str(e),
                status=SMSStatus.FAILED
            )

    async def get_sms_status(self, message_id: str) -> Optional[SMSStatus]:
        """Get the current status of a VoIP.ms SMS."""
        if not self.is_configured:
            return None

        # VoIP.ms doesn't provide individual message status lookup
        # Would need to query SMS history and filter
        logger.warning("VoIP.ms SMS status check requires querying history")
        return None

    def _map_sms_status(self, status: str) -> SMSStatus:
        """Map VoIP.ms SMS status to standard SMSStatus."""
        status_map = {
            "sent": SMSStatus.SENT,
            "delivered": SMSStatus.DELIVERED,
            "failed": SMSStatus.FAILED,
        }
        return status_map.get(status.lower(), SMSStatus.QUEUED)

    # =========================================================================
    # Phone Number Methods
    # =========================================================================

    async def list_phone_numbers(self) -> List[PhoneNumber]:
        """List all VoIP.ms DIDs on the account."""
        if not self.is_configured:
            return []

        result = await self._make_request("getDIDsInfo", client="all")
        if not result:
            return []

        try:
            dids = result.get("dids", [])
            return [
                PhoneNumber(
                    number=f"+1{did.get('did', '')}",
                    provider=self.provider_name,
                    capabilities=self._get_capabilities(did),
                    friendly_name=did.get("description", ""),
                    region=did.get("state", ""),
                    monthly_cost=float(did.get("monthly", 0)),
                    metadata={
                        "did": did.get("did", ""),
                        "routing": did.get("routing", ""),
                        "sms_enabled": did.get("sms_available", "no"),
                    }
                )
                for did in dids
            ]
        except Exception as e:
            logger.error(f"Failed to parse VoIP.ms DIDs: {e}")
            return []

    def _get_capabilities(self, did: Dict[str, Any]) -> List[str]:
        """Extract capabilities from VoIP.ms DID."""
        caps = ["voice"]  # All DIDs support voice
        if did.get("sms_available") == "yes" or did.get("sms_enabled") == "1":
            caps.append("sms")
        return caps

    async def search_available_numbers(
        self,
        country: str = "US",
        area_code: Optional[str] = None,
        contains: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[PhoneNumber]:
        """Search for available VoIP.ms DIDs."""
        if not self.is_configured:
            return []

        # VoIP.ms requires state/province for DID search
        params = {}
        if area_code:
            params["npa"] = area_code

        # Search by state if area code provided (would need mapping)
        params["state"] = self.config.extra.get("search_state", "PA")
        params["type"] = "local"

        result = await self._make_request("getDIDsUSA", **params)
        if not result:
            return []

        try:
            dids = result.get("dids", [])[:limit]
            return [
                PhoneNumber(
                    number=f"+1{did.get('did', '')}",
                    provider=self.provider_name,
                    capabilities=capabilities or ["voice"],
                    region=did.get("ratecenter", ""),
                    monthly_cost=float(did.get("monthly", 0)),
                )
                for did in dids
            ]
        except Exception as e:
            logger.error(f"Failed to search VoIP.ms DIDs: {e}")
            return []

    async def purchase_number(self, number: str) -> Optional[PhoneNumber]:
        """Purchase a VoIP.ms DID."""
        if not self.is_configured:
            return None

        try:
            # Clean the number
            did = number.replace("+1", "").replace("+", "")

            result = await self._make_request(
                "orderDID",
                did=did,
                routing="account:" + self.config.extra.get("account", ""),
            )

            if not result:
                return None

            logger.info(f"Purchased VoIP.ms DID {number}")

            return PhoneNumber(
                number=f"+1{did}",
                provider=self.provider_name,
                capabilities=["voice"],
            )
        except Exception as e:
            logger.error(f"Failed to purchase VoIP.ms DID {number}: {e}")
            return None

    async def release_number(self, number: str) -> bool:
        """Release a VoIP.ms DID."""
        if not self.is_configured:
            return False

        try:
            did = number.replace("+1", "").replace("+", "")

            result = await self._make_request("cancelDID", did=did)

            if result:
                logger.info(f"Released VoIP.ms DID {number}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to release VoIP.ms DID {number}: {e}")
            return False

    # =========================================================================
    # Webhook Methods
    # =========================================================================

    def parse_webhook_call(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse VoIP.ms call webhook data."""
        # VoIP.ms sends CDR data via email or API polling
        # Webhook format depends on configuration
        return {
            "call_id": data.get("uniqueid", ""),
            "from_number": data.get("callerid", ""),
            "to_number": data.get("destination", ""),
            "direction": CallDirection.INBOUND,
            "status": self._map_call_status(data.get("disposition", "")),
            "duration": int(data.get("seconds", 0)) if data.get("seconds") else None,
            "metadata": {
                "date": data.get("date", ""),
                "account": data.get("account", ""),
            }
        }

    def parse_webhook_sms(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse VoIP.ms SMS webhook data."""
        return {
            "message_id": data.get("id", ""),
            "from_number": data.get("from", ""),
            "to_number": data.get("to", ""),
            "body": data.get("message", ""),
            "status": self._map_sms_status(data.get("type", "")),
            "metadata": {
                "date": data.get("date", ""),
            }
        }

    def validate_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        url: Optional[str] = None,
    ) -> bool:
        """
        Validate VoIP.ms webhook signature.

        VoIP.ms uses IP whitelist rather than signature validation.
        """
        # VoIP.ms relies on IP whitelisting for webhook security
        # Signature validation not supported
        logger.warning("VoIP.ms uses IP whitelisting, not signature validation")
        return True  # Caller should verify IP instead
