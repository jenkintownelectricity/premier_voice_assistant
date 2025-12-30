"""
Telephony API Router

Provides unified API endpoints for all telephony providers.
Handles voice calls, SMS, webhooks, and provider management.
"""

import os
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Request, Response, Header
from pydantic import BaseModel

from backend.telephony.factory import (
    get_factory,
    get_default_provider,
    list_providers,
    init_providers_from_env,
)
from backend.telephony.provider import (
    CallStatus,
    SMSStatus,
    CallDirection,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ProviderStatus(BaseModel):
    """Status of a telephony provider."""
    name: str
    configured: bool
    healthy: bool
    phone_number: Optional[str] = None
    sip_configured: bool = False
    message: str


class TelephonyStatusResponse(BaseModel):
    """Overall telephony status response."""
    default_provider: Optional[str]
    providers: List[ProviderStatus]
    available_providers: List[str]


class InitiateCallRequest(BaseModel):
    """Request to initiate an outbound call."""
    to_number: str
    provider: Optional[str] = None  # Use default if not specified
    from_number: Optional[str] = None
    room_name: Optional[str] = None
    user_id: Optional[str] = None
    assistant_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class InitiateCallResponse(BaseModel):
    """Response from initiating a call."""
    success: bool
    call_id: Optional[str] = None
    provider_call_id: Optional[str] = None
    room_name: Optional[str] = None
    status: str
    provider: str
    error: Optional[str] = None


class SendSMSRequest(BaseModel):
    """Request to send an SMS."""
    to_number: str
    message: str
    provider: Optional[str] = None
    from_number: Optional[str] = None
    user_id: Optional[str] = None
    assistant_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SendSMSResponse(BaseModel):
    """Response from sending an SMS."""
    success: bool
    message_id: Optional[str] = None
    provider_message_id: Optional[str] = None
    status: str
    provider: str
    segments: int = 1
    error: Optional[str] = None


class PhoneNumberResponse(BaseModel):
    """Phone number information."""
    number: str
    provider: str
    capabilities: List[str]
    friendly_name: Optional[str] = None
    region: Optional[str] = None
    monthly_cost: Optional[float] = None


# ============================================================================
# STATUS ENDPOINTS
# ============================================================================

@router.get("/status", response_model=TelephonyStatusResponse)
async def get_telephony_status():
    """Get status of all telephony providers."""
    factory = get_factory()

    # Initialize providers if not already done
    if not factory.list_registered():
        init_providers_from_env()

    provider_statuses = []
    health_results = await factory.health_check_all()

    for name in factory.list_registered():
        provider = factory.get(name)
        health = health_results.get(name, {})

        provider_statuses.append(ProviderStatus(
            name=name,
            configured=provider.is_configured if provider else False,
            healthy=health.get("healthy", False),
            phone_number=health.get("details", {}).get("phone_number"),
            sip_configured=health.get("details", {}).get("sip_configured", False),
            message=health.get("message", "Unknown"),
        ))

    default = factory.get()

    return TelephonyStatusResponse(
        default_provider=default.provider_name if default else None,
        providers=provider_statuses,
        available_providers=list_providers(),
    )


@router.get("/providers")
async def list_available_providers():
    """List all available telephony providers."""
    factory = get_factory()

    if not factory.list_registered():
        init_providers_from_env()

    return {
        "registered": factory.list_registered(),
        "available": list_providers(),
        "default": factory.get().provider_name if factory.get() else None,
    }


@router.post("/providers/{provider_name}/set-default")
async def set_default_provider(provider_name: str):
    """Set the default telephony provider."""
    factory = get_factory()

    if provider_name not in factory.list_registered():
        raise HTTPException(status_code=404, detail=f"Provider {provider_name} not registered")

    if not factory.set_default(provider_name):
        raise HTTPException(status_code=500, detail="Failed to set default provider")

    return {"success": True, "default_provider": provider_name}


# ============================================================================
# VOICE CALL ENDPOINTS
# ============================================================================

@router.post("/calls/initiate", response_model=InitiateCallResponse)
async def initiate_call(request: InitiateCallRequest):
    """Initiate an outbound phone call."""
    factory = get_factory()

    if not factory.list_registered():
        init_providers_from_env()

    # Get the provider
    provider = factory.get(request.provider) if request.provider else factory.get()

    if not provider:
        raise HTTPException(status_code=503, detail="No telephony provider available")

    if not provider.is_configured:
        raise HTTPException(
            status_code=503,
            detail=f"Provider {provider.provider_name} is not configured"
        )

    # Initiate the call
    result = await provider.initiate_call(
        to_number=request.to_number,
        from_number=request.from_number,
        room_name=request.room_name,
        metadata=request.metadata,
    )

    # Log to database if available
    if result.success:
        try:
            from backend.supabase_client import get_supabase
            supabase = get_supabase().client
            supabase.table("va_call_logs").insert({
                "user_id": request.user_id,
                "assistant_id": request.assistant_id,
                "call_type": "phone",
                "status": "initiating",
                "started_at": datetime.utcnow().isoformat(),
                "metadata": {
                    "room_name": result.room_name,
                    "provider": provider.provider_name,
                    "provider_call_id": result.provider_call_id,
                    "to_number": request.to_number,
                    "direction": "outbound",
                    **(request.metadata or {})
                }
            }).execute()
        except Exception as e:
            logger.warning(f"Failed to log call: {e}")

    return InitiateCallResponse(
        success=result.success,
        call_id=result.call_id,
        provider_call_id=result.provider_call_id,
        room_name=result.room_name,
        status=result.status.value,
        provider=provider.provider_name,
        error=result.error,
    )


@router.post("/calls/{call_id}/end")
async def end_call(call_id: str, provider: Optional[str] = None):
    """End an active call."""
    factory = get_factory()
    prov = factory.get(provider) if provider else factory.get()

    if not prov:
        raise HTTPException(status_code=503, detail="No telephony provider available")

    success = await prov.end_call(call_id)

    return {"success": success, "call_id": call_id}


@router.get("/calls/{call_id}/status")
async def get_call_status(call_id: str, provider: Optional[str] = None):
    """Get the status of a call."""
    factory = get_factory()
    prov = factory.get(provider) if provider else factory.get()

    if not prov:
        raise HTTPException(status_code=503, detail="No telephony provider available")

    status = await prov.get_call_status(call_id)

    return {
        "call_id": call_id,
        "status": status.value if status else "unknown",
        "provider": prov.provider_name,
    }


# ============================================================================
# SMS ENDPOINTS
# ============================================================================

@router.post("/sms/send", response_model=SendSMSResponse)
async def send_sms(request: SendSMSRequest):
    """Send an SMS message."""
    factory = get_factory()

    if not factory.list_registered():
        init_providers_from_env()

    provider = factory.get(request.provider) if request.provider else factory.get()

    if not provider:
        raise HTTPException(status_code=503, detail="No telephony provider available")

    if not provider.is_configured:
        raise HTTPException(
            status_code=503,
            detail=f"Provider {provider.provider_name} is not configured"
        )

    result = await provider.send_sms(
        to_number=request.to_number,
        message=request.message,
        from_number=request.from_number,
        metadata=request.metadata,
    )

    # Log to database if available
    if result.success:
        try:
            from backend.supabase_client import get_supabase
            supabase = get_supabase().client
            supabase.table("va_sms_logs").insert({
                "user_id": request.user_id,
                "assistant_id": request.assistant_id,
                "phone_number": request.to_number,
                "direction": "outbound",
                "message": request.message,
                "message_sid": result.provider_message_id,
                "provider": provider.provider_name,
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
        except Exception as e:
            logger.warning(f"Failed to log SMS: {e}")

    return SendSMSResponse(
        success=result.success,
        message_id=result.message_id,
        provider_message_id=result.provider_message_id,
        status=result.status.value,
        provider=provider.provider_name,
        segments=result.segments,
        error=result.error,
    )


@router.get("/sms/{message_id}/status")
async def get_sms_status(message_id: str, provider: Optional[str] = None):
    """Get the status of an SMS message."""
    factory = get_factory()
    prov = factory.get(provider) if provider else factory.get()

    if not prov:
        raise HTTPException(status_code=503, detail="No telephony provider available")

    status = await prov.get_sms_status(message_id)

    return {
        "message_id": message_id,
        "status": status.value if status else "unknown",
        "provider": prov.provider_name,
    }


# ============================================================================
# PHONE NUMBER ENDPOINTS
# ============================================================================

@router.get("/numbers", response_model=List[PhoneNumberResponse])
async def list_phone_numbers(provider: Optional[str] = None):
    """List all phone numbers across providers."""
    factory = get_factory()

    if not factory.list_registered():
        init_providers_from_env()

    all_numbers = []

    if provider:
        # List from specific provider
        prov = factory.get(provider)
        if prov and prov.is_configured:
            numbers = await prov.list_phone_numbers()
            all_numbers.extend(numbers)
    else:
        # List from all configured providers
        for prov in factory.get_configured_providers():
            numbers = await prov.list_phone_numbers()
            all_numbers.extend(numbers)

    return [
        PhoneNumberResponse(
            number=n.number,
            provider=n.provider,
            capabilities=n.capabilities,
            friendly_name=n.friendly_name,
            region=n.region,
            monthly_cost=n.monthly_cost,
        )
        for n in all_numbers
    ]


@router.get("/numbers/search", response_model=List[PhoneNumberResponse])
async def search_available_numbers(
    provider: Optional[str] = None,
    country: str = "US",
    area_code: Optional[str] = None,
    contains: Optional[str] = None,
    limit: int = 10,
):
    """Search for available phone numbers to purchase."""
    factory = get_factory()
    prov = factory.get(provider) if provider else factory.get()

    if not prov:
        raise HTTPException(status_code=503, detail="No telephony provider available")

    numbers = await prov.search_available_numbers(
        country=country,
        area_code=area_code,
        contains=contains,
        limit=limit,
    )

    return [
        PhoneNumberResponse(
            number=n.number,
            provider=n.provider,
            capabilities=n.capabilities,
            friendly_name=n.friendly_name,
            region=n.region,
            monthly_cost=n.monthly_cost,
        )
        for n in numbers
    ]


# ============================================================================
# WEBHOOK ENDPOINTS (Provider-specific)
# ============================================================================

async def _handle_voice_webhook(
    request: Request,
    provider_name: str,
    webhook_type: str,
) -> Response:
    """Generic handler for voice webhooks."""
    factory = get_factory()
    provider = factory.get(provider_name)

    if not provider:
        logger.error(f"Provider {provider_name} not found for webhook")
        return Response(content="<Response/>", media_type="application/xml")

    try:
        # Get request data
        if request.headers.get("content-type", "").startswith("application/json"):
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)

        # Parse webhook data
        call_data = provider.parse_webhook_call(data)

        logger.info(
            f"{provider_name} {webhook_type}: {call_data.get('call_id')} "
            f"from {call_data.get('from_number')} - {call_data.get('status')}"
        )

        # Handle connect webhooks - generate response to connect to LiveKit
        if webhook_type == "connect":
            room = request.query_params.get("room", f"phone-{uuid.uuid4().hex[:12]}")
            response_content = provider.generate_call_response(
                room_name=room,
                caller_number=call_data.get("from_number", ""),
                called_number=call_data.get("to_number", ""),
            )

            # Determine content type
            if provider_name == "vonage":
                return Response(content=response_content, media_type="application/json")
            else:
                return Response(content=response_content, media_type="application/xml")

        # Status webhooks - just acknowledge
        return Response(content="<Response/>", media_type="application/xml")

    except Exception as e:
        logger.error(f"Error handling {provider_name} voice webhook: {e}")
        return Response(content="<Response/>", media_type="application/xml")


async def _handle_sms_webhook(
    request: Request,
    provider_name: str,
) -> Response:
    """Generic handler for SMS webhooks."""
    factory = get_factory()
    provider = factory.get(provider_name)

    if not provider:
        logger.error(f"Provider {provider_name} not found for SMS webhook")
        return Response(content="<Response/>", media_type="application/xml")

    try:
        # Get request data
        if request.headers.get("content-type", "").startswith("application/json"):
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)

        # Parse webhook data
        sms_data = provider.parse_webhook_sms(data)

        logger.info(
            f"{provider_name} SMS: {sms_data.get('message_id')} "
            f"from {sms_data.get('from_number')}"
        )

        # Generate AI response for inbound SMS
        response_text = await _generate_sms_response(
            sms_data.get("body", ""),
            sms_data.get("from_number", ""),
        )

        # Log to database
        try:
            from backend.supabase_client import get_supabase
            supabase = get_supabase().client
            supabase.table("va_sms_logs").insert({
                "phone_number": sms_data.get("from_number"),
                "direction": "inbound",
                "message": sms_data.get("body"),
                "response": response_text,
                "message_sid": sms_data.get("message_id"),
                "provider": provider_name,
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
        except Exception as e:
            logger.warning(f"Failed to log SMS: {e}")

        # Return provider-specific response format
        if provider_name == "vonage":
            return Response(content="", status_code=200)
        elif provider_name == "telnyx":
            return Response(content="", status_code=200)
        else:
            # TwiML-style response
            return Response(
                content=f'<Response><Message>{response_text}</Message></Response>',
                media_type="application/xml"
            )

    except Exception as e:
        logger.error(f"Error handling {provider_name} SMS webhook: {e}")
        return Response(content="<Response/>", media_type="application/xml")


async def _generate_sms_response(message: str, phone_number: str) -> str:
    """Generate an AI response for SMS."""
    try:
        from backend.brain_client import FastBrainClient
        brain_url = os.getenv("FAST_BRAIN_URL", "")

        if brain_url:
            brain = FastBrainClient(base_url=brain_url, default_skill="sms")

            if await brain.is_healthy():
                response_parts = []
                async for token in brain.stream(message, skill="sms"):
                    response_parts.append(token)
                response = "".join(response_parts)
                await brain.close()
                return response[:160] if len(response) > 160 else response

    except Exception as e:
        logger.warning(f"Brain client not available for SMS: {e}")

    return "Thanks for your message! For full conversations, visit hive215.com"


# Provider-specific webhook routes
@router.post("/{provider_name}/voice/connect")
async def handle_voice_connect(provider_name: str, request: Request):
    """Handle voice connect webhook for any provider."""
    return await _handle_voice_webhook(request, provider_name, "connect")


@router.post("/{provider_name}/voice/status")
async def handle_voice_status(provider_name: str, request: Request):
    """Handle voice status webhook for any provider."""
    return await _handle_voice_webhook(request, provider_name, "status")


@router.post("/{provider_name}/sms/incoming")
async def handle_sms_incoming(provider_name: str, request: Request):
    """Handle incoming SMS webhook for any provider."""
    return await _handle_sms_webhook(request, provider_name)
