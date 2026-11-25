import Link from "next/link";

export function SiteIntro({ projectCount }: { projectCount: number }) {
  return (
    <section aria-labelledby="site-title" className="max-w-3xl">
      <p className="font-mono text-sm text-muted">Provenance · a guide with receipts</p>
      <h1
        id="site-title"
        className="mt-3 font-serif text-4xl leading-tight font-medium sm:text-5xl"
      >
        Ask about Michael Rollinson&apos;s engineering work.
      </h1>
      <p className="mt-6 max-w-[60ch] text-lg">
        Provenance answers questions in plain English and cites the project write-up behind every
        claim, so you can check the evidence yourself.
      </p>
      <p className="mt-6 font-mono text-sm">
        {projectCount > 0 ? (
          <Link href="/projects" className="underline">
            Browse {projectCount} project {projectCount === 1 ? "write-up" : "write-ups"}
          </Link>
        ) : (
          <span className="text-muted">Project write-ups are being prepared.</span>
        )}
      </p>
    </section>
  );
}
