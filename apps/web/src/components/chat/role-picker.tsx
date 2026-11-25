"use client";

import { ROLES } from "@/lib/recruiter";

import { useRole } from "./use-role";

export function RolePicker() {
  const [role, setRole] = useRole();
  return (
    <fieldset className="js-only">
      <legend className="font-mono text-sm text-muted">
        I&apos;m visiting as…{" "}
        <span className="sr-only">(changes suggested questions and project order only)</span>
      </legend>
      <div className="mt-2 flex flex-wrap gap-2">
        {ROLES.map((r) => (
          <label
            key={r.id}
            className={`cursor-pointer rounded border px-3 py-1.5 text-sm has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-[var(--focus)] ${
              role === r.id ? "border-accent bg-accent-soft" : "border-line"
            }`}
          >
            <input
              type="radio"
              name="visitor-role"
              value={r.id}
              checked={role === r.id}
              onChange={() => setRole(r.id)}
              className="sr-only"
            />
            {r.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
