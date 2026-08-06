import { router } from "expo-router";
import { TravelMapView } from "@/features/travel/components/TravelMapView";
import { useTravelMap } from "@/features/travel/stores/map-store";

export default function TravelMapScreen() {
  const spots = useTravelMap((s) => s.spots);
  const question = useTravelMap((s) => s.question);
  const selectedId = useTravelMap((s) => s.selectedId);
  const select = useTravelMap((s) => s.select);

  return (
    <TravelMapView
      spots={spots}
      question={question}
      selectedId={selectedId}
      onSelect={select}
      onClose={() => router.back()}
    />
  );
}
