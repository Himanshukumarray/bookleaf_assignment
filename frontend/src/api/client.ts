import axios, { AxiosError } from "axios";

const TOKEN_KEY = "bookleaf.token";

export const tokenStore = {
  get: (): string | null => {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (token: string) => {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      /* storage unavailable: session lasts until reload */
    }
  },
  clear: () => {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
export const WS_URL = import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000/api/v1/ws";

export const api = axios.create({ baseURL: API_BASE_URL, timeout: 70_000 });

let onUnauthorized: (() => void) | null = null;
export const setUnauthorizedHandler = (handler: (() => void) | null) => {
  onUnauthorized = handler;
};

api.interceptors.request.use((config) => {
  const token = tokenStore.get();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const isLogin = error.config?.url?.includes("/auth/login");
    if (error.response?.status === 401 && !isLogin) {
      tokenStore.clear();
      onUnauthorized?.();
    }
    return Promise.reject(error);
  },
);

interface ApiErrorBody {
  error?: { code?: string; message?: string; details?: unknown };
}

export function getErrorMessage(error: unknown, fallback = "Something went wrong. Please try again."): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    if (error.response?.data?.error?.message) return error.response.data.error.message;
    if (!error.response) return "Cannot reach the server. Check your connection.";
  }
  return fallback;
}

export function getErrorCode(error: unknown): string | undefined {
  return axios.isAxiosError<ApiErrorBody>(error) ? error.response?.data?.error?.code : undefined;
}
