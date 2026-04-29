export interface FetchJsonInit {
  method?: string;
  body?: string;
  headers?: Record<string, string>;
  timeoutMs: number;
}

export interface HttpErrorContext {
  status: number;
  text: string;
  detail: unknown;
  message: string;
}

export type HttpErrorMapper = (context: HttpErrorContext) => Error | null;

export async function fetchJson<T>(
  url: string,
  init: FetchJsonInit,
  mapError: HttpErrorMapper = () => null
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), init.timeoutMs);
  try {
    const resp = await fetch(url, {
      method: init.method ?? "GET",
      body: init.body,
      headers: init.headers ?? {},
      signal: controller.signal,
    });
    const text = await resp.text();
    const data = parseJsonText(text);
    if (!resp.ok) {
      throw mappedHttpError(resp.status, text, data, mapError);
    }
    return data as T;
  } finally {
    clearTimeout(timer);
  }
}

function parseJsonText(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return { raw: text };
  }
}

function mappedHttpError(status: number, text: string, data: unknown, mapError: HttpErrorMapper): Error {
  const detail = (data as Record<string, unknown>)?.["detail"];
  const message = detailMessage(detail, text);
  return mapError({ status, text, detail, message }) ?? new Error(`HTTP ${status}: ${message}`);
}

function detailMessage(detail: unknown, text: string): string {
  if (typeof detail === "string") return detail;
  if (typeof detail === "object" && detail !== null) return JSON.stringify(detail);
  return text;
}
