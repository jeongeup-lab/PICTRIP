import type { ColorValue } from "react-native";
import { Tabs, router } from "expo-router";
import { Icon, type IconName } from "@/components/Icon";
import { colors } from "@/constants/theme";

function tabIcon(name: IconName) {
  const TabBarIcon = ({ color }: { color: ColorValue }) => (
    <Icon name={name} size={24} color={color} />
  );
  TabBarIcon.displayName = `TabBarIcon(${name})`;
  return TabBarIcon;
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.ink,
        tabBarInactiveTintColor: colors.ter,
        tabBarStyle: { borderTopColor: colors.line },
      }}
    >
      <Tabs.Screen name="index" options={{ title: "홈", tabBarIcon: tabIcon("home") }} />
      <Tabs.Screen name="map" options={{ title: "지도", tabBarIcon: tabIcon("map-pin") }} />
      <Tabs.Screen
        name="photo"
        options={{ title: "사진", tabBarIcon: tabIcon("camera") }}
        listeners={{
          tabPress: (e) => {
            e.preventDefault();
            router.push("/photo/select");
          },
        }}
      />
      <Tabs.Screen name="profile" options={{ title: "마이", tabBarIcon: tabIcon("person") }} />
    </Tabs>
  );
}
