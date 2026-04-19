"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  RefreshCw,
  Settings,
  Shield,
  UserPlus,
  Users,
} from "lucide-react";

interface CurrentUser {
  id: number | string;
  email: string;
  name: string;
  role: string;
  tenant_id: string;
}

interface ManagedUser extends CurrentUser {
  active?: boolean;
  created_at?: string;
  last_login?: string | null;
}

interface TelegramStatus {
  status?: string;
  tenant_id?: string;
  protected_groups?: number;
  active_sessions?: number;
  pending_reviews?: number;
  orchestrator_type?: string;
}

interface ReviewPayload {
  count?: number;
  pending_reviews?: Record<string, unknown>[];
}

interface ConfigPayload {
  tenant_id?: string;
  tenant_name?: string;
  active_detectors?: string[];
  configuration?: Record<string, unknown>;
}

interface AdminState {
  currentUser: CurrentUser | null;
  users: ManagedUser[];
  telegramStatus: TelegramStatus | null;
  reviews: ReviewPayload | null;
  config: ConfigPayload | null;
}

const emptyState: AdminState = {
  currentUser: null,
  users: [],
  telegramStatus: null,
  reviews: null,
  config: null,
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

export default function AdminPage() {
  const [tenant, setTenant] = useState("default");
  const [state, setState] = useState<AdminState>(emptyState);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [newUser, setNewUser] = useState({
    email: "",
    name: "",
    password: "",
    role: "reviewer",
    tenant_id: "default",
  });

  const loadAdminData = useCallback(async () => {
    setLoading(true);
    setError("");
    setNotice("");

    try {
      const query = new URLSearchParams({ tenant }).toString();
      const [currentUser, users, telegramStatus, reviews, config] =
        await Promise.all([
          fetch("/api/auth/me", { cache: "no-store" }).then(readJson<CurrentUser>),
          fetch("/api/admin/users", { cache: "no-store" }).then(readJson<ManagedUser[]>),
          fetch(`/api/admin/telegram/status?${query}`, { cache: "no-store" }).then(
            readJson<TelegramStatus>,
          ),
          fetch(`/api/admin/telegram/reviews?${query}`, { cache: "no-store" }).then(
            readJson<ReviewPayload>,
          ),
          fetch(`/api/admin/telegram/config?${query}`, { cache: "no-store" }).then(
            readJson<ConfigPayload>,
          ),
        ]);

      setState({ currentUser, users, telegramStatus, reviews, config });
      setNewUser((value) => ({ ...value, tenant_id: currentUser.tenant_id || tenant }));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Admin data could not be loaded";
      setState(emptyState);
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [tenant]);

  useEffect(() => {
    void loadAdminData();
  }, [loadAdminData]);

  const adminAllowed = state.currentUser?.role === "super_admin";
  const detectorSummary = useMemo(
    () => state.config?.active_detectors?.join(", ") || "No detector data loaded",
    [state.config],
  );

  const createUser = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");

    try {
      await fetch("/api/admin/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newUser),
      }).then(readJson<ManagedUser>);
      setNotice(`Created ${newUser.email}`);
      setNewUser({
        email: "",
        name: "",
        password: "",
        role: "reviewer",
        tenant_id: tenant,
      });
      await loadAdminData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "User could not be created");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="min-h-screen px-6 py-8">
      <section className="mx-auto flex w-full max-w-7xl flex-col gap-8">
        <div className="flex flex-col justify-between gap-4 border-b border-[var(--tp-border)] pb-6 lg:flex-row lg:items-end">
          <div>
            <p className="text-sm font-semibold uppercase text-[var(--tp-accent)]">
              Administration
            </p>
            <h1 className="mt-2 text-3xl font-bold text-[var(--tp-text-primary)]">
              Admin console
            </h1>
            <p className="mt-2 max-w-2xl text-[var(--tp-text-secondary)]">
              Manage users, tenant status, review queues, and Telegram protection settings.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              className="btn-secondary"
              disabled={loading}
              onClick={() => void loadAdminData()}
              type="button"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
            <Link className="btn-secondary" href="/dashboard">
              Back to dashboard
            </Link>
          </div>
        </div>

        {error && (
          <section className="card border-[var(--tp-danger)]">
            <div className="flex items-start gap-3 text-[var(--tp-danger)]">
              <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0" />
              <div>
                <h2 className="font-semibold">Admin console unavailable</h2>
                <p className="mt-1 text-sm text-[var(--tp-text-secondary)]">{error}</p>
                <p className="mt-2 text-sm text-[var(--tp-text-secondary)]">
                  Sign in as a super_admin account, then confirm the web app can reach the
                  TruePresence API URL configured for this deployment.
                </p>
              </div>
            </div>
          </section>
        )}

        {notice && (
          <section className="card border-[var(--tp-success)] text-[var(--tp-success)]">
            {notice}
          </section>
        )}

        <div className="grid gap-4 lg:grid-cols-4">
          <section className="card">
            <div className="flex items-center gap-3">
              <Shield className="h-5 w-5 text-[var(--tp-accent)]" />
              <p className="text-sm text-[var(--tp-text-muted)]">Signed in</p>
            </div>
            <p className="mt-3 text-xl font-semibold text-[var(--tp-text-primary)]">
              {state.currentUser?.name || "Unknown"}
            </p>
            <p className="mt-1 text-sm text-[var(--tp-text-secondary)]">
              {state.currentUser?.role || "No role loaded"}
            </p>
          </section>

          <section className="card">
            <div className="flex items-center gap-3">
              <Users className="h-5 w-5 text-[var(--tp-accent)]" />
              <p className="text-sm text-[var(--tp-text-muted)]">Users</p>
            </div>
            <p className="mt-3 text-2xl font-semibold text-[var(--tp-text-primary)]">
              {state.users.length}
            </p>
          </section>

          <section className="card">
            <div className="flex items-center gap-3">
              <Activity className="h-5 w-5 text-[var(--tp-accent)]" />
              <p className="text-sm text-[var(--tp-text-muted)]">Pending reviews</p>
            </div>
            <p className="mt-3 text-2xl font-semibold text-[var(--tp-text-primary)]">
              {state.reviews?.count ?? state.telegramStatus?.pending_reviews ?? 0}
            </p>
          </section>

          <section className="card">
            <div className="flex items-center gap-3">
              <Settings className="h-5 w-5 text-[var(--tp-accent)]" />
              <p className="text-sm text-[var(--tp-text-muted)]">Tenant</p>
            </div>
            <input
              className="mt-3"
              disabled={loading}
              onChange={(event) => setTenant(event.target.value || "default")}
              value={tenant}
            />
          </section>
        </div>

        {!adminAllowed && !loading && state.currentUser && (
          <section className="card border-[var(--tp-warning)]">
            <p className="font-semibold text-[var(--tp-warning)]">Admin role required</p>
            <p className="mt-2 text-sm text-[var(--tp-text-secondary)]">
              This account is authenticated, but only super_admin users can manage tenant
              users or Telegram protection settings.
            </p>
          </section>
        )}

        <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <section className="card">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
              <div>
                <h2 className="text-lg font-semibold text-[var(--tp-text-primary)]">
                  Users
                </h2>
                <p className="mt-1 text-sm text-[var(--tp-text-secondary)]">
                  Super admin, reviewer, and observer accounts.
                </p>
              </div>
              <span className="badge badge-neutral">{loading ? "Loading" : "Current"}</span>
            </div>

            <div className="mt-5 overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="text-[var(--tp-text-muted)]">
                  <tr className="border-b border-[var(--tp-border)]">
                    <th className="py-3 pr-4 font-medium">Name</th>
                    <th className="py-3 pr-4 font-medium">Email</th>
                    <th className="py-3 pr-4 font-medium">Role</th>
                    <th className="py-3 pr-4 font-medium">Tenant</th>
                    <th className="py-3 pr-4 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {state.users.map((user) => (
                    <tr className="border-b border-[var(--tp-border)]" key={user.id}>
                      <td className="py-3 pr-4 text-[var(--tp-text-primary)]">{user.name}</td>
                      <td className="py-3 pr-4 text-[var(--tp-text-secondary)]">{user.email}</td>
                      <td className="py-3 pr-4">
                        <span className="badge badge-neutral">{user.role}</span>
                      </td>
                      <td className="py-3 pr-4 text-[var(--tp-text-secondary)]">
                        {user.tenant_id}
                      </td>
                      <td className="py-3 pr-4">
                        <span className={user.active === false ? "badge badge-danger" : "badge badge-success"}>
                          {user.active === false ? "Inactive" : "Active"}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {!state.users.length && (
                    <tr>
                      <td className="py-6 text-[var(--tp-text-secondary)]" colSpan={5}>
                        {loading ? "Loading users..." : "No users returned."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card">
            <div className="flex items-center gap-3">
              <UserPlus className="h-5 w-5 text-[var(--tp-accent)]" />
              <h2 className="text-lg font-semibold text-[var(--tp-text-primary)]">
                Create user
              </h2>
            </div>
            <form className="mt-5 space-y-4" onSubmit={createUser}>
              <input
                onChange={(event) => setNewUser((value) => ({ ...value, name: event.target.value }))}
                placeholder="Name"
                required
                value={newUser.name}
              />
              <input
                onChange={(event) => setNewUser((value) => ({ ...value, email: event.target.value }))}
                placeholder="Email"
                required
                type="email"
                value={newUser.email}
              />
              <input
                onChange={(event) => setNewUser((value) => ({ ...value, password: event.target.value }))}
                placeholder="Temporary password"
                required
                type="password"
                value={newUser.password}
              />
              <select
                onChange={(event) => setNewUser((value) => ({ ...value, role: event.target.value }))}
                value={newUser.role}
              >
                <option value="reviewer">reviewer</option>
                <option value="observer">observer</option>
                <option value="super_admin">super_admin</option>
              </select>
              <input
                onChange={(event) =>
                  setNewUser((value) => ({ ...value, tenant_id: event.target.value }))
                }
                placeholder="Tenant"
                required
                value={newUser.tenant_id}
              />
              <button className="btn-primary w-full" disabled={saving || !adminAllowed} type="submit">
                {saving ? "Creating..." : "Create user"}
              </button>
            </form>
          </section>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <section className="card">
            <h2 className="text-lg font-semibold text-[var(--tp-text-primary)]">
              Telegram protection
            </h2>
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <p className="text-sm text-[var(--tp-text-secondary)]">
                Status
                <span className="mt-1 block text-lg font-semibold text-[var(--tp-text-primary)]">
                  {state.telegramStatus?.status || "Unknown"}
                </span>
              </p>
              <p className="text-sm text-[var(--tp-text-secondary)]">
                Protected groups
                <span className="mt-1 block text-lg font-semibold text-[var(--tp-text-primary)]">
                  {state.telegramStatus?.protected_groups ?? 0}
                </span>
              </p>
              <p className="text-sm text-[var(--tp-text-secondary)]">
                Active sessions
                <span className="mt-1 block text-lg font-semibold text-[var(--tp-text-primary)]">
                  {state.telegramStatus?.active_sessions ?? 0}
                </span>
              </p>
              <p className="text-sm text-[var(--tp-text-secondary)]">
                Orchestrator
                <span className="mt-1 block text-lg font-semibold text-[var(--tp-text-primary)]">
                  {state.telegramStatus?.orchestrator_type || "Unknown"}
                </span>
              </p>
            </div>
          </section>

          <section className="card">
            <h2 className="text-lg font-semibold text-[var(--tp-text-primary)]">
              Active detectors
            </h2>
            <p className="mt-3 text-sm text-[var(--tp-text-secondary)]">{detectorSummary}</p>
            <pre className="mt-5 max-h-64 overflow-auto rounded-md border border-[var(--tp-border)] bg-[var(--tp-bg-secondary)] p-4 text-xs text-[var(--tp-text-secondary)]">
              {JSON.stringify(state.config?.configuration || {}, null, 2)}
            </pre>
          </section>
        </div>
      </section>
    </main>
  );
}
