import { File, Paths } from "expo-file-system";
import type { Plan } from "@/features/plan/api";
import { planThumb, planTitle, totalSlots } from "@/features/plan/lib/plan-format";

export type RecentPlan = {
  id: string;
  title: string;
  days: number;
  count: number;
  thumb: string | null;
};

const FILE_NAME = "recent-plans.json";
const MAX_ENTRIES = 20;

export function toRecentPlan(plan: Plan): RecentPlan | null {
  if (!plan.planId) return null;
  return {
    id: plan.planId,
    title: planTitle(plan),
    days: plan.days.length,
    count: totalSlots(plan),
    thumb: planThumb(plan),
  };
}

export function mergeRecent(list: RecentPlan[], entry: RecentPlan): RecentPlan[] {
  return [entry, ...list.filter((p) => p.id !== entry.id)].slice(0, MAX_ENTRIES);
}

export function recentSubtitle(entry: RecentPlan): string {
  const visits = entry.count > 0 ? `${entry.count}곳 방문` : "";
  if (entry.days <= 1) return visits || "당일 코스";
  const duration = `${entry.days - 1}박 ${entry.days}일`;
  return visits ? `${duration} · ${visits}` : duration;
}

function isRecentPlan(value: unknown): value is RecentPlan {
  const entry = value as RecentPlan | null;
  return (
    !!entry &&
    typeof entry.id === "string" &&
    typeof entry.title === "string" &&
    typeof entry.days === "number" &&
    typeof entry.count === "number"
  );
}

export function parseRecentPlans(raw: string): RecentPlan[] {
  const parsed: unknown = JSON.parse(raw);
  return Array.isArray(parsed) ? parsed.filter(isRecentPlan) : [];
}

export function readRecentPlans(): RecentPlan[] {
  try {
    const file = new File(Paths.document, FILE_NAME);
    if (!file.exists) return [];
    return parseRecentPlans(file.textSync());
  } catch {
    return [];
  }
}

export function writeRecentPlans(list: RecentPlan[]): void {
  try {
    const file = new File(Paths.document, FILE_NAME);
    if (!file.exists) file.create();
    file.write(JSON.stringify(list));
  } catch {}
}
