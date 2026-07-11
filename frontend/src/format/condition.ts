import type { ConditionCode } from "../contract/conditionCodes";

const CONDITION_LABELS: Record<ConditionCode, string> = {
  CLEAR: "Sunny",
  MAINLY_CLEAR: "Mostly Sunny",
  PARTLY_CLOUDY: "Partly Cloudy",
  CLOUDY: "Cloudy",
  FOG: "Foggy",
  DRIZZLE: "Drizzling",
  FREEZING_DRIZZLE: "Freezing Drizzle",
  RAIN: "Rainy",
  HEAVY_RAIN: "Heavy Rain",
  FREEZING_RAIN: "Freezing Rain",
  SNOW: "Snowy",
  HEAVY_SNOW: "Heavy Snow",
  RAIN_SHOWERS: "Rain Showers",
  SNOW_SHOWERS: "Snow Showers",
  THUNDERSTORM: "Thunderstorms",
  UNKNOWN: "Unknown",
};

export function conditionLabel(code: ConditionCode): string {
  return CONDITION_LABELS[code];
}
