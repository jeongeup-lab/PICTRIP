export function makeSeed(): string {
  return Math.random().toString(36).slice(2, 14);
}
