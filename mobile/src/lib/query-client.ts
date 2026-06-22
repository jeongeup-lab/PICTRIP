import { QueryClient } from "@tanstack/react-query";
import { AppError } from "@/lib/app-error";

/** 4xx AppErrors are deterministic — never retry them. */
export function isAppError4xx(error: unknown): boolean {
  return error instanceof AppError && error.status >= 400 && error.status < 500;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: (failureCount, error) => {
        if (isAppError4xx(error)) return false;
        return failureCount < 2;
      },
    },
  },
});
