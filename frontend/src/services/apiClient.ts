export const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: boolean;
  isFormData?: boolean;
}

let getAccessToken: () => string | null = () => null;
let tryRefresh: () => Promise<boolean> = async () => false;
let onSessionExpired: () => void = () => {};

/** Branché depuis AuthProvider au démarrage — évite une dépendance
 * circulaire entre le client API et le store d'auth. */
export function configureApiClient(opts: {
  getAccessToken: () => string | null;
  tryRefresh: () => Promise<boolean>;
  onSessionExpired: () => void;
}) {
  getAccessToken = opts.getAccessToken;
  tryRefresh = opts.tryRefresh;
  onSessionExpired = opts.onSessionExpired;
}

async function doFetch(path: string, method: string, headers: Record<string, string>, body: unknown, isFormData: boolean) {
  return fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: isFormData ? (body as FormData) : body !== undefined ? JSON.stringify(body) : undefined,
  });
}

async function request<T>(path: string, options: RequestOptions = {}, _isRetry = false): Promise<T> {
  const { method = "GET", body, auth = false, isFormData = false } = options;

  const headers: Record<string, string> = {};
  if (body !== undefined && !isFormData) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await doFetch(path, method, headers, body, isFormData);

  if (response.status === 401 && auth && !_isRetry) {
    // Token expiré : une seule tentative de rafraîchissement silencieux,
    // puis on rejoue la requête d'origine une fois avec le nouveau token.
    const refreshed = await tryRefresh();
    if (refreshed) {
      return request<T>(path, options, true);
    }
    onSessionExpired();
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = data.detail ?? detail;
    } catch {
      // corps non-JSON, on garde le statusText
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string, auth = false) => request<T>(path, { method: "GET", auth }),
  post: <T>(path: string, body?: unknown, auth = false) =>
    request<T>(path, { method: "POST", body, auth }),
  put: <T>(path: string, body?: unknown, auth = true) =>
    request<T>(path, { method: "PUT", body, auth }),
  patch: <T>(path: string, body?: unknown, auth = true) =>
    request<T>(path, { method: "PATCH", body, auth }),
  delete: <T>(path: string, auth = true) => request<T>(path, { method: "DELETE", auth }),
  postForm: <T>(path: string, formData: FormData, auth = true) =>
    request<T>(path, { method: "POST", body: formData, auth, isFormData: true }),
};
