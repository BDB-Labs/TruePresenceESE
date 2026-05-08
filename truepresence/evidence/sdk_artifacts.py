from __future__ import annotations

import json
import logging
import os
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field
from psycopg2.extras import Json


SCORING_MODEL_VERSION = "deterministic_probabilistic_v1"
SDK_EVIDENCE_RETENTION_DAYS_ENV = "TRUEPRESENCE_SDK_EVIDENCE_RETENTION_DAYS"
DEFAULT_SDK_EVIDENCE_RETENTION_DAYS = 30

logger = logging.getLogger(__name__)

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

_FORBIDDEN_ARTIFACT_KEY_NAMES = frozenset(
    {
        "caption",
        "card_number",
        "clientx",
        "file_id",
        "file_url",
        "key_values",
        "keys",
        "media_url",
        "message_text",
        "password",
        "raw_input",
        "raw_pointer_trail",
        "raw_text",
        "raw_value",
        "ssn",
        "thumbnail",
        "typed_text",
    }
)

_FORBIDDEN_ARTIFACT_VALUE_FRAGMENTS = frozenset(
    {
        "card_number",
        "file_url",
        "key_values",
        "media_url",
        "message_text",
        "private message",
        "raw pointer trail",
        "raw_text",
        "thumbnail",
        "typed_text",
    }
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


def _normalize_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_")


def _scan_for_raw_content(value: Any, path: str = "") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = _normalize_key(key)
            child_path = f"{path}.{key}" if path else str(key)
            if normalized in _FORBIDDEN_ARTIFACT_KEY_NAMES:
                return child_path
            violation = _scan_for_raw_content(child, child_path)
            if violation:
                return violation
        return None

    if isinstance(value, list):
        for index, child in enumerate(value):
            violation = _scan_for_raw_content(child, f"{path}[{index}]")
            if violation:
                return violation
        return None

    if isinstance(value, str):
        normalized = value.lower().replace("-", "_")
        if any(fragment in normalized for fragment in _FORBIDDEN_ARTIFACT_VALUE_FRAGMENTS):
            return path or "<value>"

    return None


def ensure_sdk_artifact_minimized(artifact: SdkEvidenceArtifact) -> None:
    """Reject evidence artifacts that contain raw-content markers."""
    violation = _scan_for_raw_content(artifact.model_dump(mode="json"))
    if violation:
        raise ValueError(f"SDK evidence artifact contains disallowed raw-content field: {violation}")


class InMemorySdkEvidenceArtifactStore:
    """Process-local artifact store for tests and non-DB deployments."""

    def __init__(self) -> None:
        self._artifacts: dict[str, SdkEvidenceArtifact] = {}
        self._lock = RLock()

    def put(self, artifact: SdkEvidenceArtifact) -> None:
        ensure_sdk_artifact_minimized(artifact)
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


SqlDialect = Literal["postgres", "sqlite"]


class SqlSdkEvidenceArtifactStore:
    """DB-backed SDK evidence artifact store.

    Production uses PostgreSQL via ``truepresence.db.get_db``. Tests can inject
    a SQLite connection context to prove durable behavior across store
    reinitialization without requiring production infrastructure.
    """

    def __init__(
        self,
        connection_context_factory: Callable[[], AbstractContextManager[Any]],
        *,
        dialect: SqlDialect = "postgres",
    ) -> None:
        self._connection_context_factory = connection_context_factory
        self._dialect = dialect

    def initialize_schema(self) -> None:
        if self._dialect == "sqlite":
            schema = """
            CREATE TABLE IF NOT EXISTS sdk_evidence_artifacts (
                evidence_packet_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                session_id TEXT NOT NULL,
                surface TEXT NOT NULL DEFAULT 'web',
                created_at TEXT NOT NULL,
                feature_summaries TEXT NOT NULL,
                detector_signals TEXT NOT NULL,
                reason_codes TEXT NOT NULL,
                likelihoods TEXT NOT NULL,
                confidence REAL NOT NULL,
                recommended_action TEXT NOT NULL,
                scoring_metadata TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sdk_evidence_tenant_created
                ON sdk_evidence_artifacts (tenant_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_sdk_evidence_session
                ON sdk_evidence_artifacts (session_id);
            """
        else:
            schema = """
            CREATE TABLE IF NOT EXISTS sdk_evidence_artifacts (
                evidence_packet_id VARCHAR(255) PRIMARY KEY,
                tenant_id VARCHAR(100) NOT NULL DEFAULT 'default',
                session_id VARCHAR(255) NOT NULL,
                surface VARCHAR(100) NOT NULL DEFAULT 'web',
                created_at TIMESTAMPTZ NOT NULL,
                feature_summaries JSONB NOT NULL DEFAULT '{}'::jsonb,
                detector_signals JSONB NOT NULL DEFAULT '[]'::jsonb,
                reason_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
                likelihoods JSONB NOT NULL DEFAULT '{}'::jsonb,
                confidence DOUBLE PRECISION NOT NULL,
                recommended_action VARCHAR(100) NOT NULL,
                scoring_metadata JSONB NOT NULL DEFAULT '{}'::jsonb
            );
            CREATE INDEX IF NOT EXISTS idx_sdk_evidence_tenant_created
                ON sdk_evidence_artifacts (tenant_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_sdk_evidence_session
                ON sdk_evidence_artifacts (session_id);
            """
        with self._connection_context_factory() as conn:
            if self._dialect == "sqlite":
                conn.executescript(schema)
            else:
                with conn.cursor() as cur:
                    cur.execute(schema)

    def put(self, artifact: SdkEvidenceArtifact) -> None:
        ensure_sdk_artifact_minimized(artifact)
        params = self._artifact_params(artifact)
        placeholder = "?" if self._dialect == "sqlite" else "%s"
        placeholders = ", ".join([placeholder] * len(params))
        if self._dialect == "sqlite":
            update_clause = """
                tenant_id = excluded.tenant_id,
                session_id = excluded.session_id,
                surface = excluded.surface,
                created_at = excluded.created_at,
                feature_summaries = excluded.feature_summaries,
                detector_signals = excluded.detector_signals,
                reason_codes = excluded.reason_codes,
                likelihoods = excluded.likelihoods,
                confidence = excluded.confidence,
                recommended_action = excluded.recommended_action,
                scoring_metadata = excluded.scoring_metadata
            """
        else:
            update_clause = """
                tenant_id = EXCLUDED.tenant_id,
                session_id = EXCLUDED.session_id,
                surface = EXCLUDED.surface,
                created_at = EXCLUDED.created_at,
                feature_summaries = EXCLUDED.feature_summaries,
                detector_signals = EXCLUDED.detector_signals,
                reason_codes = EXCLUDED.reason_codes,
                likelihoods = EXCLUDED.likelihoods,
                confidence = EXCLUDED.confidence,
                recommended_action = EXCLUDED.recommended_action,
                scoring_metadata = EXCLUDED.scoring_metadata
            """
        sql = f"""
            INSERT INTO sdk_evidence_artifacts (
                evidence_packet_id,
                tenant_id,
                session_id,
                surface,
                created_at,
                feature_summaries,
                detector_signals,
                reason_codes,
                likelihoods,
                confidence,
                recommended_action,
                scoring_metadata
            )
            VALUES ({placeholders})
            ON CONFLICT (evidence_packet_id) DO UPDATE SET {update_clause}
        """
        with self._connection_context_factory() as conn:
            if self._dialect == "sqlite":
                conn.execute(sql, params)
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, params)

    def get(self, evidence_packet_id: str) -> SdkEvidenceArtifact | None:
        placeholder = "?" if self._dialect == "sqlite" else "%s"
        sql = f"""
            SELECT
                evidence_packet_id,
                tenant_id,
                session_id,
                surface,
                created_at,
                feature_summaries,
                detector_signals,
                reason_codes,
                likelihoods,
                confidence,
                recommended_action,
                scoring_metadata
            FROM sdk_evidence_artifacts
            WHERE evidence_packet_id = {placeholder}
        """
        with self._connection_context_factory() as conn:
            if self._dialect == "sqlite":
                row = conn.execute(sql, (evidence_packet_id,)).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (evidence_packet_id,))
                    row = cur.fetchone()
        return self._artifact_from_row(row) if row else None

    def list_recent(
        self,
        *,
        tenant_id: str | None = None,
        limit: int = 10,
    ) -> list[SdkEvidenceArtifact]:
        placeholder = "?" if self._dialect == "sqlite" else "%s"
        params: list[Any] = []
        where = ""
        if tenant_id:
            where = f"WHERE tenant_id = {placeholder}"
            params.append(tenant_id)
        params.append(max(1, int(limit)))
        sql = f"""
            SELECT
                evidence_packet_id,
                tenant_id,
                session_id,
                surface,
                created_at,
                feature_summaries,
                detector_signals,
                reason_codes,
                likelihoods,
                confidence,
                recommended_action,
                scoring_metadata
            FROM sdk_evidence_artifacts
            {where}
            ORDER BY created_at DESC
            LIMIT {placeholder}
        """
        with self._connection_context_factory() as conn:
            if self._dialect == "sqlite":
                rows = conn.execute(sql, tuple(params)).fetchall()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, tuple(params))
                    rows = cur.fetchall()
        return [artifact for row in rows if (artifact := self._artifact_from_row(row)) is not None]

    def _artifact_params(self, artifact: SdkEvidenceArtifact) -> tuple[Any, ...]:
        return (
            artifact.evidence_packet_id,
            artifact.tenant_id,
            artifact.session_id,
            artifact.surface,
            artifact.created_at,
            self._json_param(artifact.feature_summaries),
            self._json_param(artifact.detector_signals),
            self._json_param(artifact.reason_codes),
            self._json_param(artifact.likelihoods),
            artifact.confidence,
            artifact.recommended_action,
            self._json_param(artifact.scoring_metadata),
        )

    def _json_param(self, value: Any) -> Any:
        if self._dialect == "sqlite":
            return json.dumps(value, sort_keys=True)
        return Json(value)

    def _artifact_from_row(self, row: Any) -> SdkEvidenceArtifact | None:
        if row is None:
            return None
        created_at = self._row_value(row, "created_at")
        if isinstance(created_at, datetime):
            created_at = created_at.astimezone(timezone.utc).isoformat()
        artifact = SdkEvidenceArtifact(
            evidence_packet_id=self._row_value(row, "evidence_packet_id"),
            tenant_id=self._row_value(row, "tenant_id"),
            session_id=self._row_value(row, "session_id"),
            surface=self._row_value(row, "surface"),
            created_at=str(created_at),
            feature_summaries=self._json_row_value(row, "feature_summaries", {}),
            detector_signals=self._json_row_value(row, "detector_signals", []),
            reason_codes=self._json_row_value(row, "reason_codes", []),
            likelihoods=self._json_row_value(row, "likelihoods", {}),
            confidence=float(self._row_value(row, "confidence")),
            recommended_action=self._row_value(row, "recommended_action"),
            scoring_metadata=self._json_row_value(row, "scoring_metadata", {}),
        )
        ensure_sdk_artifact_minimized(artifact)
        return artifact

    @staticmethod
    def _row_value(row: Any, key: str) -> Any:
        return row[key]

    @staticmethod
    def _json_row_value(row: Any, key: str, fallback: Any) -> Any:
        value = row[key]
        if value is None:
            return fallback
        if isinstance(value, str):
            return json.loads(value)
        return value


class PostgresSdkEvidenceArtifactStore(SqlSdkEvidenceArtifactStore):
    """PostgreSQL-backed SDK evidence artifact store for production/runtime."""

    def __init__(self) -> None:
        from truepresence.db import get_db

        super().__init__(get_db, dialect="postgres")


def retention_days() -> int:
    try:
        return max(1, int(os.environ.get(SDK_EVIDENCE_RETENTION_DAYS_ENV, "")))
    except ValueError:
        return DEFAULT_SDK_EVIDENCE_RETENTION_DAYS


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _sdk_evidence_store_mode() -> str:
    return os.environ.get("TRUEPRESENCE_SDK_EVIDENCE_STORE", "auto").strip().lower()


def _is_explicit_production_environment() -> bool:
    mode = (
        os.environ.get("TRUEPRESENCE_ENV")
        or os.environ.get("APP_ENV")
        or os.environ.get("ENVIRONMENT")
        or ""
    ).strip().lower()
    return mode in {"prod", "production"}


def default_sdk_evidence_store() -> SdkEvidenceArtifactStore:
    mode = _sdk_evidence_store_mode()
    if mode in {"memory", "in_memory", "test"}:
        return InMemorySdkEvidenceArtifactStore()
    if mode in {"postgres", "db", "database"}:
        store = PostgresSdkEvidenceArtifactStore()
        if _truthy_env("TRUEPRESENCE_SDK_EVIDENCE_AUTO_INIT"):
            store.initialize_schema()
        return store

    try:
        from truepresence.db import _database_configured
        from truepresence.runtime.wiring import is_development_environment, is_test_environment

        database_configured = _database_configured()
        if database_configured and not (is_test_environment() or is_development_environment()):
            return PostgresSdkEvidenceArtifactStore()
        if _is_explicit_production_environment() and not database_configured:
            raise RuntimeError(
                "Durable SDK evidence storage requires database configuration in production. "
                "Set DATABASE_URL or TRUEPRESENCE_SDK_EVIDENCE_STORE=memory only for local/test use."
            )
    except Exception as exc:
        if _is_explicit_production_environment():
            raise
        logger.warning("SDK evidence DB store unavailable; falling back to in-memory store: %s", exc)

    return InMemorySdkEvidenceArtifactStore()


sdk_evidence_store = default_sdk_evidence_store()


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
    store: SdkEvidenceArtifactStore | None = None,
) -> SdkEvidenceArtifact:
    artifact = build_sdk_evidence_artifact(
        packet=packet,
        response=response,
        signals=signals,
        enforcement_mode=enforcement_mode,
    )
    (store or sdk_evidence_store).put(artifact)
    return artifact
