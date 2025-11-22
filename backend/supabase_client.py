"""
Supabase client for Premier Voice Assistant backend.
Handles database operations, auth, and storage.
"""
import os
from typing import Optional, Dict, List, Any
from supabase import create_client, Client
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SupabaseManager:
    """
    Manages all Supabase operations for the voice assistant.
    """

    def __init__(self, url: str = None, service_key: str = None):
        """
        Initialize Supabase client with service role key.

        Args:
            url: Supabase project URL
            service_key: Service role key (backend only, bypasses RLS)
        """
        self.url = url or os.getenv("SUPABASE_URL")
        self.service_key = service_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not self.url or not self.service_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
            )

        self.client: Client = create_client(self.url, self.service_key)
        logger.info(f"Supabase client initialized for {self.url}")

    # =========================================================================
    # USER PROFILE OPERATIONS
    # =========================================================================

    def get_or_create_user_profile(self, user_id: str, phone: str = None) -> Dict:
        """
        Get user profile or create if doesn't exist.

        Args:
            user_id: Supabase auth user ID
            phone: Optional phone number

        Returns:
            User profile dict
        """
        try:
            # Try to get existing profile
            result = (
                self.client.table("va_user_profiles")
                .select("*")
                .eq("id", user_id)
                .execute()
            )

            if result.data:
                return result.data[0]

            # Create new profile
            profile_data = {"id": user_id}
            if phone:
                profile_data["phone"] = phone

            result = self.client.table("va_user_profiles").insert(profile_data).execute()

            logger.info(f"Created new user profile for {user_id}")
            return result.data[0]

        except Exception as e:
            logger.error(f"Error getting/creating user profile: {e}")
            raise

    def update_user_preferences(
        self,
        user_id: str,
        preferred_voice: str = None,
        conversation_style: str = None,
        language: str = None,
    ) -> Dict:
        """Update user preferences."""
        try:
            updates = {}
            if preferred_voice:
                updates["preferred_voice"] = preferred_voice
            if conversation_style:
                updates["conversation_style"] = conversation_style
            if language:
                updates["language"] = language

            result = (
                self.client.table("va_user_profiles")
                .update(updates)
                .eq("id", user_id)
                .execute()
            )

            return result.data[0]

        except Exception as e:
            logger.error(f"Error updating user preferences: {e}")
            raise

    # =========================================================================
    # CONVERSATION OPERATIONS
    # =========================================================================

    def create_conversation(self, user_id: str, title: str = None) -> Dict:
        """
        Create a new conversation.

        Args:
            user_id: User ID
            title: Optional conversation title

        Returns:
            Conversation dict with id
        """
        try:
            conversation_data = {"user_id": user_id}
            if title:
                conversation_data["title"] = title

            result = (
                self.client.table("va_conversations").insert(conversation_data).execute()
            )

            logger.info(f"Created conversation {result.data[0]['id']} for user {user_id}")
            return result.data[0]

        except Exception as e:
            logger.error(f"Error creating conversation: {e}")
            raise

    def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Get a conversation by ID."""
        try:
            result = (
                self.client.table("va_conversations")
                .select("*")
                .eq("id", conversation_id)
                .execute()
            )

            return result.data[0] if result.data else None

        except Exception as e:
            logger.error(f"Error getting conversation: {e}")
            return None

    def get_user_conversations(
        self, user_id: str, limit: int = 20
    ) -> List[Dict]:
        """Get recent conversations for a user."""
        try:
            result = (
                self.client.table("va_conversations")
                .select("*")
                .eq("user_id", user_id)
                .order("last_message_at", desc=True)
                .limit(limit)
                .execute()
            )

            return result.data

        except Exception as e:
            logger.error(f"Error getting user conversations: {e}")
            return []

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        audio_url: str = None,
        metadata: Dict = None,
    ) -> Dict:
        """
        Add a message to a conversation.

        Args:
            conversation_id: Conversation ID
            role: 'user' or 'assistant'
            content: Message text
            audio_url: Optional URL to audio in storage
            metadata: Optional metadata (latency, etc.)

        Returns:
            Created message dict
        """
        try:
            message_data = {
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
            }

            if audio_url:
                message_data["audio_url"] = audio_url
            if metadata:
                message_data["metadata"] = metadata

            result = self.client.table("va_messages").insert(message_data).execute()

            return result.data[0]

        except Exception as e:
            logger.error(f"Error adding message: {e}")
            raise

    def get_conversation_messages(
        self, conversation_id: str, limit: int = 50
    ) -> List[Dict]:
        """Get messages for a conversation."""
        try:
            result = (
                self.client.table("va_messages")
                .select("*")
                .eq("conversation_id", conversation_id)
                .order("created_at", desc=False)
                .limit(limit)
                .execute()
            )

            return result.data

        except Exception as e:
            logger.error(f"Error getting conversation messages: {e}")
            return []

    # =========================================================================
    # VOICE CLONE OPERATIONS
    # =========================================================================

    def create_voice_clone(
        self,
        user_id: str,
        voice_name: str,
        display_name: str,
        reference_audio_url: str,
        sample_duration: float = None,
        modal_voice_id: str = None,
        is_public: bool = False,
    ) -> Dict:
        """Register a new voice clone."""
        try:
            voice_data = {
                "user_id": user_id,
                "voice_name": voice_name,
                "display_name": display_name,
                "reference_audio_url": reference_audio_url,
                "is_public": is_public,
            }

            if sample_duration:
                voice_data["sample_duration"] = sample_duration
            if modal_voice_id:
                voice_data["modal_voice_id"] = modal_voice_id

            result = self.client.table("va_voice_clones").insert(voice_data).execute()

            logger.info(f"Created voice clone '{voice_name}' for user {user_id}")
            return result.data[0]

        except Exception as e:
            logger.error(f"Error creating voice clone: {e}")
            raise

    def get_user_voice_clones(self, user_id: str) -> List[Dict]:
        """Get all voice clones for a user."""
        try:
            result = (
                self.client.table("va_voice_clones")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )

            return result.data

        except Exception as e:
            logger.error(f"Error getting voice clones: {e}")
            return []

    def get_public_voice_clones(self) -> List[Dict]:
        """Get all public voice clones."""
        try:
            result = (
                self.client.table("va_voice_clones")
                .select("*")
                .eq("is_public", True)
                .execute()
            )

            return result.data

        except Exception as e:
            logger.error(f"Error getting public voice clones: {e}")
            return []

    # =========================================================================
    # USAGE METRICS OPERATIONS
    # =========================================================================

    def log_usage_metric(
        self,
        user_id: str = None,
        conversation_id: str = None,
        event_type: str = "transcribe",
        stt_latency_ms: int = None,
        llm_latency_ms: int = None,
        tts_latency_ms: int = None,
        total_latency_ms: int = None,
        tokens_used: int = None,
        input_tokens: int = None,
        output_tokens: int = None,
        cost_cents: float = None,
        audio_duration_seconds: float = None,
        error: str = None,
        metadata: Dict = None,
    ) -> Dict:
        """
        Log a usage metric event.

        Args:
            user_id: Optional user ID
            conversation_id: Optional conversation ID
            event_type: Type of event (transcribe, generate, synthesize, clone_voice)
            stt_latency_ms: STT latency in milliseconds
            llm_latency_ms: LLM latency in milliseconds
            tts_latency_ms: TTS latency in milliseconds
            total_latency_ms: Total pipeline latency
            tokens_used: Number of LLM tokens used (deprecated, use input_tokens + output_tokens)
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost_cents: Cost of this operation in cents
            audio_duration_seconds: Duration of audio processed
            error: Error message if failed
            metadata: Additional metadata

        Returns:
            Created metric dict
        """
        try:
            metric_data = {"event_type": event_type}

            if user_id:
                metric_data["user_id"] = user_id
            if conversation_id:
                metric_data["conversation_id"] = conversation_id
            if stt_latency_ms is not None:
                metric_data["stt_latency_ms"] = stt_latency_ms
            if llm_latency_ms is not None:
                metric_data["llm_latency_ms"] = llm_latency_ms
            if tts_latency_ms is not None:
                metric_data["tts_latency_ms"] = tts_latency_ms
            if total_latency_ms is not None:
                metric_data["total_latency_ms"] = total_latency_ms
            if tokens_used is not None:
                metric_data["tokens_used"] = tokens_used
            if input_tokens is not None:
                metric_data["input_tokens"] = input_tokens
            if output_tokens is not None:
                metric_data["output_tokens"] = output_tokens
            if cost_cents is not None:
                metric_data["cost_cents"] = cost_cents
            if audio_duration_seconds is not None:
                metric_data["audio_duration_seconds"] = audio_duration_seconds
            if error:
                metric_data["error"] = error
            if metadata:
                metric_data["metadata"] = metadata

            result = self.client.table("va_usage_metrics").insert(metric_data).execute()

            return result.data[0]

        except Exception as e:
            logger.error(f"Error logging usage metric: {e}")
            # Don't raise - logging failures shouldn't break the app
            return {}

    def get_user_metrics(
        self, user_id: str, days: int = 7, limit: int = 100
    ) -> List[Dict]:
        """Get recent usage metrics for a user."""
        try:
            result = (
                self.client.table("va_usage_metrics")
                .select("*")
                .eq("user_id", user_id)
                .gte("created_at", f"now() - interval '{days} days'")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            return result.data

        except Exception as e:
            logger.error(f"Error getting user metrics: {e}")
            return []

    # =========================================================================
    # STORAGE OPERATIONS
    # =========================================================================

    def upload_audio(
        self, bucket: str, file_path: str, audio_bytes: bytes
    ) -> str:
        """
        Upload audio file to Supabase Storage.

        Args:
            bucket: Storage bucket name ('va-voice-recordings' or 'va-voice-clones')
            file_path: Path within bucket (e.g., 'user_id/recording.wav')
            audio_bytes: Audio file bytes

        Returns:
            Public URL to the uploaded file
        """
        try:
            result = self.client.storage.from_(bucket).upload(
                file_path, audio_bytes, {"content-type": "audio/wav"}
            )

            # Get public URL
            url = self.client.storage.from_(bucket).get_public_url(file_path)

            logger.info(f"Uploaded audio to {bucket}/{file_path}")
            return url

        except Exception as e:
            logger.error(f"Error uploading audio: {e}")
            raise

    def download_audio(self, bucket: str, file_path: str) -> bytes:
        """Download audio from storage."""
        try:
            result = self.client.storage.from_(bucket).download(file_path)
            return result

        except Exception as e:
            logger.error(f"Error downloading audio: {e}")
            raise

    def delete_audio(self, bucket: str, file_path: str):
        """Delete audio from storage."""
        try:
            self.client.storage.from_(bucket).remove([file_path])
            logger.info(f"Deleted audio from {bucket}/{file_path}")

        except Exception as e:
            logger.error(f"Error deleting audio: {e}")
            raise


# Singleton instance
_supabase_manager: Optional[SupabaseManager] = None


def get_supabase() -> SupabaseManager:
    """Get or create Supabase manager singleton."""
    global _supabase_manager
    if _supabase_manager is None:
        _supabase_manager = SupabaseManager()
    return _supabase_manager
