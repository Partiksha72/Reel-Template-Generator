import type { Metadata } from "next";
import { Anton, Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const anton = Anton({ weight: "400", subsets: ["latin"], variable: "--font-anton" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Nagrik — Civic Sense India",
  description:
    "AI-powered civic news reels for India. Turn raw footage and a story overview into a polished 9:16 reel.",
  icons: [{ rel: "icon", url: "/favicon.svg", type: "image/svg+xml" }],
};

function Logo({ size = "md" }: { size?: "md" | "lg" }) {
  const box = size === "lg" ? "h-12 w-12" : "h-9 w-9";
  return (
    <span className="flex items-center gap-3">
      <span className={`${box} flex items-center justify-center rounded-md border border-gold/40 bg-wine`}>
        <svg viewBox="0 0 64 64" className="h-[78%] w-[78%]" aria-hidden>
          <circle cx="32" cy="32" r="25" fill="none" stroke="#D4A537" strokeWidth="3.5" />
          <text
            x="32"
            y="35"
            textAnchor="middle"
            fill="#E9C878"
            style={{
              fontFamily:
                "'Noto Sans Devanagari','Kohinoor Devanagari','Devanagari Sangam MN',sans-serif",
              fontWeight: 700,
              fontSize: 24,
            }}
          >
            ना
          </text>
        </svg>
      </span>
      <span className="leading-none">
        <span className={`block font-devanagari font-bold text-cream ${size === "lg" ? "text-2xl" : "text-lg"}`}>
          नागरिक
        </span>
        <span className="mt-1 block text-[9px] font-semibold uppercase tracking-[0.34em] text-gold/90">
          Civic Sense India
        </span>
      </span>
    </span>
  );
}

const NAV = [
  { href: "/", label: "Home" },
  { href: "/create", label: "Create Reel" },
  { href: "/projects", label: "Projects" },
  { href: "/settings", label: "Settings" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${anton.variable} ${inter.variable}`}>
      <body className="min-h-screen bg-ink font-body antialiased">
        {/* top brand strip */}
        <div className="h-1 w-full bg-gradient-to-r from-wine via-gold to-wine" />
        <header className="sticky top-0 z-50 border-b border-line bg-ink/85 backdrop-blur">
          <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
            <Link href="/" className="transition hover:opacity-85">
              <Logo />
            </Link>
            <nav className="hidden items-center gap-8 md:flex">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="text-[13px] font-semibold uppercase tracking-[0.18em] text-sand transition hover:text-gold"
                >
                  {item.label}
                </Link>
              ))}
              <Link href="/create" className="btn-gold !py-2 !px-4 text-xs">
                + Create New Reel
              </Link>
            </nav>
          </div>
        </header>
        <main>{children}</main>
        <footer className="border-t border-line py-10">
          <div className="mx-auto flex max-w-7xl flex-col items-center gap-3 px-6 text-center md:flex-row md:justify-between md:text-left">
            <Logo />
            <p className="text-xs tracking-wide text-muted">
              RAW NEWS → STORY → EDIT → REEL · Made for Indian civic journalism
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
