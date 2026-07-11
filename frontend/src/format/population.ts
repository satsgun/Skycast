export function formatPopulation(population: number): string {
  if (population >= 1_000_000) {
    const millions = (population / 1_000_000).toFixed(1).replace(/\.0$/, "");
    return `${millions}M`;
  }
  if (population >= 1_000) {
    return `${Math.round(population / 1_000)}k`;
  }
  return `${population}`;
}
