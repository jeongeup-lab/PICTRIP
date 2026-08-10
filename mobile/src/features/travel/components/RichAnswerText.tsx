import { StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "@/constants/theme";

export interface RichPart {
  text: string;
  bold: boolean;
}

export interface RichBlock {
  kind: "paragraph" | "bullet";
  parts: RichPart[];
}

export function parseBold(text: string): RichPart[] {
  const parts: RichPart[] = [];
  let rest = text;
  for (;;) {
    const open = rest.indexOf("**");
    if (open < 0) break;
    const close = rest.indexOf("**", open + 2);
    if (close < 0) break;
    if (open > 0) parts.push({ text: rest.slice(0, open), bold: false });
    const inner = rest.slice(open + 2, close);
    if (inner) parts.push({ text: inner, bold: true });
    rest = rest.slice(close + 2);
  }
  if (rest) parts.push({ text: rest, bold: false });
  return parts;
}

export function parseRichText(text: string): RichBlock[] {
  return text
    .split("\n")
    .map((line) => line.trimEnd())
    .filter((line) => line.trim().length > 0)
    .map((line) =>
      line.startsWith("- ")
        ? { kind: "bullet" as const, parts: parseBold(line.slice(2)) }
        : { kind: "paragraph" as const, parts: parseBold(line) },
    );
}

function Parts({ parts }: { parts: RichPart[] }) {
  return (
    <>
      {parts.map((part, index) => (
        <Text key={`${index}-${part.text}`} style={part.bold ? styles.bold : undefined}>
          {part.text}
        </Text>
      ))}
    </>
  );
}

export function RichAnswerText({ text }: { text: string }) {
  const blocks = parseRichText(text);
  if (blocks.length === 0) return null;
  return (
    <View style={styles.root}>
      {blocks.map((block, index) =>
        block.kind === "bullet" ? (
          <View key={index} style={styles.bulletRow}>
            <View style={styles.dot} />
            <Text style={styles.body}>
              <Parts parts={block.parts} />
            </Text>
          </View>
        ) : (
          <Text key={index} style={styles.body}>
            <Parts parts={block.parts} />
          </Text>
        ),
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { gap: spacing.xs },
  body: {
    flexShrink: 1,
    fontSize: 14,
    fontWeight: "500",
    lineHeight: 21,
    letterSpacing: -0.25,
    color: colors.ink,
  },
  bold: { fontWeight: "800" },
  bulletRow: { flexDirection: "row", alignItems: "flex-start", gap: 8, paddingLeft: 2 },
  dot: {
    width: 4,
    height: 4,
    borderRadius: 2,
    marginTop: 8.5,
    backgroundColor: colors.sec,
  },
});
