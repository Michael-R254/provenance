"use client";

import { useRouter, useSearchParams } from "next/navigation";

import { ChatPanel } from "@/components/chat/chat-panel";
import type { StarterAnswer } from "@/lib/content";

type Props = {
  projects: { slug: string; title: string }[];
  starterAnswers: Record<string, StarterAnswer>;
};

/** Full-screen chat. `?project=<slug>` scopes questions to one published project. */
export function AskView({ projects, starterAnswers }: Props) {
  const params = useSearchParams();
  const router = useRouter();
  const project = projects.find((p) => p.slug === params.get("project"));
  return (
    <ChatPanel
      starterAnswers={starterAnswers}
      project={project}
      onClearProject={() => router.replace("/ask")}
    />
  );
}
