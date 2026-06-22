import { useQuery } from "@tanstack/react-query";
import { getCuration } from "@/features/curation/api";

export function useCuration(slug: string) {
  return useQuery({
    queryKey: ["curation", slug],
    queryFn: () => getCuration(slug),
    enabled: !!slug,
  });
}
