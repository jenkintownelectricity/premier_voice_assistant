"""
LiveKit API Endpoints

Provides REST API endpoints for:
- Creating LiveKit rooms for voice sessions
- Generating access tokens for participants
- Managing agent dispatching
- Monitoring active sessions

Usage:
    from backend.livekit_api import router
    app.include_router(router, prefix="/livekit", tags=["livekit"])
"""

import os
import json
import logging
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel

# LiveKit SDK
try:
    from livekit import api as livekit_api
    from livekit.api import AccessToken, VideoGrants
    LIVEKIT_AVAILABLE = True
except ImportError:
    LIVEKIT_AVAILABLE = False
    logger_warning = "LiveKit SDK not installed. Run: pip install livekit"

from backend.supabase_client import get_supabase, SupabaseManager

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


# ============================================================================
# CONFIGURATION
# ============================================================================

def get_livekit_config() -> Dict[str, str]:
    """Get LiveKit configuration from environment."""
    return {
        "url": os.getenv("LIVEKIT_URL", ""),
        "api_key": os.getenv("LIVEKIT_API_KEY", ""),
        "api_secret": os.getenv("LIVEKIT_API_SECRET", ""),
    }


def is_livekit_configured() -> bool:
    """Check if LiveKit is properly configured."""
    config = get_livekit_config()
    return all([
        LIVEKIT_AVAILABLE,
        config["url"],
        config["api_key"],
        config["api_secret"],
    ])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class CreateRoomRequest(BaseModel):
    """Request to create a new LiveKit room for voice session."""
    assistant_id: str
    room_name: Optional[str] = None  # Auto-generated if not provided
    metadata: Optional[Dict[str, Any]] = None


class CreateRoomResponse(BaseModel):
    """Response with room details and access token."""
    room_name: str
    token: str
    url: str
    assistant_id: str
    call_id: Optional[str] = None
    expires_at: str


class RoomStatus(BaseModel):
    """Status of a LiveKit room."""
    room_name: str
    participant_count: int
    has_agent: bool
    created_at: str
    metadata: Optional[Dict] = None


class LiveKitStatus(BaseModel):
    """LiveKit service status."""
    enabled: bool
    configured: bool
    url: Optional[str] = None
    message: str


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/status", response_model=LiveKitStatus)
async def get_livekit_status():
    """
    Check LiveKit service status and configuration.

    Returns:
        LiveKitStatus: Configuration status and availability
    """
    config = get_livekit_config()

    if not LIVEKIT_AVAILABLE:
        return LiveKitStatus(
            enabled=False,
            configured=False,
            message="LiveKit SDK not installed. Run: pip install livekit"
        )

    if not config["url"] or not config["api_key"] or not config["api_secret"]:
        missing = []
        if not config["url"]:
            missing.append("LIVEKIT_URL")
        if not config["api_key"]:
            missing.append("LIVEKIT_API_KEY")
        if not config["api_secret"]:
            missing.append("LIVEKIT_API_SECRET")

        return LiveKitStatus(
            enabled=False,
            configured=False,
            message=f"Missing environment variables: {', '.join(missing)}"
        )

    return LiveKitStatus(
        enabled=True,
        configured=True,
        url=config["url"],
        message="LiveKit is configured and ready"
    )


@router.post("/rooms", response_model=CreateRoomResponse)
async def create_room(
    request: CreateRoomRequest,
    user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Create a new LiveKit room for a voice session.

    This creates a room and returns an access token for the user to join.
    The agent worker will automatically join when it detects a new room.

    Headers:
        X-User-ID: Required user ID

    Request Body:
        assistant_id: ID of the assistant to use
        room_name: Optional custom room name
        metadata: Optional additional metadata

    Returns:
        CreateRoomResponse: Room details and access token
    """
    if not is_livekit_configured():
        raise HTTPException(
            status_code=503,
            detail="LiveKit is not configured. Check environment variables."
        )

    config = get_livekit_config()

    try:
        # Verify assistant exists
        supabase = get_supabase_client()
        assistant_result = supabase.table("va_assistants").select(
            "id, name, user_id"
        ).eq("id", request.assistant_id).single().execute()

        if not assistant_result.data:
            raise HTTPException(status_code=404, detail="Assistant not found")

        # Verify user owns the assistant
        if assistant_result.data.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this assistant")

        assistant_name = assistant_result.data.get("name", "Assistant")

        # Generate room name if not provided
        room_name = request.room_name or f"hive-{uuid.uuid4().hex[:12]}"

        # Create call log entry
        call_result = supabase.table("va_call_logs").insert({
            "user_id": user_id,
            "assistant_id": request.assistant_id,
            "call_type": "livekit",
            "status": "connecting",
            "started_at": datetime.utcnow().isoformat(),
            "metadata": {
                "room_name": room_name,
                "transport": "webrtc",
                "assistant_name": assistant_name,
                **(request.metadata or {}),
            }
        }).execute()

        call_id = call_result.data[0]["id"] if call_result.data else None

        # Prepare room metadata for the agent
        room_metadata = json.dumps({
            "assistant_id": request.assistant_id,
            "user_id": user_id,
            "call_id": call_id,
            "assistant_name": assistant_name,
        })

        # Create access token for user
        token = AccessToken(
            api_key=config["api_key"],
            api_secret=config["api_secret"],
        )
        token.with_identity(f"user-{user_id[:8]}")
        token.with_name(f"User")
        token.with_grants(VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
        ))
        token.with_metadata(json.dumps({"user_id": user_id}))

        # Set token expiration (1 hour)
        expires_at = datetime.utcnow() + timedelta(hours=1)
        token.with_ttl(timedelta(hours=1))

        jwt_token = token.to_jwt()

        # Create room via API (with metadata for agent)
        room_api = livekit_api.LiveKitAPI(
            url=config["url"],
            api_key=config["api_key"],
            api_secret=config["api_secret"],
        )

        try:
            await room_api.room.create_room(
                livekit_api.CreateRoomRequest(
                    name=room_name,
                    metadata=room_metadata,
                    empty_timeout=300,  # 5 minute timeout for empty rooms
                    max_participants=2,  # User + Agent
                )
            )
            logger.info(f"Created LiveKit room: {room_name}")
        finally:
            await room_api.aclose()

        return CreateRoomResponse(
            room_name=room_name,
            token=jwt_token,
            url=config["url"],
            assistant_id=request.assistant_id,
            call_id=call_id,
            expires_at=expires_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create room: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms", response_model=List[RoomStatus])
async def list_rooms(
    user_id: str = Header(..., alias="X-User-ID"),
):
    """
    List active LiveKit rooms for the user.

    Headers:
        X-User-ID: Required user ID

    Returns:
        List[RoomStatus]: List of active rooms
    """
    if not is_livekit_configured():
        raise HTTPException(
            status_code=503,
            detail="LiveKit is not configured"
        )

    config = get_livekit_config()

    try:
        room_api = livekit_api.LiveKitAPI(
            url=config["url"],
            api_key=config["api_key"],
            api_secret=config["api_secret"],
        )

        try:
            # List all rooms
            rooms_response = await room_api.room.list_rooms(
                livekit_api.ListRoomsRequest()
            )

            # Filter rooms belonging to this user
            user_rooms = []
            for room in rooms_response.rooms:
                try:
                    metadata = json.loads(room.metadata) if room.metadata else {}
                    if metadata.get("user_id") == user_id:
                        user_rooms.append(RoomStatus(
                            room_name=room.name,
                            participant_count=room.num_participants,
                            has_agent=any(
                                p.identity.startswith("agent-")
                                for p in room.active_recording  # Check participants
                            ) if hasattr(room, 'active_recording') else False,
                            created_at=datetime.fromtimestamp(room.creation_time).isoformat()
                            if room.creation_time else datetime.utcnow().isoformat(),
                            metadata=metadata,
                        ))
                except (json.JSONDecodeError, AttributeError):
                    continue

            return user_rooms

        finally:
            await room_api.aclose()

    except Exception as e:
        logger.error(f"Failed to list rooms: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rooms/{room_name}")
async def delete_room(
    room_name: str,
    user_id: str = Header(..., alias="X-User-ID"),
):
    """
    End a LiveKit session by deleting the room.

    Path Parameters:
        room_name: Name of the room to delete

    Headers:
        X-User-ID: Required user ID
    """
    if not is_livekit_configured():
        raise HTTPException(
            status_code=503,
            detail="LiveKit is not configured"
        )

    config = get_livekit_config()

    try:
        room_api = livekit_api.LiveKitAPI(
            url=config["url"],
            api_key=config["api_key"],
            api_secret=config["api_secret"],
        )

        try:
            # Get room to verify ownership
            rooms = await room_api.room.list_rooms(
                livekit_api.ListRoomsRequest(names=[room_name])
            )

            if not rooms.rooms:
                raise HTTPException(status_code=404, detail="Room not found")

            room = rooms.rooms[0]
            metadata = json.loads(room.metadata) if room.metadata else {}

            if metadata.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Access denied")

            # Delete the room
            await room_api.room.delete_room(
                livekit_api.DeleteRoomRequest(room=room_name)
            )

            # Update call log
            if metadata.get("call_id"):
                supabase = get_supabase_client()
                supabase.table("va_call_logs").update({
                    "status": "completed",
                    "ended_at": datetime.utcnow().isoformat(),
                    "ended_reason": "user_ended",
                }).eq("id", metadata["call_id"]).execute()

            logger.info(f"Deleted LiveKit room: {room_name}")

            return {"success": True, "message": f"Room {room_name} deleted"}

        finally:
            await room_api.aclose()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete room: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rooms/{room_name}/token")
async def get_room_token(
    room_name: str,
    user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Get a new access token for an existing room.

    Useful for reconnecting to a room after token expiration.

    Path Parameters:
        room_name: Name of the room

    Headers:
        X-User-ID: Required user ID

    Returns:
        Access token and expiration
    """
    if not is_livekit_configured():
        raise HTTPException(
            status_code=503,
            detail="LiveKit is not configured"
        )

    config = get_livekit_config()

    try:
        # Verify room exists and user has access
        room_api = livekit_api.LiveKitAPI(
            url=config["url"],
            api_key=config["api_key"],
            api_secret=config["api_secret"],
        )

        try:
            rooms = await room_api.room.list_rooms(
                livekit_api.ListRoomsRequest(names=[room_name])
            )

            if not rooms.rooms:
                raise HTTPException(status_code=404, detail="Room not found")

            room = rooms.rooms[0]
            metadata = json.loads(room.metadata) if room.metadata else {}

            if metadata.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Access denied")

        finally:
            await room_api.aclose()

        # Create new token
        token = AccessToken(
            api_key=config["api_key"],
            api_secret=config["api_secret"],
        )
        token.with_identity(f"user-{user_id[:8]}")
        token.with_name("User")
        token.with_grants(VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
        ))

        expires_at = datetime.utcnow() + timedelta(hours=1)
        token.with_ttl(timedelta(hours=1))

        return {
            "token": token.to_jwt(),
            "expires_at": expires_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get room token: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AGENT DISPATCH (for programmatic agent control)
# ============================================================================

@router.post("/dispatch")
async def dispatch_agent(
    request: CreateRoomRequest,
    user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Dispatch an agent to a room.

    This is an alternative to the automatic agent dispatch.
    Creates a room and explicitly requests an agent to join.

    Note: This requires the agent worker to be running and configured
    for explicit dispatch mode.
    """
    # For now, this is the same as create_room
    # In a more advanced setup, you could use LiveKit's agent dispatch API
    return await create_room(request, user_id)


# ============================================================================
# METRICS & MONITORING
# ============================================================================

@router.get("/metrics")
async def get_livekit_metrics(
    user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Get LiveKit usage metrics for the user.

    Returns aggregate statistics about LiveKit voice sessions.
    """
    try:
        supabase = get_supabase_client()

        # Get LiveKit call statistics
        result = supabase.table("va_call_logs").select(
            "id, duration_seconds, started_at"
        ).eq("user_id", user_id).eq("call_type", "livekit").execute()

        calls = result.data or []

        total_calls = len(calls)
        total_duration = sum(c.get("duration_seconds", 0) or 0 for c in calls)
        avg_duration = total_duration / total_calls if total_calls > 0 else 0

        # Get calls from last 30 days
        thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
        recent_calls = [
            c for c in calls
            if c.get("started_at", "") >= thirty_days_ago
        ]

        return {
            "total_calls": total_calls,
            "total_duration_seconds": total_duration,
            "average_duration_seconds": round(avg_duration, 1),
            "calls_last_30_days": len(recent_calls),
            "transport": "webrtc",
            "latency_improvement": "50-100ms vs WebSocket",
        }

    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
