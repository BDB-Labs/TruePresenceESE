import {
  Bot,
  Clock,
  Fingerprint,
  Gauge,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";

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

interface EvaluationEvidenceCardProps {
  card: EvaluationEvidenceCardData;
}

const eventLabels: Record<EvidenceEventType, string> = {
  web_sdk: "Web SDK evaluation",
  telegram: "Telegram evaluation",
  safety: "Safety escalation",
};

function formatPercent(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "n/a";
  }
  return `${Math.round(value * 100)}%`;
}

function formatTimestamp(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  const normalized =
    typeof value === "number" && value < 10_000_000_000 ? value * 1000 : value;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString();
}

function normalizeLabel(value: string | null | undefined, fallback = "unknown") {
  if (!value) {
    return fallback;
  }
  return value.replaceAll("_", " ");
}

function riskBadgeClass(riskLevel: string) {
  const normalized = riskLevel.toLowerCase();
  if (normalized === "critical" || normalized === "high") {
    return "badge badge-danger";
  }
  if (normalized === "medium") {
    return "badge badge-warning";
  }
  return "badge badge-success";
}

export function EvaluationEvidenceCard({ card }: EvaluationEvidenceCardProps) {
  const riskLevel = normalizeLabel(card.risk_level, "unknown");
  const reasonCodes = card.reason_codes ?? [];
  const showLikelihoods = card.eventType !== "safety";
  const likelihoods = [
    {
      icon: ShieldCheck,
      label: "Human presence",
      value: formatPercent(card.human_presence_likelihood),
    },
    {
      icon: Bot,
      label: "Automation",
      value: formatPercent(card.automation_likelihood),
    },
    {
      icon: Gauge,
      label: "Agentic control",
      value: formatPercent(card.agentic_control_likelihood),
    },
  ];

  return (
    <section className="card flex h-full flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase text-[var(--tp-accent)]">
            {eventLabels[card.eventType]}
          </p>
          <h3 className="mt-1 break-words text-lg font-semibold text-[var(--tp-text-primary)]">
            {normalizeLabel(card.surface, "unknown surface")}
          </h3>
        </div>
        <span className={riskBadgeClass(riskLevel)}>{riskLevel}</span>
      </div>

      {showLikelihoods && (
        <div className="grid gap-3 sm:grid-cols-3">
          {likelihoods.map((item) => (
            <div
              className="rounded-md border border-[var(--tp-border)] bg-[var(--tp-bg-secondary)] p-3"
              key={item.label}
            >
              <div className="flex items-center gap-2 text-[var(--tp-text-muted)]">
                <item.icon className="h-4 w-4 flex-shrink-0" />
                <span className="text-xs">{item.label}</span>
              </div>
              <p className="mt-2 text-lg font-semibold text-[var(--tp-text-primary)]">
                {item.value}
              </p>
            </div>
          ))}
        </div>
      )}

      <dl className="grid gap-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-[var(--tp-text-muted)]">Confidence</dt>
          <dd className="mt-1 font-medium text-[var(--tp-text-primary)]">
            {formatPercent(card.confidence)}
          </dd>
        </div>
        <div>
          <dt className="text-[var(--tp-text-muted)]">Recommended action</dt>
          <dd className="mt-1 break-words font-medium text-[var(--tp-text-primary)]">
            {normalizeLabel(card.recommended_action, "n/a")}
          </dd>
        </div>
        <div>
          <dt className="text-[var(--tp-text-muted)]">Timestamp</dt>
          <dd className="mt-1 flex items-center gap-2 font-medium text-[var(--tp-text-primary)]">
            <Clock className="h-4 w-4 flex-shrink-0 text-[var(--tp-text-muted)]" />
            <span className="break-words">{formatTimestamp(card.timestamp)}</span>
          </dd>
        </div>
      </dl>

      {(card.evidence_packet_id || card.decision_id) && (
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          {card.evidence_packet_id && (
            <div>
              <dt className="flex items-center gap-2 text-[var(--tp-text-muted)]">
                <Fingerprint className="h-4 w-4" />
                Evidence packet
              </dt>
              <dd className="mt-1 break-all font-mono text-xs text-[var(--tp-text-primary)]">
                {card.evidence_packet_id}
              </dd>
            </div>
          )}
          {card.decision_id && (
            <div>
              <dt className="text-[var(--tp-text-muted)]">Decision</dt>
              <dd className="mt-1 break-all font-mono text-xs text-[var(--tp-text-primary)]">
                {card.decision_id}
              </dd>
            </div>
          )}
        </dl>
      )}

      <div className="mt-auto">
        <div className="flex items-center gap-2 text-sm text-[var(--tp-text-muted)]">
          <ShieldAlert className="h-4 w-4 flex-shrink-0" />
          <span>Reason codes</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {reasonCodes.length ? (
            reasonCodes.map((code) => (
              <span className="badge badge-neutral max-w-full break-words" key={code}>
                {code}
              </span>
            ))
          ) : (
            <span className="text-sm text-[var(--tp-text-secondary)]">None</span>
          )}
        </div>
      </div>
    </section>
  );
}
