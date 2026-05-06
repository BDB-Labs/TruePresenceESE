from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


SCORING_MODEL_VERSION = "deterministic_probabilistic_v1"

_FEATURE_SUMMARY_SECTIONS = (
    "typing",
    "challenge",
    "pointer",
    "agentic",
    "environment",
    "session_continuity",
    "external_risk_provider",
    "page_context",
    "metadata",
)


class SdkEvidenceArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_packet_id: str
    session_id: str
    tenant_id: str
    surface: str
    created_at: str
    feature_summaries: dict[str, Any] = Field(default_factory=dict)
    detector_signals: list[dict[str, Any]] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    likelihoods: dict[str, float] = Field(default_factory=dict)
    confidence: float
    recommended_action: str
    scoring_metadata: dict[str, Any] = Field(default_factory=dict)


class SdkEvidenceArtifactStore(Protocol):
    def put(self, artifact: SdkEvidenceArtifact) -> None:
        ...

    def get(self, evidence_packet_id: str) -> SdkEvidenceArtifact | None:
        ...

    def list_recent(
        self,
        *,
        tenant_id: str | None = None,
        limit: int = 10,
    ) -> list[SdkEvidenceArtifact]:
        ...


class InMemorySdkEvidenceArtifactStore:
    """Process-local artifact store for tests and non-DB deployments."""

    def __init__(self) -> None:
        self._artifacts: dict[str, SdkEvidenceArtifact] = {}
        self._lock = RLock()

    def put(self, artifact: SdkEvidenceArtifact) -> None:
        with self._lock:
            self._artifacts[artifact.evidence_packet_id] = artifact

    def get(self, evidence_packet_id: str) -> SdkEvidenceArtifact | None:
        with self._lock:
            return self._artifacts.get(evidence_packet_id)

    def list_recent(
        self,
        *,
        tenant_id: str | None = None,
        limit: int = 10,
    ) -> list[SdkEvidenceArtifact]:
        with self._lock:
            artifacts = list(self._artifacts.values())
        if tenant_id:
            artifacts = [
                artifact
                for artifact in artifacts
                if artifact.tenant_id == tenant_id
            ]
        artifacts.sort(key=lambda artifact: artifact.created_at, reverse=True)
        return artifacts[:limit]

    def clear(self) -> None:
        with self._lock:
            self._artifacts.clear()

    def count(self) -> int:
        with self._lock:
            return len(self._artifacts)


sdk_evidence_store = InMemorySdkEvidenceArtifactStore()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_dump(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        return {key: child for key, child in value.items() if child is not None}
    return {}


def _feature_summaries(packet: Any) -> dict[str, Any]:
    packet_dict = _model_dump(packet)
    return {
        section: packet_dict[section]
        for section in _FEATURE_SUMMARY_SECTIONS
        if packet_dict.get(section) not in (None, {}, [])
    }


def build_sdk_evidence_artifact(
    *,
    packet: Any,
    response: Any,
    signals: list[Any],
    enforcement_mode: str,
) -> SdkEvidenceArtifact:
    detector_signals = [
        signal.model_dump(mode="json") if hasattr(signal, "model_dump") else dict(signal)
        for signal in signals
    ]
    feature_packet = _model_dump(packet)

    return SdkEvidenceArtifact(
        evidence_packet_id=response.evidence_packet_id,
        session_id=feature_packet.get("session_id") or "",
        tenant_id=feature_packet.get("tenant_id") or "default",
        surface=feature_packet.get("surface") or "web",
        created_at=_utc_now_iso(),
        feature_summaries=_feature_summaries(packet),
        detector_signals=detector_signals,
        reason_codes=list(response.reason_codes),
        likelihoods={
            "human_presence_likelihood": response.human_presence_likelihood,
            "automation_likelihood": response.automation_likelihood,
            "agentic_control_likelihood": response.agentic_control_likelihood,
        },
        confidence=response.confidence,
        recommended_action=response.recommended_action,
        scoring_metadata={
            "model": SCORING_MODEL_VERSION,
            "aggregation": "category_aware_product_of_complements",
            "enforcement_mode": enforcement_mode,
            "detector_signal_count": len(detector_signals),
            "reason_code_count": len(response.reason_codes),
        },
    )


def persist_sdk_evidence_artifact(
    *,
    packet: Any,
    response: Any,
    signals: list[Any],
    enforcement_mode: str,
    store: SdkEvidenceArtifactStore = sdk_evidence_store,
) -> SdkEvidenceArtifact:
    artifact = build_sdk_evidence_artifact(
        packet=packet,
        response=response,
        signals=signals,
        enforcement_mode=enforcement_mode,
    )
    store.put(artifact)
    return artifact
