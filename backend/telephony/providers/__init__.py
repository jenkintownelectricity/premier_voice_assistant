"""
Telephony Provider Implementations

Each provider module implements the TelephonyProvider interface.
"""

from backend.telephony.providers.twilio_provider import TwilioProvider
from backend.telephony.providers.telnyx_provider import TelnyxProvider
from backend.telephony.providers.plivo_provider import PlivoProvider
from backend.telephony.providers.vonage_provider import VonageProvider
from backend.telephony.providers.signalwire_provider import SignalWireProvider
from backend.telephony.providers.voipms_provider import VoIPMSProvider

__all__ = [
    "TwilioProvider",
    "TelnyxProvider",
    "PlivoProvider",
    "VonageProvider",
    "SignalWireProvider",
    "VoIPMSProvider",
]

# Provider registry for factory
PROVIDER_REGISTRY = {
    "twilio": TwilioProvider,
    "telnyx": TelnyxProvider,
    "plivo": PlivoProvider,
    "vonage": VonageProvider,
    "signalwire": SignalWireProvider,
    "voipms": VoIPMSProvider,
}
