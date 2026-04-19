import Link from "next/link";

const statusItems = [
  { label: "Reviews", value: "Ready" },
  { label: "Tenants", value: "Scoped" },
  { label: "Runtime", value: "Online" },
];

export default function DashboardPage() {
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
            <Link className="btn-primary" href="/dashboard/admin">
              Admin console
            </Link>
            <Link className="btn-secondary" href="/dashboard/login">
              Switch account
            </Link>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {statusItems.map((item) => (
            <section className="card" key={item.label}>
              <p className="text-sm text-[var(--tp-text-muted)]">{item.label}</p>
              <p className="mt-2 text-2xl font-semibold text-[var(--tp-text-primary)]">{item.value}</p>
            </section>
          ))}
        </div>

        <section className="card">
          <h2 className="text-lg font-semibold text-[var(--tp-text-primary)]">Review queue</h2>
          <p className="mt-2 text-[var(--tp-text-secondary)]">
            No reviews require action right now.
          </p>
        </section>
      </section>
    </main>
  );
}
