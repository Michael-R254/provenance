// Build-time guard (runs after `next build`): fails if any unapproved content file's id or
// title appears anywhere in the build output. The loader already filters drafts; this proves it.
import fs from "node:fs";
import path from "node:path";
import { parse } from "yaml";

const contentDir = path.resolve(process.env.PROVENANCE_CONTENT_DIR ?? "../../content");
const buildDir = path.resolve(".next");

function markdownFiles(dir) {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return markdownFiles(full);
    return entry.name.endsWith(".md") && !entry.name.startsWith("_") ? [full] : [];
  });
}

const drafts = [];
for (const file of markdownFiles(contentDir)) {
  const match = /^---\r?\n([\s\S]*?)\r?\n---/.exec(fs.readFileSync(file, "utf8"));
  const data = match ? parse(match[1]) : {};
  if (data?.status !== "approved") {
    const needles = [data?.id, data?.title].filter((v) => typeof v === "string" && v.length > 3);
    drafts.push({ file: path.relative(contentDir, file), needles });
  }
}

function outputFiles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return entry.name === "cache" ? [] : outputFiles(full);
    return /\.(html|rsc|body|json|js|txt|meta)$/.test(entry.name) ? [full] : [];
  });
}

const leaks = [];
const files = outputFiles(buildDir);
for (const file of files) {
  const text = fs.readFileSync(file, "utf8");
  for (const draft of drafts) {
    for (const needle of draft.needles) {
      if (text.includes(needle))
        leaks.push(`${draft.file} ("${needle}") in ${path.relative(buildDir, file)}`);
    }
  }
}

if (leaks.length > 0) {
  console.error(`Draft content found in the build output:\n  ${leaks.join("\n  ")}`);
  process.exit(1);
}
console.log(
  `Draft check: ${drafts.length} unapproved file(s), none in ${files.length} build files.`,
);
