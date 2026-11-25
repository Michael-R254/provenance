/**
 * Markdown to safe HTML. Raw HTML in content is dropped, the output is sanitised, and `##`
 * headings get the same anchors the ingestion pipeline gives their chunks.
 */
import type { Element, ElementContent, Root, Text } from "hast";
import rehypeSanitize from "rehype-sanitize";
import rehypeStringify from "rehype-stringify";
import remarkGfm from "remark-gfm";
import remarkParse from "remark-parse";
import remarkRehype from "remark-rehype";
import { unified } from "unified";

import { AnchorRegistry } from "./anchors";

export type Section = { heading: string; anchor: string };
export type Rendered = { html: string; sections: Section[]; introAnchor: string };

function textOf(node: ElementContent | Element): string {
  if (node.type === "text") return (node as Text).value;
  if ("children" in node) return node.children.map((c) => textOf(c as ElementContent)).join("");
  return "";
}

function anchorHeadings(title: string, out: { sections: Section[]; introAnchor: string }) {
  return () => (tree: Root) => {
    const registry = new AnchorRegistry();
    out.introAnchor = registry.anchorFor(title);
    tree.children = tree.children.filter(
      (node) => !(node.type === "element" && node.tagName === "h1"),
    );
    for (const node of tree.children) {
      if (node.type !== "element" || node.tagName !== "h2") continue;
      const heading = textOf(node);
      const anchor = registry.anchorFor(heading);
      node.properties = { ...node.properties, id: anchor };
      node.children = [
        {
          type: "element",
          tagName: "a",
          properties: { href: `#${anchor}`, className: ["heading-link"] },
          children: node.children,
        },
      ];
      out.sections.push({ heading, anchor });
    }
  };
}

export function renderMarkdown(body: string, title: string): Rendered {
  const out = { sections: [] as Section[], introAnchor: "" };
  const html = unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(remarkRehype)
    .use(rehypeSanitize)
    .use(anchorHeadings(title, out))
    .use(rehypeStringify)
    .processSync(body)
    .toString();
  return { html, ...out };
}
