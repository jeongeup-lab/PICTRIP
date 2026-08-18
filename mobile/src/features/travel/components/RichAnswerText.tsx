import { StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "@/constants/theme";

export interface RichPart {
  text: string;
  bold: boolean;
  cite?: number;
}

const CITE = /\[(\d{1,3})\]/g;

/** 카드가 없는 번호는 본문에서 지운다. 모델이 틀린 번호를 써도 화면에 남지 않는다. */
function splitCitations(part: RichPart, spotCount: number): RichPart[] {
  const parts: RichPart[] = [];
  let last = 0;
  let matched = false;
  for (const match of part.text.matchAll(CITE)) {
    matched = true;
    const at = match.index ?? 0;
    const number = Number(match[1]);
    if (at > last) parts.push({ text: part.text.slice(last, at), bold: part.bold });
    if (number >= 1 && number <= spotCount) {
      parts.push({ text: String(number), bold: part.bold, cite: number });
    }
    last = at + match[0].length;
  }
  if (!matched) return [part];
  if (last < part.text.length) parts.push({ text: part.text.slice(last), bold: part.bold });
  return parts;
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

export function parseRichText(text: string, spotCount?: number): RichBlock[] {
  const cited = (parts: RichPart[]): RichPart[] =>
    spotCount === undefined ? parts : parts.flatMap((part) => splitCitations(part, spotCount));
  return text
    .split("\n")
    .map((line) => line.trimEnd())
    .filter((line) => line.trim().length > 0)
    .map((line) =>
      line.startsWith("- ")
        ? { kind: "bullet" as const, parts: cited(parseBold(line.slice(2))) }
        : { kind: "paragraph" as const, parts: cited(parseBold(line)) },
    );
}

function Parts({
  parts,
  onCitePress,
}: {
  parts: RichPart[];
  onCitePress?: (number: number) => void;
}) {
  return (
    <>
      {parts.map((part, index) =>
        part.cite === undefined ? (
          <Text key={`${index}-${part.text}`} style={part.bold ? styles.bold : undefined}>
            {part.text}
          </Text>
        ) : (
          <Text
            key={`${index}-cite-${part.cite}`}
            testID={`answer-cite-${part.cite}`}
            style={styles.cite}
            onPress={() => onCitePress?.(part.cite as number)}
          >
            {`[${part.text}]`}
          </Text>
        ),
      )}
    </>
  );
}

export function RichAnswerText({
  text,
  spotCount,
  onCitePress,
}: {
  text: string;
  spotCount?: number;
  onCitePress?: (number: number) => void;
}) {
  const blocks = parseRichText(text, spotCount);
  if (blocks.length === 0) return null;
  return (
    <View style={styles.root}>
      {blocks.map((block, index) =>
        block.kind === "bullet" ? (
          <View key={index} style={styles.bulletRow}>
            <View style={styles.dot} />
            <Text style={styles.body}>
              <Parts parts={block.parts} onCitePress={onCitePress} />
            </Text>
          </View>
        ) : (
          <Text key={index} style={styles.body}>
            <Parts parts={block.parts} onCitePress={onCitePress} />
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
  cite: { fontWeight: "700", color: colors.accent },
  bulletRow: { flexDirection: "row", alignItems: "flex-start", gap: 8, paddingLeft: 2 },
  dot: {
    width: 4,
    height: 4,
    borderRadius: 2,
    marginTop: 8.5,
    backgroundColor: colors.sec,
  },
});
