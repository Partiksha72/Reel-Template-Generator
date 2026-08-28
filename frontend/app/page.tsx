"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listProjects } from "@/lib/api";
import type { Project } from "@/lib/types";
import { fmtDate, fmtDuration } from "@/lib/format";

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-coal2 text-sand",
  processing: "bg-gold/15 text-goldsoft",
  ready: "bg-emerald-900/40 text-emerald-300",
  exported: "bg-emerald-900/60 text-emerald-200",
  error: "bg-red-900/40 text-red-300",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`rounded-sm px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.16em] ${
        STATUS_STYLES[status] ?? STATUS_STYLES.draft
      }`}
    >
      {status}
    </span>
  );
}

function Thumb({ project }: { project: Project }) {
  const first = project.videos?.[0];
  if (first?.thumbnail) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/media/${project.id}/${first.thumbnail}`}
        alt=""
        className="h-full w-full object-cover opacity-90"
      />
    );
  }
  return (
    <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-wine to-ink">
      <span className="font-devanagari text-3xl font-bold text-gold/70">नागरिक</span>
    </div>
  );
}

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch(() => setProjects([]));
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-6 pb-20">
      {/* ── hero ─────────────────────────────────────────── */}
      <section className="relative mt-10 overflow-hidden border border-line bg-wine">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(212,165,55,0.13),transparent_55%)]" />
        <div className="relative grid gap-10 px-8 py-14 md:grid-cols-[1.4fr_1fr] md:px-14 md:py-20">
          <div className="animate-rise">
            <p className="label-caps !text-gold/90">नागरिक · Civic Sense India</p>
            <h1 className="mt-5 font-display text-5xl leading-[1.02] tracking-tight text-cream md:text-6xl lg:text-7xl">
              TURN NEWS INTO STORIES PEOPLE ACTUALLY WATCH.
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-sand">
              AI-powered civic news reels for India. Drop in raw footage, add your story —
              Nagrik writes the script, picks the shots and cuts a polished 9:16 reel.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-4">
              <Link href="/create" className="btn-gold !px-7 !py-3.5 text-base">
                + Create New Reel
              </Link>
              <span className="text-xs uppercase tracking-[0.2em] text-sand/70">
                Raw footage → script → captions → export
              </span>
            </div>
          </div>

          {/* mini reel mock */}
          <div className="hidden items-end justify-center md:flex">
            <div className="w-56 rotate-2 overflow-hidden rounded-md border border-gold/25 bg-ink shadow-2xl shadow-black/50">
              <div className="flex items-center justify-between border-b border-line px-3 py-2">
                <span className="font-devanagari text-xs font-bold text-gold">नागरिक</span>
                <span className="text-[8px] uppercase tracking-[0.2em] text-muted">9:16</span>
              </div>
              <div className="aspect-[9/12] bg-gradient-to-b from-coal2 via-wine/40 to-ink p-4">
                <p className="font-display text-xl leading-tight text-cream">
                  DELHI&apos;S PARKING RULES <span className="text-gold">JUST CHANGED</span>
                </p>
                <p className="mt-3 font-display text-base leading-tight text-cream/80">
                  BUT RESIDENTS HAVE QUESTIONS
                </p>
              </div>
              <div className="border-t border-line px-3 py-2 text-[8px] uppercase tracking-[0.24em] text-muted">
                Hook · Context · Impact · CTA
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── how it works strip ───────────────────────────── */}
      <section className="mt-6 grid grid-cols-2 gap-px overflow-hidden border border-line bg-line md:grid-cols-4">
        {[
          ["01", "Story", "Paste your notes, summary or facts."],
          ["02", "Footage", "Drop raw video from the field."],
          ["03", "AI Edit", "Script, clip selection & captions."],
          ["04", "Export", "A clean 1080×1920 MP4 reel."],
        ].map(([n, t, d]) => (
          <div key={n} className="bg-coal px-6 py-5">
            <span className="font-display text-sm text-gold">{n}</span>
            <h3 className="mt-1 font-display text-lg uppercase tracking-wide text-cream">{t}</h3>
            <p className="mt-1 text-xs leading-relaxed text-muted">{d}</p>
          </div>
        ))}
      </section>

      {/* ── recent reels ─────────────────────────────────── */}
      <section className="mt-12">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h2 className="font-display text-2xl uppercase tracking-wide text-cream">Recent Reels</h2>
            <div className="gold-rule" />
          </div>
          <Link href="/projects" className="text-xs font-semibold uppercase tracking-[0.18em] text-gold hover:text-goldsoft">
            All Projects →
          </Link>
        </div>

        {projects === null ? (
          <div className="panel p-10 text-center text-sm text-muted">Loading projects…</div>
        ) : projects.length === 0 ? (
          <div className="panel flex flex-col items-center gap-4 px-6 py-16 text-center">
            <span className="font-devanagari text-4xl font-bold text-gold/40">खबर से रील तक</span>
            <p className="max-w-sm text-sm leading-relaxed text-muted">
              No reels yet. Create your first one — upload footage, paste a story overview,
              and let Nagrik do the edit.
            </p>
            <Link href="/create" className="btn-gold mt-2">+ Create New Reel</Link>
          </div>
        ) : (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {projects.slice(0, 8).map((p) => (
              <Link
                key={p.id}
                href={`/projects/${p.id}`}
                className="group border border-line bg-coal transition hover:border-gold/40"
              >
                <div className="aspect-video overflow-hidden border-b border-line">
                  <Thumb project={p} />
                </div>
                <div className="space-y-2 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="line-clamp-1 text-sm font-bold text-cream group-hover:text-goldsoft">
                      {p.title}
                    </h3>
                    <StatusBadge status={p.status} />
                  </div>
                  <div className="flex items-center gap-3 text-[11px] uppercase tracking-wider text-muted">
                    <span>{fmtDuration(p.timeline.reduce((a, i) => a + i.duration, 0) || p.settings.duration_target)}</span>
                    <span>·</span>
                    <span>{fmtDate(p.created_at)}</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
