export function ratingColor(value: number): string {
  if (value < 50) return "#ff5a6f";
  if (value < 75) return "#ffd24d";
  return "#55d6a7";
}
