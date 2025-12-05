"""
Telephony Provider Factory

Creates and manages telephony provider instances.
Supports dynamic provider selection based on configuration.
"""

import os
import logging
from typing import Dict, Optional, List, Type, Any

from backend.telephony.provider import TelephonyProvider, ProviderConfig

logger = logging.getLogger(__name__)

# Provider class registry
_PROVIDER_CLASSES: Dict[str, Type[TelephonyProvider]] = {}

# Provider instance cache
_PROVIDER_INSTANCES: Dict[str, TelephonyProvider] = {}


def _load_provider_classes():
    """Lazy load provider classes to avoid circular imports."""
    global _PROVIDER_CLASSES

    if _PROVIDER_CLASSES:
        return

    try:
        from backend.telephony.providers.twilio_provider import TwilioProvider
        _PROVIDER_CLASSES["twilio"] = TwilioProvider
    except ImportError as e:
        logger.debug(f"Twilio provider not available: {e}")

    try:
        from backend.telephony.providers.telnyx_provider import TelnyxProvider
        _PROVIDER_CLASSES["telnyx"] = TelnyxProvider
    except ImportError as e:
        logger.debug(f"Telnyx provider not available: {e}")

    try:
        from backend.telephony.providers.plivo_provider import PlivoProvider
        _PROVIDER_CLASSES["plivo"] = PlivoProvider
    except ImportError as e:
        logger.debug(f"Plivo provider not available: {e}")

    try:
        from backend.telephony.providers.vonage_provider import VonageProvider
        _PROVIDER_CLASSES["vonage"] = VonageProvider
    except ImportError as e:
        logger.debug(f"Vonage provider not available: {e}")

    try:
        from backend.telephony.providers.signalwire_provider import SignalWireProvider
        _PROVIDER_CLASSES["signalwire"] = SignalWireProvider
    except ImportError as e:
        logger.debug(f"SignalWire provider not available: {e}")

    try:
        from backend.telephony.providers.voipms_provider import VoIPMSProvider
        _PROVIDER_CLASSES["voipms"] = VoIPMSProvider
    except ImportError as e:
        logger.debug(f"VoIP.ms provider not available: {e}")


def list_providers() -> List[str]:
    """
    List all available provider names.

    Returns:
        List of provider name strings
    """
    _load_provider_classes()
    return list(_PROVIDER_CLASSES.keys())


def get_provider_class(name: str) -> Optional[Type[TelephonyProvider]]:
    """
    Get a provider class by name.

    Args:
        name: Provider name (e.g., 'twilio', 'telnyx')

    Returns:
        Provider class or None if not found
    """
    _load_provider_classes()
    return _PROVIDER_CLASSES.get(name.lower())


def get_provider(
    name: str,
    config: Optional[ProviderConfig] = None,
    use_cache: bool = True,
) -> Optional[TelephonyProvider]:
    """
    Get a provider instance by name.

    Args:
        name: Provider name (e.g., 'twilio', 'telnyx')
        config: Optional provider configuration (loads from env if not provided)
        use_cache: Whether to cache and reuse provider instances

    Returns:
        Provider instance or None if not available
    """
    name = name.lower()

    # Check cache first
    if use_cache and name in _PROVIDER_INSTANCES:
        return _PROVIDER_INSTANCES[name]

    # Get provider class
    provider_class = get_provider_class(name)
    if not provider_class:
        logger.error(f"Unknown provider: {name}")
        return None

    # Load config from environment if not provided
    if config is None:
        config = ProviderConfig.from_env(name)

    # Create provider instance
    try:
        provider = provider_class(config)

        # Cache if requested
        if use_cache:
            _PROVIDER_INSTANCES[name] = provider

        return provider

    except Exception as e:
        logger.error(f"Failed to create provider {name}: {e}")
        return None


def get_default_provider() -> Optional[TelephonyProvider]:
    """
    Get the default/primary telephony provider.

    Checks TELEPHONY_PROVIDER env var, then falls back to first configured provider.

    Returns:
        Default provider instance or None
    """
    # Check for explicit default
    default_name = os.getenv("TELEPHONY_PROVIDER", "").lower()
    if default_name:
        provider = get_provider(default_name)
        if provider and provider.is_configured:
            return provider
        logger.warning(f"Default provider {default_name} is not configured")

    # Try providers in order of preference
    for name in ["twilio", "telnyx", "plivo", "signalwire", "vonage", "voipms"]:
        provider = get_provider(name)
        if provider and provider.is_configured:
            logger.info(f"Using {name} as default telephony provider")
            return provider

    logger.warning("No telephony provider configured")
    return None


def clear_cache():
    """Clear the provider instance cache."""
    global _PROVIDER_INSTANCES
    _PROVIDER_INSTANCES = {}


class ProviderFactory:
    """
    Factory for managing multiple telephony providers.

    Supports:
    - Multiple simultaneous providers
    - Provider switching
    - Health monitoring
    - Cost optimization routing
    """

    def __init__(self):
        self._providers: Dict[str, TelephonyProvider] = {}
        self._default_provider: Optional[str] = None

    def register(
        self,
        name: str,
        config: Optional[ProviderConfig] = None,
        set_default: bool = False,
    ) -> bool:
        """
        Register a provider with the factory.

        Args:
            name: Provider name
            config: Optional configuration
            set_default: Whether to set as default provider

        Returns:
            True if registered successfully
        """
        provider = get_provider(name, config, use_cache=False)
        if not provider:
            return False

        self._providers[name.lower()] = provider

        if set_default or self._default_provider is None:
            self._default_provider = name.lower()

        logger.info(f"Registered telephony provider: {name}")
        return True

    def get(self, name: Optional[str] = None) -> Optional[TelephonyProvider]:
        """
        Get a registered provider.

        Args:
            name: Provider name (uses default if not specified)

        Returns:
            Provider instance or None
        """
        if name is None:
            name = self._default_provider

        if name is None:
            return None

        return self._providers.get(name.lower())

    def set_default(self, name: str) -> bool:
        """
        Set the default provider.

        Args:
            name: Provider name

        Returns:
            True if set successfully
        """
        name = name.lower()
        if name not in self._providers:
            logger.error(f"Provider {name} not registered")
            return False

        self._default_provider = name
        return True

    def list_registered(self) -> List[str]:
        """List all registered provider names."""
        return list(self._providers.keys())

    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Run health checks on all registered providers.

        Returns:
            Dict mapping provider names to health status
        """
        results = {}
        for name, provider in self._providers.items():
            results[name] = await provider.health_check()
        return results

    def get_configured_providers(self) -> List[TelephonyProvider]:
        """
        Get all registered providers that are properly configured.

        Returns:
            List of configured provider instances
        """
        return [p for p in self._providers.values() if p.is_configured]

    async def close_all(self):
        """Close all registered providers."""
        for provider in self._providers.values():
            await provider.close()
        self._providers.clear()
        self._default_provider = None


# Global factory instance
_factory: Optional[ProviderFactory] = None


def get_factory() -> ProviderFactory:
    """Get the global provider factory instance."""
    global _factory
    if _factory is None:
        _factory = ProviderFactory()
    return _factory


def init_providers_from_env() -> ProviderFactory:
    """
    Initialize all configured providers from environment variables.

    Checks for provider-specific env vars and registers configured providers.

    Returns:
        Configured ProviderFactory instance
    """
    factory = get_factory()

    # Check each provider and register if configured
    provider_checks = [
        ("twilio", ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"]),
        ("telnyx", ["TELNYX_API_KEY"]),
        ("plivo", ["PLIVO_ACCOUNT_SID", "PLIVO_AUTH_TOKEN"]),
        ("vonage", ["VONAGE_API_KEY", "VONAGE_API_SECRET"]),
        ("signalwire", ["SIGNALWIRE_ACCOUNT_SID", "SIGNALWIRE_AUTH_TOKEN", "SIGNALWIRE_SPACE_URL"]),
        ("voipms", ["VOIPMS_API_USERNAME", "VOIPMS_API_KEY"]),
    ]

    default_provider = os.getenv("TELEPHONY_PROVIDER", "").lower()
    first_configured = None

    for name, required_vars in provider_checks:
        # Check if all required env vars are set
        if all(os.getenv(var) for var in required_vars):
            # Build config with extra vars for providers that need them
            config = ProviderConfig.from_env(name)

            # Add provider-specific extras
            if name == "signalwire":
                config.extra["space_url"] = os.getenv("SIGNALWIRE_SPACE_URL", "")
            elif name == "voipms":
                config.extra["api_username"] = os.getenv("VOIPMS_API_USERNAME", "")
                config.extra["account"] = os.getenv("VOIPMS_ACCOUNT", "")

            is_default = (name == default_provider) or (first_configured is None and not default_provider)
            if factory.register(name, config, set_default=is_default):
                if first_configured is None:
                    first_configured = name

    if not factory.list_registered():
        logger.warning("No telephony providers configured. Set provider env vars to enable.")

    return factory
