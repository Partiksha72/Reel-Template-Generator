"use client";

import type { Project } from "@/lib/types";
import { STEP_LABELS } from "@/lib/types";

const ORDER = ["overview", "transcription", "moments", "story", "clips", "captions", "music", "preview"];

function Dot({ state }: { state: string }) {
  if (state === "done")
    return (
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gold text-[11px] font-black text-ink">
        ✓
      </span>
    );
  if (state === "running")
    return <span className="mt-0.5 inline-block h-5 w-5 shrink-0 animate-pulse-dot rounded-full border-2 border-gold" />;
  if (state === "skipped")
    return (
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-line text-[10px] text-muted">
        –
      </span>
    );
  if (state === "error")
    return (
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-red-900 text-[10px] font-bold text-red-200">
        !
      </span>
    );
  return <span className="mt-0.5 inline-block h-5 w-5 shrink-0 rounded-full border border-line/60" />;
}

export default function ProcessingScreen({ project }: { project: Project }) {
  const running = Object.values(project.steps).some((s) => s.state === "running");
  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <p className="label-caps !text-gold/90">नागरिक · AI Edit in progress</p>
      <h1 className="mt-4 font-display text-4xl uppercase leading-tight tracking-wide text-cream md:text-5xl">
        {running ? "Building your reel…" : "Understanding your story…"}
      </h1>
      <p className="mt-3 text-sm text-muted">
        “{project.title}” — this usually takes under a minute. The page updates automatically.
      </p>

      <div className="panel mt-8 divide-y divide-line">
        {ORDER.map((key) => {
          const step = project.steps[key] ?? { state: "pending", message: "" };
          return (
            <div key={key} className="flex items-start gap-4 px-6 py-4">
              <Dot state={step.state} />
              <div className="min-w-0 flex-1">
                <p
                  className={`text-sm font-semibold ${
                    step.state === "done"
                      ? "text-sand"
                      : step.state === "running"
                      ? "text-goldsoft"
                      : step.state === "error"
                      ? "text-red-300"
                      : "text-muted"
                  }`}
                >
                  {STEP_LABELS[key] ?? key}
                </p>
                {step.message && (
                  <p className="mt-0.5 truncate text-xs text-muted" title={step.message}>
                    {step.message}
                  </p>
                )}
              </div>
              <span className="pt-1 font-display text-[10px] uppercase tracking-[0.2em] text-muted/70">
                {step.state}
              </span>
            </div>
          );
        })}
      </div>

      {/* subtle progress bar */}
      <div className="mt-6 h-1 w-full overflow-hidden bg-coal2">
        <div
          className="h-full bg-gold transition-all duration-500"
          style={{
            width: `${
              (ORDER.filter((k) => ["done", "skipped"].includes(project.steps[k]?.state)).length /
                ORDER.length) *
              100
            }%`,
          }}
        />
      </div>
    </div>
  );
}
