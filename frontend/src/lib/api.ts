// Thin fetch wrapper. Every call sends the CSRF header the backend requires for unsafe methods.

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
  /** Field-level validation errors from 422 responses: { field: message } */
  get fieldErrors(): Record<string, string> {
    if (!Array.isArray(this.detail)) return {};
    const out: Record<string, string> = {};
    for (const e of this.detail as { field?: string; message?: string; loc?: string[]; msg?: string }[]) {
      const field = e.field ?? e.loc?.[e.loc.length - 1];
      if (field) out[field] = e.message ?? e.msg ?? "invalid";
    }
    return out;
  }
}

type Options = { method?: string; body?: unknown; form?: FormData; query?: Record<string, string | undefined> };

export async function api<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  const headers: Record<string, string> = { "X-Requested-With": "anamnesis", Accept: "application/json" };
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let url = path;
  if (opts.query) {
    const qs = new URLSearchParams(
      Object.entries(opts.query).filter((e): e is [string, string] => e[1] !== undefined && e[1] !== ""),
    ).toString();
    if (qs) url += `?${qs}`;
  }
  const res = await fetch(url, { method: opts.method ?? "GET", headers, body, credentials: "same-origin" });
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      detail = (await res.json()).detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.detail === "string") return e.detail;
    const fe = Object.entries(e.fieldErrors);
    if (fe.length) return fe.map(([k, v]) => `${k}: ${v}`).join("; ");
    return e.message;
  }
  return e instanceof Error ? e.message : String(e);
}

export const storage = {
  get(key: string): string | null {
    try {
      return window.localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set(key: string, value: string) {
    try {
      window.localStorage.setItem(key, value);
    } catch {
      /* private mode etc. */
    }
  },
};
