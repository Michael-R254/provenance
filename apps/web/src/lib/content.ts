/**
 * Reads Michael's content at build time. Only files with `status: approved` are ever returned;
 * this mirrors the ingestion rule (AGENTS.md rule 2) so the site and the guide show the same set.
 */
import fs from "node:fs";
import path from "node:path";
import { parse as parseYaml } from "yaml";

export const PROJECT_TYPES = [
  "research",
  "dissertation",
  "coursework",
  "personal",
  "work",
] as const;
export type ProjectType = (typeof PROJECT_TYPES)[number];

const TAG_FIELDS = ["skills", "languages", "frameworks", "models", "research_areas"] as const;
export type TagField = (typeof TAG_FIELDS)[number];

export type Project = {
  slug: string;
  title: string;
  type: ProjectType;
  summary: string;
  updated: string;
  organisation?: string;
  role?: string;
  period?: string;
  repo?: string;
  tags: Record<TagField, string[]>;
  body: string;
};

export type Profile = { title: string; updated: string; body: string };

export class ContentError extends Error {}

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const FRONTMATTER = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/;

export function contentDir(): string {
  return path.resolve(
    /*turbopackIgnore: true*/ process.cwd(),
    process.env.PROVENANCE_CONTENT_DIR ?? "../../content",
  );
}

type Raw = { data: Record<string, unknown>; body: string };

function readFile(file: string): Raw {
  const text = fs.readFileSync(file, "utf8");
  const match = FRONTMATTER.exec(text);
  if (!match) throw new ContentError(`${file}: missing frontmatter`);
  let data: unknown;
  try {
    data = parseYaml(match[1]);
  } catch (error) {
    throw new ContentError(`${file}: invalid YAML (${(error as Error).message.split("\n")[0]})`);
  }
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    throw new ContentError(`${file}: frontmatter must be a mapping`);
  }
  return { data: data as Record<string, unknown>, body: match[2] };
}

function isApproved(raw: Raw): boolean {
  return raw.data.status === "approved";
}

function str(raw: Raw, key: string, file: string, required: boolean): string | undefined {
  const value = raw.data[key];
  if (value === undefined || value === null || value === "") {
    if (required) throw new ContentError(`${file}: ${key} is required`);
    return undefined;
  }
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value !== "string" && typeof value !== "number") {
    throw new ContentError(`${file}: ${key} must be text`);
  }
  return String(value).trim();
}

function list(raw: Raw, key: string, file: string): string[] {
  const value = raw.data[key] ?? [];
  if (!Array.isArray(value) || value.some((v) => typeof v !== "string")) {
    throw new ContentError(`${file}: ${key} must be a list of text`);
  }
  return value as string[];
}

function toProject(raw: Raw, file: string): Project {
  const slug = str(raw, "id", file, true)!;
  if (!SLUG.test(slug)) throw new ContentError(`${file}: id must be a lowercase slug`);
  if (path.basename(file, ".md") !== slug) {
    throw new ContentError(`${file}: file name must match id ${slug}`);
  }
  const type = str(raw, "type", file, true) as ProjectType;
  if (!PROJECT_TYPES.includes(type)) throw new ContentError(`${file}: unknown type ${type}`);
  const repo = str(raw, "repo", file, false);
  if (repo && !repo.startsWith("https://")) {
    throw new ContentError(`${file}: repo must be an https URL`);
  }
  return {
    slug,
    title: str(raw, "title", file, true)!,
    type,
    summary: str(raw, "summary", file, true)!,
    updated: str(raw, "updated", file, true)!,
    organisation: str(raw, "organisation", file, false),
    role: str(raw, "role", file, false),
    period: str(raw, "period", file, false),
    repo,
    tags: Object.fromEntries(TAG_FIELDS.map((f) => [f, list(raw, f, file)])) as Record<
      TagField,
      string[]
    >,
    body: raw.body,
  };
}

/** Approved projects, most recently updated first. */
export function loadProjects(dir: string = contentDir()): Project[] {
  const projectsDir = path.join(dir, "projects");
  if (!fs.existsSync(projectsDir)) return [];
  return fs
    .readdirSync(projectsDir)
    .filter((name) => name.endsWith(".md") && !name.startsWith("_"))
    .map((name) => path.join(projectsDir, name))
    .map((file) => ({ file, raw: readFile(file) }))
    .filter(({ raw }) => isApproved(raw))
    .map(({ file, raw }) => toProject(raw, file))
    .sort((a, b) => b.updated.localeCompare(a.updated) || a.title.localeCompare(b.title));
}

export function loadProject(slug: string, dir: string = contentDir()): Project | undefined {
  return loadProjects(dir).find((p) => p.slug === slug);
}

export function loadProfile(dir: string = contentDir()): Profile | undefined {
  const file = path.join(dir, "profile.md");
  if (!fs.existsSync(file)) return undefined;
  const raw = readFile(file);
  if (!isApproved(raw)) return undefined;
  return {
    title: str(raw, "title", file, true)!,
    updated: str(raw, "updated", file, true)!,
    body: raw.body,
  };
}

export const TAG_LABELS: Record<TagField, string> = {
  skills: "Skills",
  languages: "Languages",
  frameworks: "Frameworks and tools",
  models: "Models",
  research_areas: "Research areas",
};
