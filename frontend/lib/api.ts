import { getAccessToken, setAccessToken } from "@/lib/auth";

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  /** Don't attach the access token (used for login/refresh themselves). */
  skipAuth?: boolean;
  /** Internal: prevents infinite refresh loops. */
  skipRetry?: boolean;
};

async function parseError(response: Response): Promise<never> {
  let code = "unknown_error";
  let message = "Something went wrong. Please try again.";
  try {
    const data = await response.json();
    code = data?.error?.code ?? code;
    message = data?.error?.message ?? message;
  } catch {
    // Response had no JSON body; fall back to the defaults above.
  }
  throw new ApiError(code, message, response.status);
}

async function rawRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, skipAuth } = options;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const token = getAccessToken();
  if (token && !skipAuth) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`/api/v1${path}`, {
    method,
    headers,
    credentials: "include",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

let refreshPromise: Promise<string | null> | null = null;

function refreshAccessToken(): Promise<string | null> {
  refreshPromise ??= rawRequest<{ access_token: string }>("/auth/refresh", {
    method: "POST",
    skipAuth: true,
  })
    .then((data) => {
      setAccessToken(data.access_token);
      return data.access_token;
    })
    .catch(() => {
      setAccessToken(null);
      return null;
    })
    .finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
}

/** The access token is short-lived (~15 min); a 401 triggers one silent refresh-and-retry. */
async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  try {
    return await rawRequest<T>(path, options);
  } catch (error) {
    const canRetry = error instanceof ApiError && error.status === 401 && !options.skipRetry && !options.skipAuth;
    if (!canRetry) throw error;

    const newToken = await refreshAccessToken();
    if (!newToken) throw error;
    return rawRequest<T>(path, { ...options, skipRetry: true });
  }
}

export const api = {
  get: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) =>
    apiRequest<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    apiRequest<T>(path, { ...options, method: "POST", body }),
  patch: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    apiRequest<T>(path, { ...options, method: "PATCH", body }),
  delete: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) =>
    apiRequest<T>(path, { ...options, method: "DELETE" }),
};
