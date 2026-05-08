export type EvidenceEventType = "web_sdk" | "telegram" | "safety";

export interface EvaluationEvidenceCardData {
  id: string;
  eventType: EvidenceEventType;
  surface: string;
  risk_level?: string | null;
  human_presence_likelihood?: number | null;
  automation_likelihood?: number | null;
  agentic_control_likelihood?: number | null;
  confidence?: number | null;
  reason_codes?: string[];
  evidence_packet_id?: string | null;
  decision_id?: string | null;
  recommended_action?: string | null;
  timestamp?: string | number | null;
}

export interface EvaluationEvidenceCardNormalizationOptions {
  fallbackId?: string;
  fallbackEventType?: EvidenceEventType;
  fallbackSurface?: string;
}

export const EVALUATION_CARD_ALLOWED_FIELDS = [
  "id",
  "eventType",
  "surface",
  "risk_level",
  "human_presence_likelihood",
  "automation_likelihood",
  "agentic_control_likelihood",
  "confidence",
  "reason_codes",
  "evidence_packet_id",
  "decision_id",
  "recommended_action",
  "timestamp",
] as const;

export const EVALUATION_CARD_UNSAFE_FIELDS = [
  "typed_text",
  "raw_text",
  "key_values",
  "keys",
  "message",
  "caption",
  "content",
  "media_url",
  "file_url",
  "thumbnail",
  "password",
  "card_number",
] as const;

const eventTypes = new Set<EvidenceEventType>(["web_sdk", "telegram", "safety"]);
const safeTokenPattern = /^[A-Za-z0-9][A-Za-z0-9_.:-]*$/;
const unsafeNumericIdentifierPattern = /^(?:\d{3}-?\d{2}-?\d{4}|\d{12,19})$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function safeToken(value: unknown, maxLength = 128): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const normalized = value.trim();
  if (
    !normalized ||
    normalized.length > maxLength ||
    !safeTokenPattern.test(normalized) ||
    unsafeNumericIdentifierPattern.test(normalized)
  ) {
    return undefined;
  }
  return normalized;
}

function safeEventType(value: unknown, fallback: EvidenceEventType): EvidenceEventType {
  return eventTypes.has(value as EvidenceEventType) ? (value as EvidenceEventType) : fallback;
}

function probability(value: unknown): number | undefined {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1) {
    return undefined;
  }
  return value;
}

function timestamp(value: unknown): string | number | undefined {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) {
    return value;
  }
  if (typeof value !== "string") {
    return undefined;
  }
  const normalized = value.trim();
  if (!normalized || normalized.length > 64 || Number.isNaN(new Date(normalized).getTime())) {
    return undefined;
  }
  return normalized;
}

function reasonCodes(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  const codes = Array.from(
    new Set(
      value
        .map((item) => safeToken(item, 80))
        .filter((item): item is string => Boolean(item)),
    ),
  ).slice(0, 16);
  return codes.length ? codes : undefined;
}

function assignIfPresent<T extends keyof EvaluationEvidenceCardData>(
  card: EvaluationEvidenceCardData,
  key: T,
  value: EvaluationEvidenceCardData[T] | undefined,
) {
  if (value !== undefined) {
    card[key] = value;
  }
}

export function normalizeEvaluationEvidenceCard(
  raw: unknown,
  options: EvaluationEvidenceCardNormalizationOptions = {},
): EvaluationEvidenceCardData {
  const source = isRecord(raw) ? raw : {};
  const fallbackEventType = options.fallbackEventType ?? "web_sdk";
  const eventType = safeEventType(source.eventType, fallbackEventType);
  const fallbackId =
    safeToken(options.fallbackId) ??
    safeToken(source.evidence_packet_id) ??
    safeToken(source.decision_id) ??
    `${eventType}-evidence-card`;
  const fallbackSurface = safeToken(options.fallbackSurface, 80);
  const card: EvaluationEvidenceCardData = {
    id: safeToken(source.id) ?? fallbackId,
    eventType,
    surface:
      safeToken(source.surface, 80) ??
      fallbackSurface ??
      (eventType === "web_sdk" ? "web" : eventType),
  };

  assignIfPresent(card, "risk_level", safeToken(source.risk_level, 40));
  assignIfPresent(
    card,
    "human_presence_likelihood",
    probability(source.human_presence_likelihood),
  );
  assignIfPresent(card, "automation_likelihood", probability(source.automation_likelihood));
  assignIfPresent(
    card,
    "agentic_control_likelihood",
    probability(source.agentic_control_likelihood),
  );
  assignIfPresent(card, "confidence", probability(source.confidence));
  assignIfPresent(card, "reason_codes", reasonCodes(source.reason_codes));
  assignIfPresent(card, "evidence_packet_id", safeToken(source.evidence_packet_id));
  assignIfPresent(card, "decision_id", safeToken(source.decision_id));
  assignIfPresent(card, "recommended_action", safeToken(source.recommended_action, 80));
  assignIfPresent(card, "timestamp", timestamp(source.timestamp));

  return card;
}
