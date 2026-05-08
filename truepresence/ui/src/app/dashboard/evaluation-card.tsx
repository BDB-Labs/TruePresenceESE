import {
  Bot,
  Clock,
  Fingerprint,
  Gauge,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";

import {
  normalizeEvaluationEvidenceCard,
  type EvaluationEvidenceCardData,
  type EvidenceEventType,
} from "./evidence-card-normalization";

export type { EvaluationEvidenceCardData, EvidenceEventType } from "./evidence-card-normalization";

interface EvaluationEvidenceCardProps {
  card: EvaluationEvidenceCardData;
}

const eventLabels: Record<EvidenceEventType, string> = {
  web_sdk: "Web SDK evaluation",
  telegram: "Telegram evaluation",
  safety: "Safety escalation",
};

const labelAcronyms = new Map([
  ["ai", "AI"],
  ["api", "API"],
  ["db", "DB"],
  ["dmca", "DMCA"],
  ["id", "ID"],
  ["ip", "IP"],
  ["jwt", "JWT"],
  ["sdk", "SDK"],
  ["url", "URL"],
  ["vnc", "VNC"],
]);

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

export function formatHumanLabel(value: string | null | undefined, fallback = "unknown") {
  if (!value) {
    return fallback;
  }
  const words = value
    .trim()
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .toLowerCase()
    .split(" ")
    .filter(Boolean);
  if (!words.length) {
    return fallback;
  }
  return words
    .map((word, index) => {
      const acronym = labelAcronyms.get(word);
      if (acronym) {
        return acronym;
      }
      return index === 0 ? word[0].toUpperCase() + word.slice(1) : word;
    })
    .join(" ");
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
  const safeCard = normalizeEvaluationEvidenceCard(card);
  const riskLevel = formatHumanLabel(safeCard.risk_level, "Unknown");
  const reasonCodes = safeCard.reason_codes ?? [];
  const showLikelihoods = safeCard.eventType !== "safety";
  const likelihoods = [
    {
      icon: ShieldCheck,
      label: "Human presence",
      value: formatPercent(safeCard.human_presence_likelihood),
    },
    {
      icon: Bot,
      label: "Automation",
      value: formatPercent(safeCard.automation_likelihood),
    },
    {
      icon: Gauge,
      label: "Agentic control",
      value: formatPercent(safeCard.agentic_control_likelihood),
    },
  ];

  return (
    <section className="card flex h-full flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase text-[var(--tp-accent)]">
            {eventLabels[safeCard.eventType]}
          </p>
          <h3 className="mt-1 break-words text-lg font-semibold text-[var(--tp-text-primary)]">
            {formatHumanLabel(safeCard.surface, "Unknown surface")}
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
            {formatPercent(safeCard.confidence)}
          </dd>
        </div>
        <div>
          <dt className="text-[var(--tp-text-muted)]">Recommended action</dt>
          <dd className="mt-1 break-words font-medium text-[var(--tp-text-primary)]">
            {formatHumanLabel(safeCard.recommended_action, "n/a")}
          </dd>
        </div>
        <div>
          <dt className="text-[var(--tp-text-muted)]">Timestamp</dt>
          <dd className="mt-1 flex items-center gap-2 font-medium text-[var(--tp-text-primary)]">
            <Clock className="h-4 w-4 flex-shrink-0 text-[var(--tp-text-muted)]" />
            <span className="break-words">{formatTimestamp(safeCard.timestamp)}</span>
          </dd>
        </div>
      </dl>

      {(safeCard.evidence_packet_id || safeCard.decision_id) && (
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          {safeCard.evidence_packet_id && (
            <div>
              <dt className="flex items-center gap-2 text-[var(--tp-text-muted)]">
                <Fingerprint className="h-4 w-4" />
                Evidence packet
              </dt>
              <dd className="mt-1 break-all font-mono text-xs text-[var(--tp-text-primary)]">
                {safeCard.evidence_packet_id}
              </dd>
            </div>
          )}
          {safeCard.decision_id && (
            <div>
              <dt className="text-[var(--tp-text-muted)]">Decision</dt>
              <dd className="mt-1 break-all font-mono text-xs text-[var(--tp-text-primary)]">
                {safeCard.decision_id}
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
              <span
                className="badge badge-neutral max-w-full break-words"
                key={code}
                title={code}
              >
                {formatHumanLabel(code, "Unknown")}
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
