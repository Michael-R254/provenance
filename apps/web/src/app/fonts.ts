import localFont from "next/font/local";

// Self-hosted from @fontsource packages, Latin subset only (SIL Open Font Licence).
export const newsreader = localFont({
  src: "../../node_modules/@fontsource-variable/newsreader/files/newsreader-latin-wght-normal.woff2",
  variable: "--font-newsreader",
  weight: "200 800",
  display: "swap",
  adjustFontFallback: "Times New Roman",
});

export const plexSans = localFont({
  src: [
    {
      path: "../../node_modules/@fontsource/ibm-plex-sans/files/ibm-plex-sans-latin-400-normal.woff2",
      weight: "400",
      style: "normal",
    },
    {
      path: "../../node_modules/@fontsource/ibm-plex-sans/files/ibm-plex-sans-latin-600-normal.woff2",
      weight: "600",
      style: "normal",
    },
  ],
  variable: "--font-plex-sans",
  display: "swap",
});

export const plexMono = localFont({
  src: "../../node_modules/@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-400-normal.woff2",
  variable: "--font-plex-mono",
  weight: "400",
  display: "swap",
  preload: false,
});
