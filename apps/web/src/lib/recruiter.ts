/**
 * Recruiter mode. The chosen role changes only which starter questions are shown and the order
 * of projects. It is never sent to the API and never reaches the model (AGENTS.md rule 6).
 * Starter questions are questions, not claims, so they state nothing about Michael.
 */
import type { ProjectType } from "./content";

export const ROLES = [
  { id: "browsing", label: "Just browsing" },
  { id: "recruiter", label: "Recruiter" },
  { id: "hiring-manager", label: "Hiring manager" },
  { id: "engineer", label: "Engineer" },
] as const;
export type RoleId = (typeof ROLES)[number]["id"];
export const DEFAULT_ROLE: RoleId = "browsing";

export type StarterQuestion = { id: string; question: string };

const Q = {
  overview: { id: "overview", question: "What kinds of projects has Michael worked on?" },
  strongest: {
    id: "strongest",
    question: "Which project is the best place to start, and why?",
  },
  ownContribution: {
    id: "own-contribution",
    question: "In his projects, which parts did Michael do himself?",
  },
  stack: { id: "stack", question: "Which languages and tools appear across his projects?" },
  decisions: {
    id: "decisions",
    question: "What technical trade-offs did he describe making?",
  },
  testing: { id: "testing", question: "How did he test or evaluate his work?" },
  limits: { id: "limits", question: "What limitations does he note in his own projects?" },
} satisfies Record<string, StarterQuestion>;

export const STARTERS: Record<RoleId, StarterQuestion[]> = {
  browsing: [Q.overview, Q.strongest, Q.stack],
  recruiter: [Q.overview, Q.stack, Q.ownContribution],
  "hiring-manager": [Q.ownContribution, Q.decisions, Q.limits],
  engineer: [Q.decisions, Q.testing, Q.stack],
};

/** Lower comes first. Ties keep the default (most recently updated first) order. */
const TYPE_PRIORITY: Record<RoleId, ProjectType[]> = {
  browsing: [],
  recruiter: ["work", "dissertation", "research", "personal", "coursework"],
  "hiring-manager": ["work", "research", "dissertation", "personal", "coursework"],
  engineer: ["personal", "research", "work", "dissertation", "coursework"],
};

export function orderForRole<T extends { type: string }>(items: T[], role: RoleId): T[] {
  const priority = TYPE_PRIORITY[role];
  if (priority.length === 0) return items;
  const rank = (t: string) => {
    const i = priority.indexOf(t as ProjectType);
    return i === -1 ? priority.length : i;
  };
  return items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => rank(a.item.type) - rank(b.item.type) || a.index - b.index)
    .map(({ item }) => item);
}

export function isRole(value: unknown): value is RoleId {
  return ROLES.some((r) => r.id === value);
}

export const ROLE_STORAGE_KEY = "provenance-role";
