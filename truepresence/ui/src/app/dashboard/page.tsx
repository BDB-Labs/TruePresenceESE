"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  RefreshCw,
  ShieldCheck,
  Users,
} from "lucide-react";

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
  risk_factors?: string[];
  threat_categories?: string[];
  action?: {
    action?: string;
    confidence?: number;
    enforcement_mode?: string;
  };
}

interface ReviewPayload {
  count?: number;
  pending_reviews?: ReviewItem[];
}

interface DashboardState {
  telegramStatus: TelegramStatus | null;
  reviews: ReviewPayload | null;
}

const emptyState: DashboardState = {
  telegramStatus: null,
  reviews: null,
};

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

export default function DashboardPage() {
  const [tenant] = useState("default");
  const [state, setState] = useState<DashboardState>(emptyState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDashboardData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({ tenant }).toString();
      const [telegramStatus, reviews] = await Promise.all([
        fetch(`/api/admin/telegram/status?${query}`, { cache: "no-store" }).then(
          readJson<TelegramStatus>,
        ),
        fetch(`/api/admin/telegram/reviews?${query}`, { cache: "no-store" }).then(
          readJson<ReviewPayload>,
        ),
      ]);
      setState({ telegramStatus, reviews });
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

  const reviews = state.reviews?.pending_reviews ?? [];
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
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="text-[var(--tp-text-muted)]">
                <tr className="border-b border-[var(--tp-border)]">
                  <th className="py-3 pr-4 font-medium">Review</th>
                  <th className="py-3 pr-4 font-medium">Action</th>
                  <th className="py-3 pr-4 font-medium">Confidence</th>
                  <th className="py-3 pr-4 font-medium">Signals</th>
                  <th className="py-3 pr-4 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {reviews.map((review) => (
                  <tr className="border-b border-[var(--tp-border)]" key={review.review_id}>
                    <td className="py-3 pr-4 text-[var(--tp-text-primary)]">
                      {review.review_id || "Unassigned"}
                      <span className="mt-1 block text-xs text-[var(--tp-text-muted)]">
                        {review.created_at || review.tenant_id || tenant}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-[var(--tp-text-secondary)]">
                      {review.action?.action || "review"}
                    </td>
                    <td className="py-3 pr-4 text-[var(--tp-text-secondary)]">
                      {formatConfidence(review.action?.confidence)}
                    </td>
                    <td className="py-3 pr-4 text-[var(--tp-text-secondary)]">
                      {(review.risk_factors || review.threat_categories || []).slice(0, 3).join(", ") || "None"}
                    </td>
                    <td className="py-3 pr-4">
                      <span className="badge badge-warning">{review.status || "pending"}</span>
                    </td>
                  </tr>
                ))}
                {!reviews.length && (
                  <tr>
                    <td className="py-6 text-[var(--tp-text-secondary)]" colSpan={5}>
                      {loading ? "Loading reviews..." : "No reviews require action right now."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </section>
    </main>
  );
}
