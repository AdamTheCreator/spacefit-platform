import axios, { AxiosError } from 'axios';

// Strip a trailing `/api/v1` (with optional slash) so a misconfigured env var
// that already includes the prefix — e.g. `https://host/api/v1` — doesn't
// produce `/api/v1/api/v1/...` 404s for every call. The contract in
// .env.example is host-only, but prod deploys have historically tripped on
// this, so normalize defensively.
const rawApiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_URL = rawApiUrl.replace(/\/api\/v1\/?$/, '');

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
});

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: Error) => void;
}> = [];

const processQueue = (error: Error | null, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else if (token) {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Per-request correlation ID. Generated client-side and sent as
// X-Request-ID so the server can adopt the same ID in its logs and
// return it in its response headers. Makes it possible to grep a
// single user action through both stacks.
const newRequestId = (): string => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID().replace(/-/g, '');
  }
  return `rid-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
};

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    if (config.headers && !config.headers['X-Request-ID']) {
      config.headers['X-Request-ID'] = newRequestId();
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// A refresh failure is only destructive (wipes tokens, redirects to /login)
// if the server actually rejected the refresh token. Network errors /
// timeouts / 5xx are transient and should *not* log the user out — the
// token is still good, the DB just didn't answer in time. Returning
// without wiping lets the next navigation retry cleanly.
const isAuthoritativeRefreshRejection = (err: unknown): boolean => {
  const ax = err as AxiosError | undefined;
  const status = ax?.response?.status;
  return status === 401 || status === 403;
};

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as typeof error.config & {
      _retry?: boolean;
    };

    // Surface server request_id on 5xx so field debugging can correlate
    // the client error with a backend log line. Harmless on 4xx (no-op
    // when the header is absent).
    if (error.response && error.response.status >= 500) {
      const serverRid =
        (error.response.headers?.['x-request-id'] as string | undefined) ??
        ((error.response.data as { request_id?: string } | undefined)?.request_id);
      if (serverRid) {
        console.error(
          `[api] ${error.config?.method?.toUpperCase()} ${error.config?.url} → ${error.response.status} request_id=${serverRid}`
        );
      }
    }

    if (!originalRequest) {
      return Promise.reject(error);
    }

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
            }
            return api(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem('refresh_token');

      if (!refreshToken) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        // Wipe persisted zustand auth state too — otherwise LoginPage hydrates
        // with isAuthenticated:true and ping-pongs us back to /dashboard.
        localStorage.removeItem('auth-storage');
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        const response = await axios.post(
          `${API_URL}/api/v1/auth/refresh`,
          { refresh_token: refreshToken },
          { headers: { 'X-Request-ID': newRequestId() } }
        );

        const { access_token, refresh_token } = response.data;
        localStorage.setItem('access_token', access_token);
        localStorage.setItem('refresh_token', refresh_token);

        processQueue(null, access_token);

        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
        }
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError as Error, null);
        // Only destroy the session on an *authoritative* refresh rejection
        // (401/403 from /auth/refresh). Transient failures — network
        // errors, timeouts, 5xx from a cold DB — leave tokens in place
        // so the next nav can retry. Without this the user gets kicked
        // to /login every time the backend has a slow cold start.
        if (isAuthoritativeRefreshRejection(refreshError)) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          localStorage.removeItem('auth-storage');
          window.location.href = '/login';
        } else {
          console.warn('[api] refresh failed transiently; keeping session', refreshError);
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default api;
