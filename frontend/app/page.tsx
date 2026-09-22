export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-3xl font-semibold tracking-tight">JD Analyzer</h1>
      <p className="text-center text-sm text-neutral-600 dark:text-neutral-400">
        Paste a job description. Get a backend skill match and resume profile recommendation.
      </p>
      <a
        className="rounded-md bg-neutral-900 px-4 py-2 text-sm text-white dark:bg-neutral-100 dark:text-neutral-900"
        href="/login"
      >
        Sign in
      </a>
    </main>
  );
}
