export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function isUnauthorizedApiError(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 401;
}

export function formatApiErrorDetail(error: unknown): string | null {
  if (!(error instanceof ApiError)) {
    return error instanceof Error ? error.message : null;
  }

  if (typeof error.body === "object" && error.body && "detail" in error.body) {
    const detail = error.body.detail;
    return typeof detail === "string" ? detail : JSON.stringify(detail);
  }

  if (typeof error.body === "string") {
    return error.body;
  }

  return null;
}

const apiBaseUrl = getApiBaseUrl();

function getApiBaseUrl() {
  const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (configuredApiBaseUrl && configuredApiBaseUrl !== "same-origin") {
    return configuredApiBaseUrl.replace(/\/$/, "");
  }
  if (typeof window !== "undefined") {
    if (window.location.hostname.endsWith(".onrender.com")) {
      return "";
    }
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "";
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    }
  });

  if (!response.ok) {
    const body = await readResponseBody(response);
    throw new ApiError(`API request failed: ${response.status}`, response.status, body);
  }

  return response.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    credentials: "include",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    },
    body: JSON.stringify(body)
  });

  if (!response.ok) {
    const responseBody = await readResponseBody(response);
    throw new ApiError(`API request failed: ${response.status}`, response.status, responseBody);
  }

  return response.json() as Promise<T>;
}

export async function apiPut<T>(path: string, body: unknown, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    credentials: "include",
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    },
    body: JSON.stringify(body)
  });

  if (!response.ok) {
    const responseBody = await readResponseBody(response);
    throw new ApiError(`API request failed: ${response.status}`, response.status, responseBody);
  }

  return response.json() as Promise<T>;
}

async function readResponseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}
