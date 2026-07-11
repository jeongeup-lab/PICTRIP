import { Tabs, router } from "expo-router";
import { Icon, type IconName } from "@/components/Icon";
import { colors } from "@/constants/theme";

function tabIcon(name: IconName) {
  const TabBarIcon = ({ focused }: { focused: boolean }) => (
    <Icon
      name={name}
      size={24}
      color={focused ? colors.accent : colors.ter}
      strokeWidth={focused ? 2 : 1.9}
    />
  );
  TabBarIcon.displayName = `TabBarIcon(${name})`;
  return TabBarIcon;
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.accentText,
        tabBarInactiveTintColor: colors.ter,
        tabBarLabelStyle: { fontSize: 10, fontWeight: "700" },
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
