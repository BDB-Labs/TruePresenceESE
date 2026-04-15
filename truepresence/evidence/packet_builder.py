from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from truepresence.evidence.packet import EvidencePacket


TIMING_KEYS = {
    "response_time_ms",
    "response_time",
    "relay_risk",
    "constant_latency_pattern",
    "temporal_drift",
    "message_velocity",
    "avg_interval",
    "timing_consistency",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return dict(value)
    return {"value": value}


def _merge_feature_sources(event: Dict[str, Any]) -> Dict[str, Any]:
    merged = {}
    merged.update(_to_dict(event.get("features")))
    merged.update(_to_dict(event.get("signals")))
    return merged


def _derive_timing_features(event: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    payload = _to_dict(event.get("payload"))
    timing_features = dict(_to_dict(context.get("timing_features")))

    merged = _merge_feature_sources(event)
    for key in TIMING_KEYS:
        if key in merged and key not in timing_features:
            timing_features[key] = merged[key]

    response_time_ms = payload.get("response_time_ms") or payload.get("response_time")
    if response_time_ms is not None and "constant_latency_pattern" not in timing_features:
        response_seconds = float(response_time_ms) / 1000 if float(response_time_ms) > 10 else float(response_time_ms)
        timing_features["constant_latency_pattern"] = response_seconds < 0.3

    if "relay_risk" not in timing_features and merged.get("content_similarity") is not None:
        timing_features["relay_risk"] = float(merged.get("content_similarity", 0.0))

    return timing_features


def _derive_behavioral_features(event: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    behavioral = dict(_to_dict(context.get("behavioral_features")))
    merged = _merge_feature_sources(event)

    for key, value in merged.items():
        behavioral.setdefault(key, value)

    if "automation_pattern" not in behavioral:
        behavioral["automation_pattern"] = bool(
            merged.get("ai_mediation", 0) >= 0.7
            or merged.get("message_velocity", 0) >= 50
            or merged.get("content_similarity", 0) >= 0.9
        )

    if "known_automation_fingerprint" not in behavioral:
        behavioral["known_automation_fingerprint"] = bool(context.get("known_automation_fingerprint", False))

    return behavioral


def _derive_default_signals(event: Dict[str, Any], challenge_data: Dict[str, Any]) -> Dict[str, Any]:
    context = _to_dict(event.get("context"))
    payload = _to_dict(event.get("payload"))
    threat_analysis = _to_dict(event.get("threat_analysis"))

    verified_challenges = 1 if challenge_data.get("status") == "passed" else 0
    direct_interaction = 0.2
    if event.get("event_type") in {"cursor_move", "key_timing", "click"}:
        direct_interaction = 0.8
    elif event.get("event_type") in {"message", "member_join", "member_update"}:
        direct_interaction = 0.45

    if context.get("is_bot"):
        direct_interaction = 0.05

    liveness = min(1.0, direct_interaction + (0.2 * verified_challenges))

    pasted = payload.get("pasted") or payload.get("paste") or payload.get("is_paste")
    ai_mediation = 0.75 if pasted else 0.1
    if event.get("event_type") == "clipboard":
        ai_mediation = max(ai_mediation, 0.6)

    relay_risk = 0.1
    response_time_ms = payload.get("response_time_ms") or payload.get("response_time")
    if response_time_ms is not None:
        response_seconds = float(response_time_ms) / 1000 if float(response_time_ms) > 10 else float(response_time_ms)
        if response_seconds < 0.3:
            relay_risk = 0.9
        elif response_seconds > 8.0:
            relay_risk = 0.7
        else:
            relay_risk = 0.3

    relay_risk = max(relay_risk, float(_merge_feature_sources(event).get("content_similarity", 0.0) or 0.0))

    deterministic_policy_violation = 1.0 if threat_analysis.get("threats_detected") else 0.0

    return {
        "liveness": liveness,
        "ai_mediation": ai_mediation,
        "relay_risk": relay_risk,
        "deterministic_policy_violation": deterministic_policy_violation,
    }


def _derive_challenge_data(event: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    challenge_data = dict(_to_dict(context.get("challenge_data")))
    raw = event.get("challenge_result") or event.get("challenge_response")
    if raw:
        challenge_data.update(_to_dict(raw))

    if "status" not in challenge_data:
        if challenge_data.get("verified") is True:
            challenge_data["status"] = "passed"
        elif challenge_data.get("verified") is False:
            challenge_data["status"] = "failed"
        elif challenge_data:
            challenge_data["status"] = "submitted"

    return challenge_data


def _derive_identity_refs(session_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
    identity_refs = dict(_to_dict(context.get("identity_refs")))
    identity_refs.setdefault("session_id", session_id)
    return identity_refs


def _derive_policy_context(event: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    policy_context = dict(_to_dict(context.get("policy_context")))
    if event.get("event_type") == "high_value_transaction":
        policy_context.setdefault("high_value_flow", True)
    return policy_context


def _derive_risk_context(event: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    risk_context = dict(_to_dict(context.get("risk_context")))
    if "event_type" in event and "event_type" not in risk_context:
        risk_context["event_type"] = event["event_type"]

    threat_analysis = _to_dict(event.get("threat_analysis"))
    if threat_analysis.get("threats_detected"):
        risk_context.setdefault("threats_detected", list(threat_analysis["threats_detected"]))

    return risk_context


def build_evidence_packet(
    *,
    surface: str,
    session_id: str,
    tenant_id: str,
    event: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> EvidencePacket:
    ctx = dict(context or {})
    raw_events = [dict(event)]

    timing_features = _derive_timing_features(event, ctx)
    behavioral_features = _derive_behavioral_features(event, ctx)
    challenge_data = _derive_challenge_data(event, ctx)
    default_signals = _derive_default_signals(event, challenge_data)
    timing_features.setdefault("relay_risk", default_signals["relay_risk"])
    behavioral_features.setdefault("liveness", default_signals["liveness"])
    behavioral_features.setdefault("ai_mediation", default_signals["ai_mediation"])
    behavioral_features.setdefault("deterministic_policy_violation", default_signals["deterministic_policy_violation"])
    identity_refs = _derive_identity_refs(session_id, ctx)
    session_history = list(ctx.get("session_history", []))
    policy_context = _derive_policy_context(event, ctx)
    risk_context = _derive_risk_context(event, ctx)

    return EvidencePacket(
        packet_id=str(uuid.uuid4()),
        session_id=session_id,
        tenant_id=tenant_id,
        surface=surface,
        actor_id=ctx.get("actor_id"),
        received_at=_utc_now_iso(),
        event_window_start=ctx.get("event_window_start"),
        event_window_end=ctx.get("event_window_end"),
        raw_events=raw_events,
        challenge_data=challenge_data,
        timing_features=timing_features,
        behavioral_features=behavioral_features,
        identity_refs=identity_refs,
        session_history=session_history,
        policy_context=policy_context,
        risk_context=risk_context,
        provenance={
            "normalizer_version": "1.0",
            "source_surface": surface,
            "invalid_attestation": bool(ctx.get("invalid_attestation") or _to_dict(event.get("context")).get("invalid_attestation")),
        },
        session_context=_to_dict(ctx.get("session")),
        metadata={
            "event_type": event.get("event_type"),
            "context": _to_dict(event.get("context")),
        },
    )


class EvidencePacketBuilder:
    """Compatibility wrapper for the canonical V1 packet builder."""

    def build(
        self,
        *,
        session_id: str,
        surface: str,
        event: Dict[str, Any] | Any,
        session: Dict[str, Any] | Any | None = None,
        challenge_results: list[Dict[str, Any]] | None = None,
        session_history: list[Dict[str, Any]] | None = None,
        identity_refs: Dict[str, Any] | None = None,
        tenant_id: str | None = None,
        context: Dict[str, Any] | None = None,
    ) -> EvidencePacket:
        event_dict = _to_dict(event)
        session_dict = _to_dict(session)
        ctx = dict(context or {})

        ctx.setdefault("actor_id", session_dict.get("actor_id") or session_dict.get("user_id"))
        ctx.setdefault("session_history", list(session_history or ctx.get("session_history", [])))
        ctx.setdefault("identity_refs", dict(identity_refs or ctx.get("identity_refs", {})))
        ctx.setdefault("policy_context", dict(ctx.get("policy_context", {})))
        ctx.setdefault("risk_context", dict(ctx.get("risk_context", {})))

        if challenge_results and "challenge_data" not in ctx:
            latest = dict(challenge_results[-1])
            if latest.get("verified") is True:
                latest.setdefault("status", "passed")
            elif latest.get("verified") is False:
                latest.setdefault("status", "failed")
            ctx["challenge_data"] = latest

        resolved_tenant_id = tenant_id or session_dict.get("tenant_id") or ctx.get("tenant_id") or "default"
        return build_evidence_packet(
            surface=surface,
            session_id=session_id,
            tenant_id=resolved_tenant_id,
            event=event_dict,
            context=ctx,
        )
