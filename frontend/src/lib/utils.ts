import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

interface ApiErrorResponse {
  response?: {
    data?: Record<string, unknown>;
  };
}

export function getApiErrorMessage(error: unknown, defaultMessage = 'An error occurred'): string {
  const data = (error as ApiErrorResponse)?.response?.data;
  if (!data) return defaultMessage;

  // Direct detail string
  if (typeof data.detail === 'string') return data.detail;

  // Field-level errors: { field: ["error1", "error2"] } or { field: "error" }, possibly
  // nested for list fields: { exercises: [{ criteria: ["error"] }] }.
  const first = firstString(data, 0);
  return first ?? defaultMessage;
}

function firstString(value: unknown, depth: number): string | null {
  if (typeof value === 'string') return value;
  if (depth > 4 || value === null || typeof value !== 'object') return null;
  for (const inner of Object.values(value as Record<string, unknown>)) {
    const found = firstString(inner, depth + 1);
    if (found) return found;
  }
  return null;
}
