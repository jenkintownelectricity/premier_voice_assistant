"""
Base Telephony Provider Interface

All telephony providers must implement this interface for:
- Voice calls (inbound/outbound)
- SMS messaging
- Phone number management
- LiveKit SIP integration
"""

import os
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, AsyncIterator

logger = logging.getLogger(__name__)


class CallDirection(str, Enum):
    """Direction of a phone call."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, Enum):
    """Status of a phone call."""
    INITIATING = "initiating"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BUSY = "busy"
    NO_ANSWER = "no_answer"
    CANCELLED = "cancelled"


class SMSStatus(str, Enum):
    """Status of an SMS message."""
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    UNDELIVERED = "undelivered"


@dataclass
class ProviderConfig:
    """Configuration for a telephony provider."""
    name: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    account_sid: Optional[str] = None
    auth_token: Optional[str] = None
    api_url: Optional[str] = None
    phone_number: Optional[str] = None
    sip_uri: Optional[str] = None
    sip_username: Optional[str] = None
    sip_password: Optional[str] = None
    webhook_base_url: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls, provider_name: str) -> "ProviderConfig":
        """Load provider config from environment variables."""
        prefix = provider_name.upper().replace("-", "_").replace(".", "_")

        return cls(
            name=provider_name,
            api_key=os.getenv(f"{prefix}_API_KEY"),
            api_secret=os.getenv(f"{prefix}_API_SECRET"),
            account_sid=os.getenv(f"{prefix}_ACCOUNT_SID"),
            auth_token=os.getenv(f"{prefix}_AUTH_TOKEN"),
            api_url=os.getenv(f"{prefix}_API_URL"),
            phone_number=os.getenv(f"{prefix}_PHONE_NUMBER"),
            sip_uri=os.getenv(f"{prefix}_SIP_URI"),
            sip_username=os.getenv(f"{prefix}_SIP_USERNAME"),
            sip_password=os.getenv(f"{prefix}_SIP_PASSWORD"),
            webhook_base_url=os.getenv("API_BASE_URL", os.getenv("API_URL", "")),
        )


@dataclass
class CallResult:
    """Result of initiating a call."""
    success: bool
    call_id: Optional[str] = None
    provider_call_id: Optional[str] = None
    room_name: Optional[str] = None
    status: CallStatus = CallStatus.INITIATING
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SMSResult:
    """Result of sending an SMS."""
    success: bool
    message_id: Optional[str] = None
    provider_message_id: Optional[str] = None
    status: SMSStatus = SMSStatus.QUEUED
    error: Optional[str] = None
    segments: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PhoneNumber:
    """Represents a phone number from a provider."""
    number: str
    provider: str
    capabilities: List[str] = field(default_factory=list)  # ['voice', 'sms', 'mms']
    friendly_name: Optional[str] = None
    region: Optional[str] = None
    monthly_cost: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TelephonyProvider(ABC):
    """
    Abstract base class for telephony providers.

    All providers must implement these methods to support:
    - Voice calls with LiveKit SIP integration
    - SMS messaging
    - Phone number management
    """

    def __init__(self, config: ProviderConfig):
        self.config = config
        self._client = None
        logger.info(f"Initializing {self.provider_name} telephony provider")

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'twilio', 'telnyx')."""
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the provider is properly configured."""
        pass

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """Validate that credentials are correct by making a test API call."""
        pass

    # =========================================================================
    # Voice Call Methods
    # =========================================================================

    @abstractmethod
    async def initiate_call(
        self,
        to_number: str,
        from_number: Optional[str] = None,
        room_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CallResult:
        """
        Initiate an outbound call.

        Args:
            to_number: The phone number to call
            from_number: The caller ID (defaults to provider's number)
            room_name: LiveKit room to connect the call to
            metadata: Additional metadata to attach to the call

        Returns:
            CallResult with call details
        """
        pass

    @abstractmethod
    def generate_call_response(
        self,
        room_name: str,
        caller_number: str,
        called_number: str,
        sip_uri: Optional[str] = None,
    ) -> str:
        """
        Generate provider-specific response for incoming calls.

        For Twilio: TwiML
        For Telnyx: TeXML
        For Vonage: NCCO (JSON)

        Args:
            room_name: LiveKit room to connect the call to
            caller_number: The calling party's number
            called_number: The called number
            sip_uri: Override SIP URI for LiveKit connection

        Returns:
            Provider-specific response string (XML or JSON)
        """
        pass

    @abstractmethod
    async def end_call(self, call_id: str) -> bool:
        """
        End an active call.

        Args:
            call_id: The provider's call ID

        Returns:
            True if call was ended successfully
        """
        pass

    @abstractmethod
    async def get_call_status(self, call_id: str) -> Optional[CallStatus]:
        """
        Get the current status of a call.

        Args:
            call_id: The provider's call ID

        Returns:
            Current CallStatus or None if not found
        """
        pass

    # =========================================================================
    # SMS Methods
    # =========================================================================

    @abstractmethod
    async def send_sms(
        self,
        to_number: str,
        message: str,
        from_number: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SMSResult:
        """
        Send an SMS message.

        Args:
            to_number: Recipient phone number
            message: Message content
            from_number: Sender number (defaults to provider's number)
            metadata: Additional metadata

        Returns:
            SMSResult with message details
        """
        pass

    @abstractmethod
    async def get_sms_status(self, message_id: str) -> Optional[SMSStatus]:
        """
        Get the current status of an SMS message.

        Args:
            message_id: The provider's message ID

        Returns:
            Current SMSStatus or None if not found
        """
        pass

    # =========================================================================
    # Phone Number Methods
    # =========================================================================

    @abstractmethod
    async def list_phone_numbers(self) -> List[PhoneNumber]:
        """
        List all phone numbers associated with the account.

        Returns:
            List of PhoneNumber objects
        """
        pass

    @abstractmethod
    async def search_available_numbers(
        self,
        country: str = "US",
        area_code: Optional[str] = None,
        contains: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[PhoneNumber]:
        """
        Search for available phone numbers to purchase.

        Args:
            country: ISO country code
            area_code: Filter by area code
            contains: Filter by number pattern
            capabilities: Required capabilities (voice, sms, mms)
            limit: Maximum results to return

        Returns:
            List of available PhoneNumber objects
        """
        pass

    @abstractmethod
    async def purchase_number(self, number: str) -> Optional[PhoneNumber]:
        """
        Purchase a phone number.

        Args:
            number: The phone number to purchase

        Returns:
            PhoneNumber object if successful, None otherwise
        """
        pass

    @abstractmethod
    async def release_number(self, number: str) -> bool:
        """
        Release/delete a phone number.

        Args:
            number: The phone number to release

        Returns:
            True if released successfully
        """
        pass

    # =========================================================================
    # Webhook Methods
    # =========================================================================

    @abstractmethod
    def parse_webhook_call(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse incoming call webhook data into a standard format.

        Args:
            data: Raw webhook data from provider

        Returns:
            Standardized call event data:
            {
                'call_id': str,
                'from_number': str,
                'to_number': str,
                'direction': CallDirection,
                'status': CallStatus,
                'duration': Optional[int],
                'metadata': Dict[str, Any]
            }
        """
        pass

    @abstractmethod
    def parse_webhook_sms(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse incoming SMS webhook data into a standard format.

        Args:
            data: Raw webhook data from provider

        Returns:
            Standardized SMS event data:
            {
                'message_id': str,
                'from_number': str,
                'to_number': str,
                'body': str,
                'status': SMSStatus,
                'metadata': Dict[str, Any]
            }
        """
        pass

    @abstractmethod
    def validate_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        url: Optional[str] = None,
    ) -> bool:
        """
        Validate that a webhook request came from the provider.

        Args:
            payload: Raw request body
            signature: Signature header value
            url: Request URL (required by some providers)

        Returns:
            True if signature is valid
        """
        pass

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_sip_uri(self, room_name: str) -> str:
        """
        Get the SIP URI for connecting a call to a LiveKit room.

        Args:
            room_name: LiveKit room name

        Returns:
            SIP URI string
        """
        sip_host = self.config.sip_uri or os.getenv("LIVEKIT_SIP_URI", "")
        if not sip_host:
            raise ValueError("SIP URI not configured")
        return f"sip:{room_name}@{sip_host}"

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the provider.

        Returns:
            Health status dict with 'healthy', 'message', and 'details' keys
        """
        try:
            if not self.is_configured:
                return {
                    "healthy": False,
                    "message": f"{self.provider_name} is not configured",
                    "details": {"configured": False}
                }

            valid = await self.validate_credentials()
            return {
                "healthy": valid,
                "message": "Provider is operational" if valid else "Invalid credentials",
                "details": {
                    "configured": True,
                    "credentials_valid": valid,
                    "phone_number": self.config.phone_number,
                    "sip_configured": bool(self.config.sip_uri),
                }
            }
        except Exception as e:
            logger.error(f"Health check failed for {self.provider_name}: {e}")
            return {
                "healthy": False,
                "message": str(e),
                "details": {"error": str(e)}
            }

    async def close(self):
        """Clean up any resources."""
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(configured={self.is_configured})>"
