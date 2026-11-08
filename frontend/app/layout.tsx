import type { Metadata, Viewport } from "next";
import { Atkinson_Hyperlegible_Next } from "next/font/google";
import "./globals.css";

const atkinson = Atkinson_Hyperlegible_Next({ subsets: ["latin"], variable: "--font-atkinson", display: "swap", adjustFontFallback: false });

export const metadata: Metadata = {
  title: { default: "ScamShield", template: "%s · ScamShield" },
  description: "ScamShield checks the links in your parents’ Gmail and warns them, and you, about scam emails.",
  icons: {
    icon: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect x='2' y='7' width='28' height='18' rx='4' fill='%233b5bdb'/%3E%3Cpath d='M5 10l11 8 11-8' fill='none' stroke='white' stroke-width='2.5' stroke-linecap='round'/%3E%3C/svg%3E",
  },
};

export const viewport: Viewport = { themeColor: "#0a1020", colorScheme: "dark" };

// Runs before paint: applies the saved text size, and remembers the time zone so the server can
// bucket "today" the way the reader sees it.
const boot = `try{var t=localStorage.getItem("ss-text");if(t)document.documentElement.dataset.text=t;}catch(e){}
try{var z=Intl.DateTimeFormat().resolvedOptions().timeZone;if(z&&document.cookie.indexOf("tz="+encodeURIComponent(z))<0)document.cookie="tz="+encodeURIComponent(z)+";path=/;max-age=31536000;samesite=lax";}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={atkinson.variable} suppressHydrationWarning>
      <head>
        <script id="ss-boot" dangerouslySetInnerHTML={{ __html: boot }} />
      </head>
      <body className="min-h-dvh">
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:bg-surface-2 focus:px-4 focus:py-2 focus:rounded-lg">
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
