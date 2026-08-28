import type { Project, ProjectSettings } from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function mediaUrl(projectId: string, relPath: string): string {
  return `${API_URL}/api/media/${projectId}/${relPath}`;
}

async function handle<T>(resOrPromise: Response | Promise<Response>): Promise<T> {
  const res = await resOrPromise;
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    let hint = "";
    try {
      const data = await res.json();
      if (typeof data.detail === "string") {
        try {
          const parsed = JSON.parse(data.detail);
          message = parsed.message || message;
          hint = parsed.hint || "";
        } catch {
          message = data.detail;
        }
      } else if (data.message) {
        message = data.message;
        hint = data.hint || "";
      }
    } catch {
      /* ignore */
    }
    const err = new Error(message) as Error & { hint?: string; status?: number };
    err.hint = hint;
    err.status = res.status;
    throw err;
  }
  return res.json() as Promise<T>;
}

export async function getHealth() {
  return handle<import("./types").HealthInfo>(
    fetch(`${API_URL}/api/health`, { cache: "no-store" })
  );
}

export async function listProjects(): Promise<Project[]> {
  return handle<Project[]>(fetch(`${API_URL}/api/projects`, { cache: "no-store" }));
}

export async function getProject(id: string): Promise<Project> {
  return handle<Project>(fetch(`${API_URL}/api/projects/${id}`, { cache: "no-store" }));
}

export async function createProject(body: {
  title: string;
  overview: string;
  settings: ProjectSettings;
}): Promise<Project> {
  return handle<Project>(
    fetch(`${API_URL}/api/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
}

export async function deleteProject(id: string): Promise<void> {
  await handle(fetch(`${API_URL}/api/projects/${id}`, { method: "DELETE" }));
}

export async function uploadVideos(
  id: string,
  files: File[],
  onProgress?: (pct: number, name: string) => void
): Promise<{ videos: Project["videos"]; errors: { file: string; message: string }[] }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress)
        onProgress(Math.round((e.loaded / e.total) * 100), files[0]?.name ?? "");
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        let msg = "Upload failed";
        let hint = "";
        try {
          const data = JSON.parse(xhr.responseText);
          msg = typeof data.detail === "string" ? data.detail : msg;
        } catch {
          /* ignore */
        }
        reject(Object.assign(new Error(msg), { hint }));
      }
    };
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.open("POST", `${API_URL}/api/projects/${id}/videos`);
    xhr.send(form);
  });
}

export async function generateReel(id: string): Promise<void> {
  await handle(fetch(`${API_URL}/api/projects/${id}/generate`, { method: "POST" }));
}

export async function saveTimeline(id: string, items: Project["timeline"]) {
  return handle<{ ok: boolean }>(
    fetch(`${API_URL}/api/projects/${id}/timeline`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items }),
    })
  );
}

export async function regenerate(
  id: string,
  kind: "story" | "captions" | "section",
  sectionIndex?: number,
  instruction?: string
): Promise<Project> {
  const url =
    kind === "section"
      ? `${API_URL}/api/projects/${id}/regenerate/section/${sectionIndex}`
      : `${API_URL}/api/projects/${id}/regenerate/${kind}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction: instruction ?? "" }),
  });
  const data = await handle<{ ok: boolean; project: Project }>(res);
  return data.project;
}

export async function setMusic(id: string, category: string) {
  return handle<{ ok: boolean; music: unknown }>(
    fetch(`${API_URL}/api/projects/${id}/music`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category }),
    })
  );
}

export async function setCaptionStyle(id: string, style: string) {
  return handle<{ ok: boolean }>(
    fetch(`${API_URL}/api/projects/${id}/caption-style`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ style }),
    })
  );
}

export async function exportReel(id: string) {
  return handle<{ ok: boolean; status: string }>(
    fetch(`${API_URL}/api/projects/${id}/export`, { method: "POST" })
  );
}

export async function cancelExport(id: string) {
  return handle<{ ok: boolean }>(
    fetch(`${API_URL}/api/projects/${id}/export/cancel`, { method: "POST" })
  );
}
