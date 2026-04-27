import { API_BASE_URL } from "./config";
import type { ApiError, ApiErrorCode, ErrorPayload, FieldErrors } from "./types";

type ApiRequestOptions = Omit<RequestInit, "body" | "credentials"> & {
  body?: unknown;
  query?: Record<string, string | number | boolean | null | undefined>;
};

const CSRF_HEADER_NAME = "X-CSRF-TOKEN";
const CSRF_COOKIE_NAMES = ["csrf_access_token", "csrf_refresh_token"] as const;

function readCookie(name: string): string | null {
  if (typeof document === "undefined") {
    return null;
  }

  const encodedName = `${encodeURIComponent(name)}=`;
  const parts = document.cookie.split(";");

  for (const rawPart of parts) {
    const part = rawPart.trim();
    if (!part.startsWith(encodedName)) {
      continue;
    }

    return decodeURIComponent(part.slice(encodedName.length));
  }

  return null;
}

function readCsrfTokenFromCookie(): string | null {
  for (const cookieName of CSRF_COOKIE_NAMES) {
    const token = readCookie(cookieName);
    if (token && token.trim().length > 0) {
      return token;
    }
  }

  return null;
}

function buildUrl(path: string, query?: ApiRequestOptions["query"]): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = new URL(`${API_BASE_URL}${normalizedPath}`);

  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === "") {
        continue;
      }
      url.searchParams.set(key, String(value));
    }
  }

  return url.toString();
}

function isJsonResponse(response: Response): boolean {
  return response.headers.get("content-type")?.includes("application/json") ?? false;
}

async function parseResponseBody(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return null;
  }

  if (isJsonResponse(response)) {
    return response.json();
  }

  const text = await response.text();
  return text.length > 0 ? { detail: text } : null;
}

function getErrorCode(status: number): ApiErrorCode {
  switch (status) {
    case 400:
      return "bad_request";
    case 401:
      return "unauthorized";
    case 403:
      return "forbidden";
    case 404:
      return "not_found";
    case 409:
      return "conflict";
    case 422:
      return "validation";
    case 429:
      return "rate_limited";
    default:
      return status >= 500 ? "server_error" : "unknown";
  }
}

function normalizeFieldErrors(message: string, status: number): FieldErrors | undefined {
  if (status !== 422) {
    return undefined;
  }

  const segments = message
    .split(";")
    .map((segment) => segment.trim())
    .filter(Boolean);

  if (segments.length === 0) {
    return undefined;
  }

  const fieldErrors: FieldErrors = {};

  for (const segment of segments) {
    const separatorIndex = segment.indexOf(":");
    const key =
      separatorIndex > -1 ? segment.slice(0, separatorIndex).trim() : "form";
    const value =
      separatorIndex > -1 ? segment.slice(separatorIndex + 1).trim() : segment;

    if (!fieldErrors[key]) {
      fieldErrors[key] = [];
    }
    fieldErrors[key].push(value);
  }

  return fieldErrors;
}

function buildApiError(status: number, payload: unknown): ApiError {
  const body = (payload ?? {}) as Partial<ErrorPayload> & Record<string, unknown>;
  const message =
    typeof body.detail === "string" && body.detail.trim().length > 0
      ? body.detail
      : "Something went wrong while talking to the server.";

  return {
    name: "ApiError",
    status,
    code: getErrorCode(status),
    message,
    fieldErrors: normalizeFieldErrors(message, status),
    details: payload,
  };
}

export async function apiRequest<TResponse>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<TResponse> {
  const { body, headers, query, ...init } = options;
  const requestHeaders = new Headers(headers);
  const method = (init.method ?? "GET").toUpperCase();

  if (body !== undefined && !requestHeaders.has("Content-Type")) {
    requestHeaders.set("Content-Type", "application/json");
  }

  if (!requestHeaders.has("Accept")) {
    requestHeaders.set("Accept", "application/json");
  }

  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrfToken = readCsrfTokenFromCookie();
    if (csrfToken && !requestHeaders.has(CSRF_HEADER_NAME)) {
      requestHeaders.set(CSRF_HEADER_NAME, csrfToken);
    }
  }

  const response = await fetch(buildUrl(path, query), {
    ...init,
    headers: requestHeaders,
    credentials: "include",
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const payload = await parseResponseBody(response);

  if (!response.ok) {
    throw buildApiError(response.status, payload);
  }

  return payload as TResponse;
}

export function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    (error as ApiError).name === "ApiError"
  );
}
