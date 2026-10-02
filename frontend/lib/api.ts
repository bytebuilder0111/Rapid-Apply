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
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  /** Don't attach the access token (used for login/refresh themselves). */
  skipAuth?: boolean;
  /** Internal: prevents infinite refresh loops. */
  skipRetry?: boolean;
};

async function parseError(response: Response): Promise<never> {
  let code = "unknown_error";
  let message = `Something went wrong (HTTP ${response.status}). Please try again.`;
  try {
    const data = await response.json();
    if (data?.error) {
      code = data.error.code ?? code;
      message = data.error.message ?? message;
    } else if (data?.detail) {
      // FastAPI's own request-validation (422) and routing errors use `detail`.
      code = "request_error";
      message = Array.isArray(data.detail)
        ? `Invalid request: ${data.detail.map((d: { msg?: string }) => d.msg).join("; ")}`
        : String(data.detail);
    }
  } catch {
    // No JSON body: usually the API server is down or unreachable through the proxy.
    if (response.status >= 500) {
      message = `The API server didn't respond properly (HTTP ${response.status}). Is the backend running?`;
    }
  }
  throw new ApiError(code, message, response.status);
}

async function rawRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, skipAuth } = options;
  const headers: Record<string, string> = {};
  const isForm = body instanceof FormData;
  // For FormData the browser sets the multipart Content-Type (with its boundary) itself.
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";

  const token = getAccessToken();
  if (token && !skipAuth) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`/api/v1${path}`, {
    method,
    headers,
    credentials: "include",
    body: isForm ? body : body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Fired when the session can't be renewed (e.g. an admin signed this user out). */
export const SESSION_ENDED_EVENT = "session-ended";

let refreshPromise: Promise<string | null> | null = null;

/** The new access token, or null once the server says the session is over (401). Any other
 * failure (the API waking up, a timeout, a 5xx) is thrown: it's not a reason to sign out. */
function refreshAccessToken(): Promise<string | null> {
  refreshPromise ??= rawRequest<{ access_token: string }>("/auth/refresh", {
    method: "POST",
    skipAuth: true,
  })
    .then((data) => {
      setAccessToken(data.access_token);
      return data.access_token;
    })
    .catch((error) => {
      if (!(error instanceof ApiError && error.status === 401)) throw error;
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
    if (!newToken) {
      window.dispatchEvent(new Event(SESSION_ENDED_EVENT));
      throw error;
    }
    return rawRequest<T>(path, { ...options, skipRetry: true });
  }
}

export const api = {
  get: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) =>
    apiRequest<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    apiRequest<T>(path, { ...options, method: "POST", body }),
  put: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    apiRequest<T>(path, { ...options, method: "PUT", body }),
  patch: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    apiRequest<T>(path, { ...options, method: "PATCH", body }),
  delete: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) =>
    apiRequest<T>(path, { ...options, method: "DELETE" }),
};
