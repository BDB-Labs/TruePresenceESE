"use client";

import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Eye,
  Play,
  RefreshCw,
  ShieldCheck,
  X,
  Users,
} from "lucide-react";

import {
  EvaluationEvidenceCard,
  formatHumanLabel,
  type EvaluationEvidenceCardData,
} from "./evaluation-card";

interface TelegramStatus {
  status?: string;
  tenant_id?: string;
  protected_groups?: number;
  active_sessions?: number;
  pending_reviews?: number;
  orchestrator_type?: string;
}

interface ReviewItem {
  review_id?: string;
  tenant_id?: string;
  status?: string;
  created_at?: string;
  resolved_at?: string;
  admin_decision?: string;
  admin_notes?: string;
  risk_factors?: string[];
  threat_categories?: string[];
  user_info?: Record<string, unknown>;
  chat_info?: Record<string, unknown>;
  telegram_refs?: Record<string, unknown>;
  action?: {
    action?: string;
    confidence?: number;
    enforcement_mode?: string;
    safety_evidence_card?: Record<string, unknown>;
    safety_escalation?: boolean;
  };
  evaluation?: Record<string, unknown>;
  evidence_card?: Record<string, unknown>;
}

interface ReviewPayload {
  count?: number;
  pending_reviews?: ReviewItem[];
}

interface EvidenceCardsPayload {
  count?: number;
  evidence_cards?: Omit<EvaluationEvidenceCardData, "id" | "eventType">[];
}

interface DashboardState {
  telegramStatus: TelegramStatus | null;
  reviews: ReviewPayload | null;
  sdkEvidence: EvidenceCardsPayload | null;
}

const emptyState: DashboardState = {
  telegramStatus: null,
  reviews: null,
  sdkEvidence: null,
};

const safetyReviewActions = new Set([
  "quarantine_message",
  "restrict_sender",
  "admin_review",
  "mandatory_safety_escalation",
]);

const reviewResolutionDecisions = ["allow", "warn", "kick", "ban", "delete"] as const;

type ReviewResolutionDecision = (typeof reviewResolutionDecisions)[number];
type ReviewActionPending = "details" | "resolve" | "execute" | "";

async function readJson<T>(response: Response): Promise<T> {
  const payload = await response.json();
  if (!response.ok) {
    const message =
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : "Request failed";
    throw new Error(message);
  }
  return payload as T;
}

function formatCount(value: number | undefined) {
  return value?.toLocaleString() ?? "0";
}

function formatConfidence(value: number | undefined) {
  if (value === undefined) {
    return "n/a";
  }
  return `${Math.round(value * 100)}%`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function recordValue(
  value: Record<string, unknown> | undefined,
  key: string,
): Record<string, unknown> | undefined {
  const child = value?.[key];
  return isRecord(child) ? child : undefined;
}

function stringValue(
  value: Record<string, unknown> | undefined,
  key: string,
): string | undefined {
  const child = value?.[key];
  return typeof child === "string" && child ? child : undefined;
}

function numberValue(
  value: Record<string, unknown> | undefined,
  key: string,
): number | undefined {
  const child = value?.[key];
  return typeof child === "number" && Number.isFinite(child) ? child : undefined;
}

function timestampValue(
  value: Record<string, unknown> | undefined,
  key: string,
): string | number | undefined {
  const child = value?.[key];
  if (typeof child === "string" && child) {
    return child;
  }
  if (typeof child === "number" && Number.isFinite(child)) {
    return child;
  }
  return undefined;
}

function displayValue(value: unknown): string | undefined {
  if (typeof value === "string" && value) {
    return value;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  return undefined;
}

function primitiveRecordValue(
  value: Record<string, unknown> | undefined,
  key: string,
): string | undefined {
  return displayValue(value?.[key]);
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string" && item.length > 0);
}

function uniqueStrings(...values: (string[] | undefined)[]) {
  return Array.from(new Set(values.flatMap((items) => items ?? [])));
}

function reviewReasonCodes(
  review: ReviewItem,
  evidenceCard: Record<string, unknown> | undefined,
  final: Record<string, unknown> | undefined,
  action: Record<string, unknown> | undefined,
) {
  return uniqueStrings(
    stringList(evidenceCard?.reason_codes),
    stringList(final?.reason_codes),
    stringList(action?.reason_codes),
    review.risk_factors,
    review.threat_categories,
  );
}

function reviewSignalLabel(review: ReviewItem) {
  const signals = uniqueStrings(review.risk_factors, review.threat_categories).slice(0, 3);
  if (!signals.length) {
    return "None";
  }
  return signals.map((signal) => formatHumanLabel(signal, "Unknown")).join(", ");
}

function normalizedReviewDecision(value: string | undefined): ReviewResolutionDecision {
  return reviewResolutionDecisions.includes(value as ReviewResolutionDecision)
    ? (value as ReviewResolutionDecision)
    : "allow";
}

function shouldExecuteReviewDecision(review: ReviewItem | null) {
  const decision = normalizedReviewDecision(review?.admin_decision);
  return Boolean(review?.status === "resolved" && decision !== "allow");
}

function reviewDetailItems(review: ReviewItem) {
  const action = isRecord(review.action) ? review.action : undefined;
  const evidenceCard = isRecord(review.evidence_card) ? review.evidence_card : undefined;
  const risk = recordValue(evidenceCard, "risk");
  const timestamps = recordValue(evidenceCard, "timestamps");
  const actorRefs = recordValue(evidenceCard, "actor_refs");
  const userInfo = isRecord(review.user_info) ? review.user_info : undefined;
  const chatInfo = isRecord(review.chat_info) ? review.chat_info : undefined;
  const telegramRefs = isRecord(review.telegram_refs) ? review.telegram_refs : undefined;

  return [
    { label: "Review ID", value: review.review_id || "Unassigned" },
    { label: "Tenant", value: review.tenant_id || "default" },
    { label: "Status", value: formatHumanLabel(review.status, "Pending") },
    {
      label: "Recommended action",
      value: formatHumanLabel(action?.action as string | undefined, "Review"),
    },
    {
      label: "Admin decision",
      value: review.admin_decision ? formatHumanLabel(review.admin_decision, "Unknown") : "Not set",
    },
    { label: "Confidence", value: formatConfidence(action?.confidence as number | undefined) },
    {
      label: "Risk",
      value:
        formatHumanLabel(stringValue(evidenceCard, "risk_label"), "") ||
        formatHumanLabel(stringValue(risk, "label") || stringValue(risk, "level"), "Unknown"),
    },
    { label: "Created", value: review.created_at || "n/a" },
    { label: "Resolved", value: review.resolved_at || "Not resolved" },
    {
      label: "Event timestamp",
      value:
        displayValue(timestamps?.event_timestamp) ||
        displayValue(timestamps?.created_at) ||
        "n/a",
    },
    {
      label: "Chat ID",
      value:
        primitiveRecordValue(telegramRefs, "chat_id") ||
        primitiveRecordValue(chatInfo, "id") ||
        primitiveRecordValue(actorRefs, "group_id") ||
        primitiveRecordValue(evidenceCard, "chat_id") ||
        "n/a",
    },
    {
      label: "Message ID",
      value:
        primitiveRecordValue(telegramRefs, "message_id") ||
        primitiveRecordValue(evidenceCard, "message_id") ||
        "n/a",
    },
    {
      label: "Sender ID",
      value:
        primitiveRecordValue(telegramRefs, "sender_id") ||
        primitiveRecordValue(userInfo, "id") ||
        primitiveRecordValue(actorRefs, "user_id") ||
        primitiveRecordValue(evidenceCard, "sender_id") ||
        "n/a",
    },
    {
      label: "Media present",
      value: primitiveRecordValue(evidenceCard, "media_present") || "n/a",
    },
    {
      label: "Evidence ID",
      value: primitiveRecordValue(evidenceCard, "evidence_id") || "n/a",
    },
  ];
}

function isSafetyReview(
  review: ReviewItem,
  evidenceCard: Record<string, unknown> | undefined,
  action: Record<string, unknown> | undefined,
) {
  const recommendedAction =
    stringValue(evidenceCard, "recommended_action") || stringValue(action, "action");
  return Boolean(
    action?.safety_escalation ||
      action?.safety_evidence_card ||
      stringValue(evidenceCard, "risk_label") ||
      (recommendedAction && safetyReviewActions.has(recommendedAction)),
  );
}

function evidenceCardFromReview(review: ReviewItem): EvaluationEvidenceCardData {
  const action = isRecord(review.action) ? review.action : undefined;
  const evidenceCard = isRecord(review.evidence_card) ? review.evidence_card : undefined;
  const evaluation = isRecord(review.evaluation) ? review.evaluation : undefined;
  const final = recordValue(evaluation, "final");
  const decisionObject = recordValue(evaluation, "decision_object");
  const decisionArtifact = recordValue(evaluation, "decision_artifact");
  const evidencePacket = recordValue(evaluation, "evidence_packet");
  const risk = recordValue(evidenceCard, "risk");
  const timestamps = recordValue(evidenceCard, "timestamps");
  const safety = isSafetyReview(review, evidenceCard, action);
  const decisionId =
    stringValue(decisionObject, "decision_id") ||
    stringValue(decisionArtifact, "decision_id");
  const evidencePacketId =
    stringValue(decisionObject, "evidence_packet_id") ||
    stringValue(decisionArtifact, "evidence_packet_id") ||
    stringValue(evidencePacket, "packet_id");

  return {
    id:
      review.review_id ||
      stringValue(evidenceCard, "evidence_id") ||
      evidencePacketId ||
      decisionId ||
      review.created_at ||
      "telegram-evidence",
    eventType: safety ? "safety" : "telegram",
    surface:
      stringValue(evidenceCard, "surface") ||
      stringValue(decisionObject, "surface") ||
      "telegram",
    risk_level:
      stringValue(evidenceCard, "risk_label") ||
      stringValue(risk, "level") ||
      stringValue(risk, "label") ||
      stringValue(decisionObject, "risk_level") ||
      stringValue(decisionArtifact, "risk_level"),
    human_presence_likelihood: safety
      ? undefined
      : numberValue(final, "human_presence_likelihood") ??
        numberValue(final, "human_probability") ??
        numberValue(evaluation, "human_probability") ??
        numberValue(decisionObject, "human_probability"),
    automation_likelihood: safety
      ? undefined
      : numberValue(final, "automation_likelihood") ??
        numberValue(final, "bot_probability") ??
        numberValue(evaluation, "bot_probability") ??
        numberValue(decisionObject, "bot_probability"),
    agentic_control_likelihood: safety
      ? undefined
      : numberValue(final, "agentic_control_likelihood") ??
        numberValue(evaluation, "agentic_control_likelihood"),
    confidence:
      numberValue(evidenceCard, "confidence") ??
      numberValue(action, "confidence") ??
      numberValue(final, "confidence") ??
      numberValue(evaluation, "confidence") ??
      numberValue(decisionObject, "confidence"),
    reason_codes: reviewReasonCodes(review, evidenceCard, final, action),
    evidence_packet_id: safety ? undefined : evidencePacketId,
    decision_id: safety ? undefined : decisionId,
    recommended_action:
      stringValue(evidenceCard, "recommended_action") ||
      stringValue(action, "action") ||
      stringValue(decisionObject, "recommended_enforcement") ||
      review.status,
    timestamp:
      timestampValue(timestamps, "created_at") ||
      timestampValue(timestamps, "event_timestamp") ||
      review.created_at,
  };
}

export default function DashboardPage() {
  const [tenant] = useState("default");
  const [state, setState] = useState<DashboardState>(emptyState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reviewNotice, setReviewNotice] = useState("");
  const [selectedReview, setSelectedReview] = useState<ReviewItem | null>(null);
  const [reviewDecision, setReviewDecision] =
    useState<ReviewResolutionDecision>("allow");
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewActionPending, setReviewActionPending] =
    useState<ReviewActionPending>("");

  const loadDashboardData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({ tenant }).toString();
      const evidenceQuery = new URLSearchParams({ tenant, limit: "6" }).toString();
      const [telegramStatus, reviews, sdkEvidence] = await Promise.all([
        fetch(`/api/admin/telegram/status?${query}`, { cache: "no-store" }).then(
          readJson<TelegramStatus>,
        ),
        fetch(`/api/admin/telegram/reviews?${query}`, { cache: "no-store" }).then(
          readJson<ReviewPayload>,
        ),
        fetch(`/api/dashboard/evidence?${evidenceQuery}`, { cache: "no-store" }).then(
          readJson<EvidenceCardsPayload>,
        ),
      ]);
      setState({ telegramStatus, reviews, sdkEvidence });
    } catch (err) {
      setState(emptyState);
      setError(err instanceof Error ? err.message : "Dashboard data could not be loaded");
    } finally {
      setLoading(false);
    }
  }, [tenant]);

  useEffect(() => {
    void loadDashboardData();
  }, [loadDashboardData]);

  const fetchReviewDetails = useCallback(
    async (reviewId: string) => {
      const query = new URLSearchParams({ tenant }).toString();
      return fetch(
        `/api/admin/telegram/reviews/${encodeURIComponent(reviewId)}?${query}`,
        { cache: "no-store" },
      ).then(readJson<ReviewItem>);
    },
    [tenant],
  );

  const openReviewDetails = useCallback(
    async (review: ReviewItem) => {
      setReviewNotice("");
      setError("");
      setReviewActionPending("details");
      setSelectedReview(review);
      setReviewDecision(normalizedReviewDecision(review.admin_decision || review.action?.action));
      setReviewNotes(review.admin_notes || "");

      if (!review.review_id) {
        setReviewActionPending("");
        return;
      }

      try {
        const details = await fetchReviewDetails(review.review_id);
        setSelectedReview(details);
        setReviewDecision(
          normalizedReviewDecision(details.admin_decision || details.action?.action),
        );
        setReviewNotes(details.admin_notes || "");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Review details could not be loaded");
      } finally {
        setReviewActionPending("");
      }
    },
    [fetchReviewDetails],
  );

  const resolveSelectedReview = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedReview?.review_id) {
      return;
    }

    setReviewNotice("");
    setError("");
    setReviewActionPending("resolve");

    try {
      const query = new URLSearchParams({ tenant }).toString();
      await fetch(
        `/api/admin/telegram/reviews/${encodeURIComponent(selectedReview.review_id)}/resolve?${query}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ decision: reviewDecision, notes: reviewNotes }),
        },
      ).then(readJson<Record<string, unknown>>);

      const details = await fetchReviewDetails(selectedReview.review_id);
      setSelectedReview(details);
      setReviewNotice(`Review resolved as ${formatHumanLabel(reviewDecision)}.`);
      await loadDashboardData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review could not be resolved");
    } finally {
      setReviewActionPending("");
    }
  };

  const executeSelectedReview = async () => {
    if (!selectedReview?.review_id) {
      return;
    }

    setReviewNotice("");
    setError("");
    setReviewActionPending("execute");

    try {
      const query = new URLSearchParams({ tenant }).toString();
      const result = await fetch(
        `/api/admin/telegram/reviews/${encodeURIComponent(selectedReview.review_id)}/execute?${query}`,
        { method: "POST" },
      ).then(readJson<Record<string, unknown>>);
      const details = await fetchReviewDetails(selectedReview.review_id);
      setSelectedReview(details);
      setReviewNotice(
        displayValue(result.message) ||
          `Executed ${formatHumanLabel(selectedReview.admin_decision, "review action")}.`,
      );
      await loadDashboardData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review decision could not be executed");
    } finally {
      setReviewActionPending("");
    }
  };

  const reviews = useMemo(
    () => state.reviews?.pending_reviews ?? [],
    [state.reviews?.pending_reviews],
  );
  const selectedReviewCard = useMemo(
    () => (selectedReview ? evidenceCardFromReview(selectedReview) : null),
    [selectedReview],
  );
  const selectedReviewDetails = useMemo(
    () => (selectedReview ? reviewDetailItems(selectedReview) : []),
    [selectedReview],
  );
  const webSdkCards = useMemo<EvaluationEvidenceCardData[]>(
    () =>
      (state.sdkEvidence?.evidence_cards ?? []).map((card, index) => ({
        ...card,
        id: card.evidence_packet_id || `web-sdk-evidence-${index}`,
        eventType: "web_sdk",
        surface: card.surface || "web",
      })),
    [state.sdkEvidence],
  );
  const reviewEvidenceCards = useMemo(
    () => reviews.map(evidenceCardFromReview),
    [reviews],
  );
  const telegramCards = useMemo(
    () => reviewEvidenceCards.filter((card) => card.eventType === "telegram"),
    [reviewEvidenceCards],
  );
  const safetyCards = useMemo(
    () => reviewEvidenceCards.filter((card) => card.eventType === "safety"),
    [reviewEvidenceCards],
  );
  const statusItems = useMemo(
    () => [
      {
        icon: ShieldCheck,
        label: "Protection status",
        value: state.telegramStatus?.status || (loading ? "Loading" : "Unknown"),
      },
      {
        icon: Activity,
        label: "Pending reviews",
        value: formatCount(state.reviews?.count ?? state.telegramStatus?.pending_reviews),
      },
      {
        icon: Users,
        label: "Active sessions",
        value: formatCount(state.telegramStatus?.active_sessions),
      },
    ],
    [loading, state.reviews?.count, state.telegramStatus],
  );

  return (
    <main className="min-h-screen px-6 py-8">
      <section className="mx-auto flex w-full max-w-6xl flex-col gap-8">
        <div className="flex flex-col justify-between gap-4 border-b border-[var(--tp-border)] pb-6 sm:flex-row sm:items-end">
          <div>
            <p className="text-sm font-semibold uppercase tracking-widest text-[var(--tp-accent)]">
              Operations
            </p>
            <h1 className="mt-2 text-3xl font-bold text-[var(--tp-text-primary)]">
              Dashboard
            </h1>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              className="btn-secondary inline-flex items-center gap-2"
              disabled={loading}
              onClick={() => void loadDashboardData()}
              type="button"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
            <Link className="btn-primary" href="/dashboard/admin">
              Admin console
            </Link>
            <Link className="btn-secondary" href="/dashboard/login">
              Switch account
            </Link>
          </div>
        </div>

        {error && (
          <section className="card border-[var(--tp-danger)]">
            <div className="flex items-start gap-3 text-[var(--tp-danger)]">
              <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0" />
              <div>
                <h2 className="font-semibold">Dashboard unavailable</h2>
                <p className="mt-1 text-sm text-[var(--tp-text-secondary)]">{error}</p>
              </div>
            </div>
          </section>
        )}

        {reviewNotice && (
          <section className="card border-[var(--tp-success)] text-[var(--tp-success)]">
            {reviewNotice}
          </section>
        )}

        <div className="grid gap-4 md:grid-cols-3">
          {statusItems.map((item) => (
            <section className="card" key={item.label}>
              <div className="flex items-center gap-3">
                <item.icon className="h-5 w-5 text-[var(--tp-accent)]" />
                <p className="text-sm text-[var(--tp-text-muted)]">{item.label}</p>
              </div>
              <p className="mt-2 text-2xl font-semibold text-[var(--tp-text-primary)]">{item.value}</p>
            </section>
          ))}
        </div>

        <section className="flex flex-col gap-4">
          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <h2 className="text-lg font-semibold text-[var(--tp-text-primary)]">
              Web SDK evaluations
            </h2>
            <span className="badge badge-neutral">
              {loading ? "Loading" : `${webSdkCards.length} cards`}
            </span>
          </div>
          {webSdkCards.length ? (
            <div className="grid gap-4 xl:grid-cols-2">
              {webSdkCards.map((card) => (
                <EvaluationEvidenceCard card={card} key={card.id} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-[var(--tp-text-secondary)]">
              {loading ? "Loading Web SDK evidence..." : "No Web SDK evidence cards returned."}
            </p>
          )}
        </section>

        <section className="flex flex-col gap-4">
          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <h2 className="text-lg font-semibold text-[var(--tp-text-primary)]">
              Telegram evaluations
            </h2>
            <span className="badge badge-neutral">
              {loading ? "Loading" : `${telegramCards.length} cards`}
            </span>
          </div>
          {telegramCards.length ? (
            <div className="grid gap-4 xl:grid-cols-2">
              {telegramCards.map((card) => (
                <EvaluationEvidenceCard card={card} key={card.id} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-[var(--tp-text-secondary)]">
              {loading ? "Loading Telegram evidence..." : "No Telegram evidence cards returned."}
            </p>
          )}
        </section>

        <section className="flex flex-col gap-4">
          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <h2 className="text-lg font-semibold text-[var(--tp-text-primary)]">
              Safety escalations
            </h2>
            <span className="badge badge-neutral">
              {loading ? "Loading" : `${safetyCards.length} queued`}
            </span>
          </div>
          {safetyCards.length ? (
            <div className="grid gap-4 xl:grid-cols-2">
              {safetyCards.map((card) => (
                <EvaluationEvidenceCard card={card} key={card.id} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-[var(--tp-text-secondary)]">
              {loading ? "Loading safety escalations..." : "No safety escalations queued."}
            </p>
          )}
        </section>

        <section className="card">
          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <div>
              <h2 className="text-lg font-semibold text-[var(--tp-text-primary)]">Review queue</h2>
              <p className="mt-1 text-sm text-[var(--tp-text-secondary)]">
                Pending admin reviews for tenant {tenant}.
              </p>
            </div>
            <span className="badge badge-neutral">
              {loading ? "Loading" : `${reviews.length} pending`}
            </span>
          </div>

          <div className="mt-5 overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead className="text-[var(--tp-text-muted)]">
                <tr className="border-b border-[var(--tp-border)]">
                  <th className="py-3 pr-4 font-medium">Review</th>
                  <th className="py-3 pr-4 font-medium">Action</th>
                  <th className="py-3 pr-4 font-medium">Confidence</th>
                  <th className="py-3 pr-4 font-medium">Signals</th>
                  <th className="py-3 pr-4 font-medium">Status</th>
                  <th className="py-3 pr-4 font-medium">Details</th>
                </tr>
              </thead>
              <tbody>
                {reviews.map((review) => (
                  <tr
                    className={
                      selectedReview?.review_id === review.review_id
                        ? "border-b border-[var(--tp-border)] bg-[var(--tp-bg-secondary)]"
                        : "border-b border-[var(--tp-border)]"
                    }
                    key={review.review_id}
                  >
                    <td className="py-3 pr-4 text-[var(--tp-text-primary)]">
                      {review.review_id || "Unassigned"}
                      <span className="mt-1 block text-xs text-[var(--tp-text-muted)]">
                        {review.created_at || review.tenant_id || tenant}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-[var(--tp-text-secondary)]">
                      {formatHumanLabel(review.action?.action, "Review")}
                    </td>
                    <td className="py-3 pr-4 text-[var(--tp-text-secondary)]">
                      {formatConfidence(review.action?.confidence)}
                    </td>
                    <td className="py-3 pr-4 text-[var(--tp-text-secondary)]">
                      {reviewSignalLabel(review)}
                    </td>
                    <td className="py-3 pr-4">
                      <span className="badge badge-warning">
                        {formatHumanLabel(review.status, "Pending")}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      <button
                        className="btn-secondary inline-flex items-center gap-2"
                        disabled={reviewActionPending !== ""}
                        onClick={() => void openReviewDetails(review)}
                        type="button"
                      >
                        <Eye className="h-4 w-4" />
                        Details
                      </button>
                    </td>
                  </tr>
                ))}
                {!reviews.length && (
                  <tr>
                    <td className="py-6 text-[var(--tp-text-secondary)]" colSpan={6}>
                      {loading ? "Loading reviews..." : "No reviews require action right now."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {selectedReview && (
            <section className="mt-6 border-t border-[var(--tp-border)] pt-5">
              <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                <div>
                  <p className="text-xs font-semibold uppercase text-[var(--tp-accent)]">
                    Review details
                  </p>
                  <h3 className="mt-1 break-all text-lg font-semibold text-[var(--tp-text-primary)]">
                    {selectedReview.review_id || "Unassigned review"}
                  </h3>
                  <p className="mt-2 max-w-3xl text-sm text-[var(--tp-text-secondary)]">
                    Metadata-only review view. Message text, captions, media previews,
                    file URLs, and raw Telegram updates are not displayed.
                  </p>
                </div>
                <button
                  className="btn-secondary inline-flex items-center gap-2"
                  onClick={() => setSelectedReview(null)}
                  type="button"
                >
                  <X className="h-4 w-4" />
                  Close
                </button>
              </div>

              {reviewActionPending === "details" ? (
                <p className="mt-5 text-sm text-[var(--tp-text-secondary)]">
                  Loading review details...
                </p>
              ) : (
                <>
                  <dl className="mt-5 grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
                    {selectedReviewDetails.map((item) => (
                      <div
                        className="border-b border-[var(--tp-border)] pb-3"
                        key={item.label}
                      >
                        <dt className="text-xs uppercase text-[var(--tp-text-muted)]">
                          {item.label}
                        </dt>
                        <dd className="mt-1 break-words text-sm font-medium text-[var(--tp-text-primary)]">
                          {item.value}
                        </dd>
                      </div>
                    ))}
                  </dl>

                  <div className="mt-5">
                    <p className="text-xs uppercase text-[var(--tp-text-muted)]">
                      Reason codes
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {(selectedReviewCard?.reason_codes ?? []).length ? (
                        selectedReviewCard?.reason_codes?.map((code) => (
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

                  <form
                    className="mt-6 border-t border-[var(--tp-border)] pt-5"
                    onSubmit={resolveSelectedReview}
                  >
                    <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
                      <label className="text-sm text-[var(--tp-text-secondary)]">
                        Resolution
                        <select
                          className="mt-2"
                          disabled={reviewActionPending !== ""}
                          onChange={(event) =>
                            setReviewDecision(event.target.value as ReviewResolutionDecision)
                          }
                          value={reviewDecision}
                        >
                          {reviewResolutionDecisions.map((decision) => (
                            <option key={decision} value={decision}>
                              {formatHumanLabel(decision)}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="text-sm text-[var(--tp-text-secondary)]">
                        Admin notes
                        <textarea
                          className="mt-2 min-h-24"
                          disabled={reviewActionPending !== ""}
                          onChange={(event) => setReviewNotes(event.target.value)}
                          placeholder="Optional resolution notes"
                          value={reviewNotes}
                        />
                      </label>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-3">
                      <button
                        className="btn-primary"
                        disabled={!selectedReview.review_id || reviewActionPending !== ""}
                        type="submit"
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        {reviewActionPending === "resolve" ? "Resolving..." : "Resolve review"}
                      </button>
                      {shouldExecuteReviewDecision(selectedReview) && (
                        <button
                          className="btn-secondary inline-flex items-center gap-2"
                          disabled={reviewActionPending !== ""}
                          onClick={() => void executeSelectedReview()}
                          type="button"
                        >
                          <Play className="h-4 w-4" />
                          {reviewActionPending === "execute"
                            ? "Executing..."
                            : "Execute Telegram action"}
                        </button>
                      )}
                      {selectedReview.status === "resolved" &&
                        !shouldExecuteReviewDecision(selectedReview) && (
                          <p className="text-sm text-[var(--tp-text-secondary)]">
                            No Telegram execution is required for this resolution.
                          </p>
                        )}
                    </div>
                  </form>
                </>
              )}
            </section>
          )}
        </section>
      </section>
    </main>
  );
}
