"""
HIVE215 Deployment Kernel

Deployment health monitoring and service readiness checks. Tracks the
health of all deployed services and provides readiness verdicts.

Trust model:
    - Health check responses: PARTIALLY TRUSTED (external service)
    - Readiness verdicts: TRUSTED (after validation)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class ServiceType(Enum):
    """Known deployed service types."""
    WEB_API = "web_api"
    VOICE_WORKER = "voice_worker"
    FAST_BRAIN = "fast_brain"
    DEEPGRAM_STT = "deepgram_stt"
    CARTESIA_TTS = "cartesia_tts"
    LIVEKIT = "livekit"
    SUPABASE = "supabase"
    MODAL_WHISPER = "modal_whisper"
    MODAL_COQUI = "modal_coqui"
    MODAL_KOKORO = "modal_kokoro"


class ServiceHealth(Enum):
    """Health status of a deployed service."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"


class ReadinessVerdict(Enum):
    """System-wide readiness verdict."""
    READY = "ready"
    READY_DEGRADED = "ready_degraded"  # Core services up, some auxiliary down
    NOT_READY = "not_ready"


# Services required for the system to be READY
CORE_SERVICES = {
    ServiceType.WEB_API,
    ServiceType.VOICE_WORKER,
    ServiceType.LIVEKIT,
    ServiceType.DEEPGRAM_STT,
}

# Services that degrade but don't block readiness
AUXILIARY_SERVICES = {
    ServiceType.FAST_BRAIN,
    ServiceType.CARTESIA_TTS,
    ServiceType.SUPABASE,
    ServiceType.MODAL_WHISPER,
    ServiceType.MODAL_COQUI,
    ServiceType.MODAL_KOKORO,
}


@dataclass(frozen=True)
class ServiceHealthRecord:
    """Health record for a single service."""
    service: ServiceType
    health: ServiceHealth
    latency_ms: Optional[int]
    checked_utc: str
    endpoint: Optional[str] = None
    error_message: Optional[str] = None
    version: Optional[str] = None


@dataclass(frozen=True)
class ReadinessReport:
    """System-wide readiness report."""
    report_id: str
    verdict: ReadinessVerdict
    timestamp_utc: str
    service_statuses: dict[str, str]
    core_services_healthy: int
    core_services_total: int
    auxiliary_services_healthy: int
    auxiliary_services_total: int
    issues: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DeploymentReceipt:
    """Receipt for a deployment health check."""
    receipt_id: str
    report_id: str
    verdict: ReadinessVerdict
    timestamp_utc: str
    services_checked: int


class DeploymentKernel:
    """
    Deployment health monitoring and readiness checks.

    Tracks health of all services and produces readiness verdicts.
    Core services must be healthy for READY verdict. Auxiliary service
    failures result in READY_DEGRADED.
    """

    def __init__(self) -> None:
        self._health_records: dict[ServiceType, ServiceHealthRecord] = {}

    def record_health(
        self,
        service: ServiceType,
        health: ServiceHealth,
        latency_ms: Optional[int] = None,
        endpoint: Optional[str] = None,
        error_message: Optional[str] = None,
        version: Optional[str] = None,
    ) -> ServiceHealthRecord:
        """Record a health check result for a service."""
        record = ServiceHealthRecord(
            service=service,
            health=health,
            latency_ms=latency_ms,
            checked_utc=datetime.now(timezone.utc).isoformat(),
            endpoint=endpoint,
            error_message=error_message,
            version=version,
        )
        self._health_records[service] = record
        return record

    def check_readiness(self) -> tuple[ReadinessReport, DeploymentReceipt]:
        """
        Produce a system-wide readiness report.

        Returns (ReadinessReport, DeploymentReceipt).
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        report_id = str(uuid.uuid4())
        receipt_id = str(uuid.uuid4())
        issues: list[str] = []

        # Check core services
        core_healthy = 0
        for service in CORE_SERVICES:
            record = self._health_records.get(service)
            if record is None:
                issues.append(f"CORE service {service.value} has not been checked")
            elif record.health == ServiceHealth.HEALTHY:
                core_healthy += 1
            else:
                issues.append(
                    f"CORE service {service.value} is {record.health.value}"
                    + (f": {record.error_message}" if record.error_message else "")
                )

        # Check auxiliary services
        aux_healthy = 0
        for service in AUXILIARY_SERVICES:
            record = self._health_records.get(service)
            if record is None:
                issues.append(f"AUXILIARY service {service.value} has not been checked")
            elif record.health == ServiceHealth.HEALTHY:
                aux_healthy += 1
            else:
                issues.append(
                    f"AUXILIARY service {service.value} is {record.health.value}"
                    + (f": {record.error_message}" if record.error_message else "")
                )

        # Determine verdict
        if core_healthy == len(CORE_SERVICES):
            if aux_healthy == len(AUXILIARY_SERVICES):
                verdict = ReadinessVerdict.READY
            else:
                verdict = ReadinessVerdict.READY_DEGRADED
        else:
            verdict = ReadinessVerdict.NOT_READY

        service_statuses = {
            service.value: (
                self._health_records[service].health.value
                if service in self._health_records
                else "unchecked"
            )
            for service in list(CORE_SERVICES) + list(AUXILIARY_SERVICES)
        }

        report = ReadinessReport(
            report_id=report_id,
            verdict=verdict,
            timestamp_utc=now_utc,
            service_statuses=service_statuses,
            core_services_healthy=core_healthy,
            core_services_total=len(CORE_SERVICES),
            auxiliary_services_healthy=aux_healthy,
            auxiliary_services_total=len(AUXILIARY_SERVICES),
            issues=issues,
        )

        receipt = DeploymentReceipt(
            receipt_id=receipt_id,
            report_id=report_id,
            verdict=verdict,
            timestamp_utc=now_utc,
            services_checked=len(self._health_records),
        )

        return report, receipt

    def get_service_health(self, service: ServiceType) -> Optional[ServiceHealthRecord]:
        """Get the latest health record for a service."""
        return self._health_records.get(service)

    def is_core_healthy(self) -> bool:
        """Quick check: are all core services healthy?"""
        for service in CORE_SERVICES:
            record = self._health_records.get(service)
            if record is None or record.health != ServiceHealth.HEALTHY:
                return False
        return True
