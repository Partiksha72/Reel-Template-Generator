"use client";

import { useEffect, useState } from "react";
import { API_URL, getHealth } from "@/lib/api";
import type { HealthInfo } from "@/lib/types";

function ProviderCard({ name, status, envKeys }: { name: string; status?: HealthInfo["providers"]["llm"]; envKeys: string }) {
  const configured = status?.configured ?? false;
  return (
    <div className={`border p-5 ${configured ? "border-emerald-900/50 bg-emerald-950/15" : "border-amber-900/50 bg-amber-950/15"}`}>
      <div className="flex items-center justify-between">
        <h3 className="font-display text-sm uppercase tracking-[0.16em] text-cream">{name}</h3>
        <span
          className={`flex items-center gap-2 rounded-sm px-2 py-1 text-[10px] font-bold uppercase tracking-widest ${
            configured ? "bg-emerald-900/50 text-emerald-300" : "bg-amber-900/40 text-amber-300"
          }`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${configured ? "bg-emerald-400" : "bg-amber-400"}`} />
          {configured ? "Ready" : "Not configured"}
        </span>
      </div>
      <p className="mt-2 text-xs text-muted">
        Provider: <span className="text-sand">{status?.provider ?? "—"}</span>
        {status?.model ? <> · model: <span className="text-sand">{status.model}</span></> : null}
      </p>
      {!configured && status?.hint && (
        <p className="mt-3 border-t border-line pt-3 text-xs leading-relaxed text-amber-200/90">{status.hint}</p>
      )}
      <p className="mt-3 font-mono text-[11px] text-muted">{envKeys}</p>
    </div>
  );
}

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [unreachable, setUnreachable] = useState(false);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setUnreachable(true));
  }, []);

  return (
    <div className="mx-auto max-w-4xl px-6 pb-24">
      <div className="flex items-center gap-4 border-b border-line py-8">
        <h1 className="font-display text-4xl uppercase tracking-wide text-cream">Settings</h1>
        <div className="gold-rule" />
      </div>

      {unreachable && (
        <div className="mt-8 border border-red-900/50 bg-red-950/30 p-6">
          <p className="font-bold text-red-300">Backend unreachable</p>
          <p className="mt-2 text-sm leading-relaxed text-red-200/90">
            Nagrik&apos;s API isn&apos;t responding at <span className="font-mono">{API_URL}</span>. Start it with:
          </p>
          <pre className="mt-3 bg-black/40 p-3 font-mono text-xs leading-relaxed text-sand">{`cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000`}</pre>
        </div>
      )}

      {health && (
        <>
          <section className="mt-8 grid gap-4 md:grid-cols-3">
            <ProviderCard name="AI · Story (LLM)" status={health.providers.llm} envKeys="LLM_API_KEY · LLM_BASE_URL · LLM_MODEL" />
            <ProviderCard name="Transcription (STT)" status={health.providers.stt} envKeys="STT_PROVIDER=local|openai · STT_MODEL" />
            <ProviderCard name="Voiceover (TTS)" status={health.providers.tts} envKeys="TTS_PROVIDER=openai · TTS_API_KEY" />
          </section>

          <section className="mt-6 border border-line bg-coal/60 p-6">
            <h3 className="label-caps mb-3 !text-gold/80">System</h3>
            <div className="grid gap-x-10 gap-y-3 text-sm md:grid-cols-2">
              <div className="flex items-center justify-between border-b border-line/60 pb-2">
                <span className="text-muted">FFmpeg</span>
                <span className={health.ffmpeg.available ? "text-emerald-300" : "text-red-300"}>
                  {health.ffmpeg.available ? `✓ v${health.ffmpeg.version}` : "✗ not found"}
                </span>
              </div>
              <div className="flex items-center justify-between border-b border-line/60 pb-2">
                <span className="text-muted">Max upload size</span>
                <span className="text-sand">{health.limits.max_upload_mb} MB</span>
              </div>
              <div className="flex items-center justify-between border-b border-line/60 pb-2">
                <span className="text-muted">API base URL</span>
                <span className="font-mono text-xs text-sand">{API_URL}</span>
              </div>
              <div className="flex items-center justify-between border-b border-line/60 pb-2">
                <span className="text-muted">Output format</span>
                <span className="text-sand">MP4 · H.264 · 1080×1920</span>
              </div>
            </div>
            {!health.ffmpeg.available && (
              <p className="mt-4 border-l-2 border-red-500 pl-3 text-xs leading-relaxed text-red-200">
                Install FFmpeg to enable processing &amp; export:
                <br />macOS: <code>brew install ffmpeg</code> · Debian: <code>sudo apt install ffmpeg</code> · Windows:{" "}
                <code>winget install Gyan.FFmpeg</code>
              </p>
            )}
          </section>

          <section className="mt-6 border border-line bg-coal/60 p-6">
            <h3 className="label-caps mb-3 !text-gold/80">Music library (royalty-free)</h3>
            <div className="flex flex-wrap gap-2">
              {health.music_categories.map((c) => (
                <span key={c.id} className="border border-line bg-coal2 px-3 py-1.5 text-xs text-sand">
                  {c.label} <span className="text-muted">· {c.tracks.length} track{c.tracks.length > 1 ? "s" : ""}</span>
                </span>
              ))}
            </div>
            <p className="mt-3 text-xs leading-relaxed text-muted">
              All beds are synthesized locally — safe for commercial use. Add your own royalty-free files in{" "}
              <code className="font-mono">backend/app/assets/music/</code>.
            </p>
          </section>

          <section className="mt-6 border border-line bg-coal/60 p-6">
            <h3 className="label-caps mb-3 !text-gold/80">Fact safety policy</h3>
            <ul className="list-disc space-y-1.5 pl-5 text-xs leading-relaxed text-sand">
              <li>Nagrik only writes from facts present in your overview — never fabricated statistics, quotes or names.</li>
              <li>Every reel keeps an audit trail: <em>source facts</em> vs <em>creative copy</em>, visible in the editor.</li>
              <li>Facts that can&apos;t be traced back to your overview are flagged for review.</li>
              <li>Missing information is phrased neutrally, never filled in.</li>
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
