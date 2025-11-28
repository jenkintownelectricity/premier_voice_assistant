"""
Automatic Model Version Manager for Premier Voice Assistant.

Handles:
- Dynamic model discovery via Anthropic Models API
- Fallback chains for automatic recovery from deprecation
- Admin override via environment variables
- Automatic retry on 404/deprecation errors

Architecture:
┌─────────────────────────────────────────────────┐
│  Layer 1: Model Aliases + Dynamic Discovery     │
├─────────────────────────────────────────────────┤
│  Layer 2: Fallback Chain                        │
├─────────────────────────────────────────────────┤
│  Layer 3: Admin Override                        │
└─────────────────────────────────────────────────┘
"""

import os
import logging
from typing import Optional, List, Dict, Any, Tuple
from functools import lru_cache
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)


# ============================================================================
# MODEL REGISTRY - Define all models with fallback chains
# ============================================================================

MODEL_REGISTRY = {
    # Sonnet family - for balanced performance/cost
    "sonnet": {
        "display_name": "Claude Sonnet",
        "fallback_chain": [
            "claude-sonnet-4-5-20250929",     # Latest Sonnet 4.5
            "claude-sonnet-4-20250514",       # Sonnet 4
            "claude-3-5-sonnet-20241022",     # Sonnet 3.5 (legacy)
            "claude-3-sonnet-20240229",       # Sonnet 3 (legacy)
        ],
        "alias": "claude-sonnet-4-5",
        "use_case": "general",
        "cost_tier": "medium",
    },

    # Haiku family - for speed and cost
    "haiku": {
        "display_name": "Claude Haiku",
        "fallback_chain": [
            "claude-haiku-4-5-20241022",      # Latest Haiku 4.5
            "claude-3-haiku-20240307",        # Haiku 3 (legacy)
        ],
        "alias": "claude-haiku-4-5",
        "use_case": "fast",
        "cost_tier": "low",
    },

    # Opus family - for maximum capability
    "opus": {
        "display_name": "Claude Opus",
        "fallback_chain": [
            "claude-opus-4-5-20251101",       # Latest Opus 4.5
            "claude-opus-4-1-20250805",       # Opus 4.1
            "claude-opus-4-20250514",         # Opus 4
        ],
        "alias": "claude-opus-4-5",
        "use_case": "complex",
        "cost_tier": "high",
    },
}

# Emergency cross-family fallback (if entire family is down)
EMERGENCY_FALLBACK = "claude-haiku-4-5-20241022"


# ============================================================================
# MODEL MANAGER CLASS
# ============================================================================

class ModelManager:
    """
    Manages model selection with automatic fallbacks and discovery.

    Usage:
        manager = ModelManager()
        model_id = manager.get_model("sonnet")  # Returns best available model

        # Or with automatic retry on failure:
        model_id = manager.get_model_with_retry("sonnet", exclude=["claude-sonnet-4-5-20250929"])
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern for global model manager."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._available_models: Optional[List[str]] = None
        self._models_cache_time: Optional[datetime] = None
        self._failed_models: Dict[str, datetime] = {}  # Track failed models with timestamp
        self._cache_ttl = timedelta(hours=1)
        self._failure_cooldown = timedelta(minutes=5)

        # Admin overrides
        self._admin_overrides: Dict[str, str] = {}
        self._load_admin_overrides()

        logger.info("ModelManager initialized")

    def _load_admin_overrides(self):
        """Load admin model overrides from environment variables."""
        # Format: CLAUDE_MODEL_OVERRIDE_SONNET=claude-specific-version
        for family in MODEL_REGISTRY.keys():
            env_key = f"CLAUDE_MODEL_OVERRIDE_{family.upper()}"
            override = os.getenv(env_key)
            if override:
                self._admin_overrides[family] = override
                logger.info(f"Admin override for {family}: {override}")

        # Global override
        global_override = os.getenv("CLAUDE_MODEL")
        if global_override:
            # Apply to default family (sonnet)
            if "sonnet" not in self._admin_overrides:
                self._admin_overrides["sonnet"] = global_override
                logger.info(f"Global model override: {global_override}")

    def discover_available_models(self, force_refresh: bool = False) -> List[str]:
        """
        Query Anthropic Models API to discover available models.
        Results are cached for 1 hour.
        """
        # Check cache
        if (not force_refresh and
            self._available_models is not None and
            self._models_cache_time is not None and
            datetime.now() - self._models_cache_time < self._cache_ttl):
            return self._available_models

        try:
            import anthropic
            client = anthropic.Anthropic()

            # List all available models
            response = client.models.list(limit=100)

            self._available_models = [model.id for model in response.data]
            self._models_cache_time = datetime.now()

            logger.info(f"Discovered {len(self._available_models)} available models")
            logger.debug(f"Available models: {self._available_models[:10]}...")

            return self._available_models

        except Exception as e:
            logger.warning(f"Failed to discover models via API: {e}")
            # Return empty list, will use fallback chain without validation
            return []

    def is_model_available(self, model_id: str) -> bool:
        """Check if a specific model is available."""
        # Check if model recently failed
        if model_id in self._failed_models:
            failure_time = self._failed_models[model_id]
            if datetime.now() - failure_time < self._failure_cooldown:
                logger.debug(f"Model {model_id} in cooldown until {failure_time + self._failure_cooldown}")
                return False

        # If we have discovered models, validate against them
        available = self.discover_available_models()
        if available:
            return model_id in available

        # If discovery failed, assume available
        return True

    def mark_model_failed(self, model_id: str):
        """Mark a model as failed (will be in cooldown for 5 minutes)."""
        self._failed_models[model_id] = datetime.now()
        logger.warning(f"Marked model {model_id} as failed, cooldown for {self._failure_cooldown}")

    def get_model(
        self,
        family: str = "sonnet",
        prefer_alias: bool = False,
        exclude: Optional[List[str]] = None
    ) -> str:
        """
        Get the best available model from a family.

        Args:
            family: Model family ("sonnet", "haiku", "opus")
            prefer_alias: If True, return alias instead of specific version
            exclude: List of model IDs to skip (e.g., ones that already failed)

        Returns:
            Model ID string
        """
        exclude = exclude or []

        # Check for admin override first
        if family in self._admin_overrides:
            override = self._admin_overrides[family]
            if override not in exclude:
                logger.info(f"Using admin override for {family}: {override}")
                return override

        # Get family config
        config = MODEL_REGISTRY.get(family)
        if not config:
            logger.warning(f"Unknown model family: {family}, falling back to sonnet")
            config = MODEL_REGISTRY["sonnet"]

        # If alias preferred and available
        if prefer_alias:
            alias = config.get("alias")
            if alias and alias not in exclude:
                if self.is_model_available(alias):
                    return alias

        # Walk through fallback chain
        for model_id in config["fallback_chain"]:
            if model_id in exclude:
                continue
            if self.is_model_available(model_id):
                logger.info(f"Selected model: {model_id}")
                return model_id

        # Emergency fallback
        if EMERGENCY_FALLBACK not in exclude:
            logger.warning(f"Using emergency fallback: {EMERGENCY_FALLBACK}")
            return EMERGENCY_FALLBACK

        # Last resort: return first in chain regardless
        logger.error(f"All models exhausted, using first in chain")
        return config["fallback_chain"][0]

    def get_model_with_retry(
        self,
        family: str = "sonnet",
        failed_model: Optional[str] = None
    ) -> str:
        """
        Get a model, excluding any that have failed.
        Call this when a model returns 404/deprecation error.

        Args:
            family: Model family
            failed_model: Model that just failed (will be marked and excluded)

        Returns:
            Next model to try
        """
        exclude = []

        if failed_model:
            self.mark_model_failed(failed_model)
            exclude.append(failed_model)

        # Add all models currently in cooldown
        for model_id, failure_time in self._failed_models.items():
            if datetime.now() - failure_time < self._failure_cooldown:
                if model_id not in exclude:
                    exclude.append(model_id)

        return self.get_model(family, exclude=exclude)

    def validate_on_startup(self) -> Dict[str, Any]:
        """
        Validate model availability on application startup.
        Returns a report of available models.
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "families": {},
            "warnings": [],
            "errors": [],
        }

        # Discover available models
        available = self.discover_available_models(force_refresh=True)

        if not available:
            report["warnings"].append("Could not discover models via API - using fallback chain without validation")

        # Check each family
        for family, config in MODEL_REGISTRY.items():
            family_report = {
                "selected": None,
                "available": [],
                "deprecated": [],
            }

            for model_id in config["fallback_chain"]:
                if not available or model_id in available:
                    family_report["available"].append(model_id)
                    if not family_report["selected"]:
                        family_report["selected"] = model_id
                else:
                    family_report["deprecated"].append(model_id)

            if not family_report["selected"]:
                report["errors"].append(f"No available models for family: {family}")

            report["families"][family] = family_report

        # Log report
        logger.info(f"Model validation report: {report}")

        return report

    def get_all_families(self) -> List[str]:
        """Get list of all model families."""
        return list(MODEL_REGISTRY.keys())

    def get_family_info(self, family: str) -> Optional[Dict[str, Any]]:
        """Get info about a model family."""
        return MODEL_REGISTRY.get(family)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get or create the global ModelManager instance."""
    global _manager
    if _manager is None:
        _manager = ModelManager()
    return _manager


def get_model(family: str = "sonnet", **kwargs) -> str:
    """Convenience function to get a model."""
    return get_model_manager().get_model(family, **kwargs)


def get_model_with_fallback(family: str = "sonnet", failed_model: Optional[str] = None) -> str:
    """Convenience function to get a model with fallback."""
    return get_model_manager().get_model_with_retry(family, failed_model)


def validate_models_on_startup() -> Dict[str, Any]:
    """Validate models on application startup."""
    return get_model_manager().validate_on_startup()


# ============================================================================
# ANTHROPIC CLIENT WRAPPER WITH AUTO-RETRY
# ============================================================================

class ResilientAnthropicClient:
    """
    Wrapper around Anthropic client that automatically handles model deprecation.

    Usage:
        client = ResilientAnthropicClient()
        response = client.messages_create(
            family="sonnet",
            max_tokens=150,
            messages=[{"role": "user", "content": "Hello"}]
        )
    """

    def __init__(self, api_key: Optional[str] = None):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.manager = get_model_manager()

    def messages_create(
        self,
        family: str = "sonnet",
        model: Optional[str] = None,  # Override with specific model
        max_retries: int = 3,
        **kwargs
    ):
        """
        Create a message with automatic model fallback on deprecation errors.

        Args:
            family: Model family to use
            model: Specific model override (skips family selection)
            max_retries: Max number of fallback attempts
            **kwargs: Passed to anthropic.messages.create()

        Returns:
            Anthropic Message response
        """
        import anthropic

        # Get initial model
        current_model = model or self.manager.get_model(family)
        excluded_models = []

        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"Attempting API call with model: {current_model} (attempt {attempt + 1})")

                response = self.client.messages.create(
                    model=current_model,
                    **kwargs
                )

                return response

            except anthropic.NotFoundError as e:
                # Model deprecated or not found
                logger.warning(f"Model {current_model} not found (deprecated?): {e}")
                excluded_models.append(current_model)
                self.manager.mark_model_failed(current_model)

                if attempt < max_retries:
                    current_model = self.manager.get_model(family, exclude=excluded_models)
                    logger.info(f"Falling back to: {current_model}")
                else:
                    raise

            except anthropic.APIError as e:
                # Other API errors - don't retry with different model
                logger.error(f"Anthropic API error: {e}")
                raise

    def __getattr__(self, name):
        """Proxy other attributes to the underlying client."""
        return getattr(self.client, name)


# ============================================================================
# CLI FOR TESTING
# ============================================================================

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)

    print("\n" + "="*60)
    print("MODEL MANAGER TEST")
    print("="*60 + "\n")

    manager = get_model_manager()

    # Validate on startup
    print("Validating models...")
    report = manager.validate_on_startup()
    print(json.dumps(report, indent=2))

    print("\n" + "-"*60 + "\n")

    # Test getting models
    for family in manager.get_all_families():
        model = manager.get_model(family)
        print(f"{family}: {model}")

    print("\n" + "-"*60 + "\n")

    # Test fallback
    print("Testing fallback (simulating failure)...")
    sonnet = manager.get_model("sonnet")
    print(f"Initial: {sonnet}")

    next_model = manager.get_model_with_retry("sonnet", failed_model=sonnet)
    print(f"After failure: {next_model}")

    print("\n" + "="*60 + "\n")
