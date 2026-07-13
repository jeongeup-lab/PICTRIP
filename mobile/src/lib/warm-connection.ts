import { API_BASE } from "@/constants/env";

const HEALTH_URL = API_BASE.replace(/\/v1\/?$/, "") + "/health";

export function warmConnection(): void {
  void fetch(HEALTH_URL, { method: "GET" }).catch(() => {});
}
