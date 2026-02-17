// Shared HTTP utilities for generated clients and hooks

export type ApiError = {
  status: number;
  message: string;
  details?: unknown;
};

const apiBase = (import.meta.env.VITE_API_URL as string | undefined) ?? '';
const apiPrefix = (import.meta.env.VITE_API_PREFIX as string | undefined) ?? '/api';

export const buildUrl = (path: string) => `${apiBase}${apiPrefix}${path}`;

export async function http<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(buildUrl(path), {
    headers: { 'Content-Type': 'application/json', ...(options?.headers ?? {}) },
    ...options,
  });

  if (!response.ok) {
    let message = response.statusText;
    let details: unknown;
    try {
      const text = await response.text();
      message = text || response.statusText;
    } catch (error) {
      details = error;
    }

    const apiError: ApiError = { status: response.status, message, details };
    throw apiError;
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
