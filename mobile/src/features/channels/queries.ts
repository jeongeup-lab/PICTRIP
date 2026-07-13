import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { create } from "zustand";
import { getChannelCards, getChannels, type ChannelKey } from "@/features/channels/api";
import { loadSeen, saveSeen } from "@/features/channels/lib/seen-store";

function todayKst(): string {
  return new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });
}

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
  hydrated: boolean;
  hydrate: () => Promise<void>;
  markSeen: (k: ChannelKey) => void;
}

const useSeenStore = create<SeenState>((set, get) => ({
  seen: new Set(),
  hydrated: false,
  hydrate: async () => {
    if (get().hydrated) return;
    const keys = await loadSeen(todayKst());
    set({ seen: new Set(keys as ChannelKey[]), hydrated: true });
  },
  markSeen: (k) => {
    const next = new Set(get().seen);
    next.add(k);
    set({ seen: next });
    void saveSeen([...next], todayKst());
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
