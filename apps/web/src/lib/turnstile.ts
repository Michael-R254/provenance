/**
 * Cloudflare Turnstile, loaded only when a site key is configured. Without one (local
 * development and tests) a placeholder token is sent; the API's development default accepts it
 * and production refuses to start without a real secret.
 */
const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
const SCRIPT = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

type Turnstile = {
  render: (el: HTMLElement, options: Record<string, unknown>) => string;
  execute: (id: string) => void;
  reset: (id: string) => void;
};

declare global {
  interface Window {
    turnstile?: Turnstile;
  }
}

let loading: Promise<Turnstile> | null = null;

function load(): Promise<Turnstile> {
  loading ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT;
    script.async = true;
    script.onload = () =>
      window.turnstile ? resolve(window.turnstile) : reject(new Error("no turnstile"));
    script.onerror = () => reject(new Error("turnstile failed to load"));
    document.head.appendChild(script);
  });
  return loading;
}

export async function turnstileToken(): Promise<string> {
  if (!SITE_KEY) return "development-token";
  const turnstile = await load();
  const host = document.createElement("div");
  host.hidden = true;
  document.body.appendChild(host);
  try {
    return await new Promise<string>((resolve, reject) => {
      const id = turnstile.render(host, {
        sitekey: SITE_KEY,
        execution: "execute",
        appearance: "interaction-only",
        callback: resolve,
        "error-callback": () => reject(new Error("turnstile error")),
      });
      turnstile.execute(id);
    });
  } finally {
    host.remove();
  }
}
