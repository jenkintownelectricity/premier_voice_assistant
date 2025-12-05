"""
HIVE215 Multi-Provider Telephony Module

Supports multiple telephony providers for voice calls and SMS:
- Twilio (default)
- Telnyx
- Plivo
- Vonage
- SignalWire
- VoIP.ms

Each provider implements a common interface for:
- Inbound/outbound voice calls via SIP
- SMS sending and receiving
- Phone number management
- Webhooks for call/SMS events
"""

from backend.telephony.provider import TelephonyProvider, ProviderConfig, CallStatus, SMSStatus
from backend.telephony.factory import get_provider, list_providers, ProviderFactory

__all__ = [
    "TelephonyProvider",
    "ProviderConfig",
    "CallStatus",
    "SMSStatus",
    "get_provider",
    "list_providers",
    "ProviderFactory",
]
