import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

interface ApiErrorResponse {
  response?: {
    data?: {
      detail?: string;
    };
  };
}

export function getApiErrorMessage(error: unknown, defaultMessage = 'An error occurred'): string {
  return (error as ApiErrorResponse)?.response?.data?.detail || defaultMessage;
}
