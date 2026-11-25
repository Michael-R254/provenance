import Link from "next/link";

export default function NotFound() {
  return (
    <main id="main" className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
      <p className="font-mono text-sm text-muted">404</p>
      <h1 className="mt-2 font-serif text-4xl font-medium">Nothing published here</h1>
      <p className="mt-4">
        This page does not exist, or its write-up has not been approved for publication.
      </p>
      <p className="mt-4">
        <Link href="/projects" className="underline">
          See all projects
        </Link>
      </p>
    </main>
  );
}
