import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { create } from "zustand";
import { getChannelCards, getChannels, type ChannelKey } from "@/features/channels/api";
import { loadSeen, saveSeen } from "@/features/channels/lib/seen-store";
import { todayKst } from "@/features/channels/lib/kst";

export function useChannels() {
  return useQuery({
    queryKey: ["channels"],
    queryFn: getChannels,
    staleTime: 5 * 60 * 1000,
  });
}

export function channelCardsKey(key: ChannelKey, coords?: { lat: number; lng: number }) {
  return [
    "channel-cards",
    key,
    coords ? [Math.round(coords.lat * 1000), Math.round(coords.lng * 1000)] : null,
  ];
}

export function useChannelCards(key: ChannelKey, coords?: { lat: number; lng: number }) {
  return useQuery({
    queryKey: channelCardsKey(key, coords),
    queryFn: () => getChannelCards(key, coords),
    enabled: key !== "around" || !!coords,
  });
}

interface SeenState {
  seen: Set<ChannelKey>;
  day: string | null;
  hydrated: boolean;
  hydrate: () => Promise<void>;
  markSeen: (k: ChannelKey) => void;
}

export const useSeenStore = create<SeenState>((set, get) => ({
  seen: new Set(),
  day: null,
  hydrated: false,
  hydrate: async () => {
    if (get().hydrated) return;
    const today = todayKst();
    const keys = await loadSeen(today);
    const merged = new Set<ChannelKey>([
      ...(keys as ChannelKey[]),
      ...(get().day === today ? get().seen : []),
    ]);
    set({ seen: merged, day: today, hydrated: true });
    void saveSeen([...merged], today);
  },
  markSeen: (k) => {
    const today = todayKst();
    const base = get().day === today ? get().seen : new Set<ChannelKey>();
    const next = new Set(base);
    next.add(k);
    set({ seen: next, day: today });
    if (get().hydrated) void saveSeen([...next], today);
  },
}));

export function useSeenChannels(): { seen: Set<ChannelKey>; markSeen: (k: ChannelKey) => void } {
  const seen = useSeenStore((s) => s.seen);
  const markSeen = useSeenStore((s) => s.markSeen);
  const hydrate = useSeenStore((s) => s.hydrate);
  useEffect(() => {
    void hydrate();
  }, [hydrate]);
  return { seen, markSeen };
}
