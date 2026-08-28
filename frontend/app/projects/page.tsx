"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { deleteProject, listProjects } from "@/lib/api";
import type { Project } from "@/lib/types";
import { fmtDate, fmtDuration } from "@/lib/format";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);

  useEffect(() => {
    listProjects().then(setProjects).catch(() => setProjects([]));
  }, []);

  async function remove(id: string) {
    if (!confirm("Delete this project and its footage?")) return;
    await deleteProject(id);
    setProjects((prev) => prev?.filter((p) => p.id !== id) ?? null);
  }

  return (
    <div className="mx-auto max-w-7xl px-6 pb-24">
      <div className="flex items-center gap-4 border-b border-line py-8">
        <h1 className="font-display text-4xl uppercase tracking-wide text-cream">Projects</h1>
        <div className="gold-rule" />
        <Link href="/create" className="btn-gold ml-auto !py-2 !px-4 text-xs">+ Create New Reel</Link>
      </div>

      {projects === null ? (
        <p className="mt-10 text-sm text-muted">Loading…</p>
      ) : projects.length === 0 ? (
        <p className="mt-10 text-sm text-muted">
          No projects yet — <Link href="/create" className="text-gold hover:underline">create your first reel</Link>.
        </p>
      ) : (
        <div className="mt-8 overflow-hidden border border-line">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-line bg-coal text-[11px] uppercase tracking-[0.18em] text-muted">
                <th className="px-5 py-3 font-semibold">Title</th>
                <th className="px-5 py-3 font-semibold">Duration</th>
                <th className="hidden px-5 py-3 font-semibold md:table-cell">Date</th>
                <th className="px-5 py-3 font-semibold">Status</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {projects.map((p) => (
                <tr key={p.id} className="group border-b border-line/60 transition hover:bg-coal">
                  <td className="max-w-[380px] px-5 py-4">
                    <Link href={`/projects/${p.id}`} className="block truncate font-semibold text-cream group-hover:text-goldsoft">
                      {p.title}
                    </Link>
                    <span className="text-xs text-muted">{p.videos.length} clip{p.videos.length === 1 ? "" : "s"} · {p.settings.tone}</span>
                  </td>
                  <td className="px-5 py-4 font-mono text-xs text-sand">
                    {fmtDuration(p.timeline.reduce((a, i) => a + i.duration, 0) || p.settings.duration_target)}
                  </td>
                  <td className="hidden px-5 py-4 text-xs text-muted md:table-cell">{fmtDate(p.created_at)}</td>
                  <td className="px-5 py-4">
                    <span
                      className={`rounded-sm px-2 py-1 text-[10px] font-bold uppercase tracking-[0.14em] ${
                        p.status === "error"
                          ? "bg-red-900/40 text-red-300"
                          : p.status === "processing"
                          ? "bg-gold/15 text-goldsoft"
                          : p.status === "draft"
                          ? "bg-coal2 text-sand"
                          : "bg-emerald-900/40 text-emerald-300"
                      }`}
                    >
                      {p.render.output_path ? "exported" : p.status}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-right">
                    <button
                      onClick={() => remove(p.id)}
                      className="rounded-sm px-2 py-1 text-xs uppercase tracking-wider text-muted opacity-0 transition hover:bg-red-950 hover:text-red-300 group-hover:opacity-100"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
