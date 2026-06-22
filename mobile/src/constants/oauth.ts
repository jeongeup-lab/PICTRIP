import { Platform } from "react-native";

/** OAuth client config from EXPO_PUBLIC_* env (placeholders until consoles set up).
 * Apple needs no client id (native bundle id is the audience). */
export const OAUTH = {
  google: {
    clientId:
      (Platform.OS === "ios"
        ? process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID
        : process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID) ?? "",
    webClientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID ?? "",
  },
  kakao: {
    restKey: process.env.EXPO_PUBLIC_KAKAO_REST_KEY ?? "",
  },
} as const;
