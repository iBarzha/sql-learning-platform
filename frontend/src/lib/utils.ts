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

  // Field-level errors: { field: ["error1", "error2"] } or { field: "error" }
  for (const value of Object.values(data)) {
    if (typeof value === 'string') return value;
    if (Array.isArray(value) && typeof value[0] === 'string') return value[0];
  }

  return defaultMessage;
}
