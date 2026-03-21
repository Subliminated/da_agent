const DEFAULT_API_BASE_URL = "http://localhost:8000";

export const getApiBaseUrl = () => {
  return process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || DEFAULT_API_BASE_URL;
};

type RequestOptions = {
  method?: "GET" | "POST";
  body?: BodyInit | null;
  headers?: HeadersInit;
};

export async function requestJson(path: string, options: RequestOptions = {}) {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: options.method || "GET",
    body: options.body ?? null,
    headers: options.headers,
    cache: "no-store"
  });

  const rawText = await response.text();
  const data = rawText ? tryParseJson(rawText) : null;

  if (!response.ok) {
    throw new Error(formatErrorMessage(response.status, data, rawText));
  }

  return data;
}

function tryParseJson(rawText: string) {
  try {
    return JSON.parse(rawText);
  } catch {
    return rawText;
  }
}

function formatErrorMessage(status: number, data: unknown, rawText: string) {
  if (typeof data === "string" && data) {
    return `Request failed (${status}): ${data}`;
  }

  if (data && typeof data === "object") {
    return `Request failed (${status}): ${JSON.stringify(data, null, 2)}`;
  }

  return `Request failed (${status}): ${rawText || "Unknown error"}`;
}
