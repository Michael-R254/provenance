import { ChatPanel } from "@/components/chat/chat-panel";
import { SiteIntro } from "@/components/site-intro";
import { loadProjects } from "@/lib/content";
import { starterAnswers } from "@/lib/starter-answers";

export default function Home() {
  return (
    <main id="main" className="mx-auto max-w-6xl px-4 py-12 sm:px-6 sm:py-16">
      <SiteIntro projectCount={loadProjects().length} />
      <div className="mt-12">
        <ChatPanel starterAnswers={starterAnswers()} />
      </div>
    </main>
  );
}
