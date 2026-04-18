import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen px-6 py-10">
      <section className="mx-auto flex min-h-[calc(100vh-5rem)] w-full max-w-5xl flex-col justify-center gap-8">
        <div className="max-w-3xl">
          <p className="mb-4 text-sm font-semibold uppercase tracking-widest text-[var(--tp-accent)]">
            TruePresence
          </p>
          <h1 className="text-4xl font-bold leading-tight text-[var(--tp-text-primary)] sm:text-5xl">
            Human verification for high-trust communities.
          </h1>
          <p className="mt-5 max-w-2xl text-lg leading-8 text-[var(--tp-text-secondary)]">
            Review live enforcement decisions, tenant configuration, and evidence trails from one operating surface.
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row">
          <Link className="btn-primary" href="/dashboard/login">
            Sign in
          </Link>
          <Link className="btn-secondary" href="/dashboard">
            Open dashboard
          </Link>
        </div>
      </section>
    </main>
  );
}
