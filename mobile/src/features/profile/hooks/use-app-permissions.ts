import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import * as ImagePicker from "expo-image-picker";
import { getPermissionStatus, type PermStatus } from "@/features/map/usecases/request-location";

export interface AppPermissions {
  location: PermStatus | null;
  photos: PermStatus | null;
  camera: PermStatus | null;
}

export const PERM_LABEL: Record<PermStatus, string> = {
  granted: "허용됨",
  denied: "꺼짐",
  undetermined: "미설정",
};

const EMPTY: AppPermissions = { location: null, photos: null, camera: null };

function toStatus(result: { granted: boolean; canAskAgain: boolean }): PermStatus {
  if (result.granted) return "granted";
  return result.canAskAgain ? "undetermined" : "denied";
}

export function useAppPermissions(withMedia = false): AppPermissions {
  const [perms, setPerms] = useState<AppPermissions>(EMPTY);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      void (async () => {
        try {
          const location = await getPermissionStatus();
          if (!alive) return;
          setPerms((prev) => ({ ...prev, location }));
          if (!withMedia) return;
          const [library, camera] = await Promise.all([
            ImagePicker.getMediaLibraryPermissionsAsync(),
            ImagePicker.getCameraPermissionsAsync(),
          ]);
          if (!alive) return;
          setPerms((prev) => ({
            ...prev,
            photos: toStatus(library),
            camera: toStatus(camera),
          }));
        } catch {
          if (alive) setPerms(EMPTY);
        }
      })();
      return () => {
        alive = false;
      };
    }, [withMedia]),
  );

  return perms;
}
