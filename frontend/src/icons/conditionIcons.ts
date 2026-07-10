import type { ConditionCode } from "../contract/conditionCodes";

export type IconName =
  | "clear-day"
  | "clear-night"
  | "mainly-clear-day"
  | "mainly-clear-night"
  | "partly-cloudy"
  | "cloudy"
  | "fog"
  | "drizzle"
  | "freezing-drizzle"
  | "rain"
  | "heavy-rain"
  | "freezing-rain"
  | "snow"
  | "heavy-snow"
  | "rain-showers"
  | "snow-showers"
  | "thunderstorm"
  | "unknown";

const CONDITION_ICON_MAP: Record<ConditionCode, IconName> = {
  CLEAR: "clear-day",
  MAINLY_CLEAR: "mainly-clear-day",
  PARTLY_CLOUDY: "partly-cloudy",
  CLOUDY: "cloudy",
  FOG: "fog",
  DRIZZLE: "drizzle",
  FREEZING_DRIZZLE: "freezing-drizzle",
  RAIN: "rain",
  HEAVY_RAIN: "heavy-rain",
  FREEZING_RAIN: "freezing-rain",
  SNOW: "snow",
  HEAVY_SNOW: "heavy-snow",
  RAIN_SHOWERS: "rain-showers",
  SNOW_SHOWERS: "snow-showers",
  THUNDERSTORM: "thunderstorm",
  UNKNOWN: "unknown",
};

const NIGHT_ICON_OVERRIDES: Partial<Record<ConditionCode, IconName>> = {
  CLEAR: "clear-night",
  MAINLY_CLEAR: "mainly-clear-night",
};

export function getConditionIcon(
  code: ConditionCode,
  isDaytime = true,
): IconName {
  if (!isDaytime) {
    const nightIcon = NIGHT_ICON_OVERRIDES[code];
    if (nightIcon !== undefined) {
      return nightIcon;
    }
  }
  return CONDITION_ICON_MAP[code];
}
