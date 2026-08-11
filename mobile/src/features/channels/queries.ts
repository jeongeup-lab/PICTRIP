import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { create } from "zustand";
import { Image } from "expo-image";
import { fullSizeSourceUri } from "@/components/RemoteImage";
import { getChannelCards, getChannels, type ChannelKey } from "@/features/channels/api";
import { loadSeen, saveSeen } from "@/features/channels/lib/seen-store";
import { todayKst } from "@/features/channels/lib/kst";
import { queryClient } from "@/lib/query-client";

export function useChannels() {
  return useQuery({
    queryKey: ["channels"],
    queryFn: getChannels,
    staleTime: 5 * 60 * 1000,
  });
}

export function channelCardsKey(key: ChannelKey) {
  return ["channel-cards", key];
}

export function useChannelCards(key: ChannelKey) {
  return useQuery({
    queryKey: channelCardsKey(key),
    queryFn: () => getChannelCards(key),
  });
}

export function prefetchChannelCards(key: ChannelKey) {
  void queryClient
    .prefetchQuery({
      queryKey: channelCardsKey(key),
      queryFn: () => getChannelCards(key),
    })
    .then(() => {
      const data = queryClient.getQueryData<Awaited<ReturnType<typeof getChannelCards>>>(
        channelCardsKey(key),
      );
      const first = data?.cards[0]?.imageUrl;
      if (first) void Image.prefetch(fullSizeSourceUri(first), { cachePolicy: "memory-disk" });
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
    const today = todayKst();
    if (get().hydrated && get().day === today) return;
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
  const storeSeen = useSeenStore((s) => s.seen);
  const storeDay = useSeenStore((s) => s.day);
  const markSeen = useSeenStore((s) => s.markSeen);
  const hydrate = useSeenStore((s) => s.hydrate);
  const today = todayKst();
  useEffect(() => {
    void hydrate();
  }, [hydrate, today]);
  const seen = storeDay === today ? storeSeen : new Set<ChannelKey>();
  return { seen, markSeen };
}
