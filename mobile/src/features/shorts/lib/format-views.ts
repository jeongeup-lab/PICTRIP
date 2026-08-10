export function formatViews(count: number): string {
  if (count >= 100_000_000) {
    return `${trimZero((count / 100_000_000).toFixed(1))}억`;
  }
  if (count >= 10_000) {
    return `${trimZero((count / 10_000).toFixed(1))}만`;
  }
  return count.toLocaleString("ko-KR");
}

function trimZero(value: string): string {
  return value.endsWith(".0") ? value.slice(0, -2) : value;
}
