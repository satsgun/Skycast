/**
 * Vendored from backend/src/skycast/domain/conditions.json (generated
 * by backend/src/skycast/domain/conditions.py). To refresh after a
 * backend change: from backend/, run `python -m
 * skycast.domain.conditions`, then copy this array to match the
 * regenerated conditions.json exactly. Do not maintain this by hand
 * from memory of the backend enum -- always copy the generated file's
 * actual contents.
 */
export const CONDITION_CODES = [
  "CLEAR",
  "MAINLY_CLEAR",
  "PARTLY_CLOUDY",
  "CLOUDY",
  "FOG",
  "DRIZZLE",
  "FREEZING_DRIZZLE",
  "RAIN",
  "HEAVY_RAIN",
  "FREEZING_RAIN",
  "SNOW",
  "HEAVY_SNOW",
  "RAIN_SHOWERS",
  "SNOW_SHOWERS",
  "THUNDERSTORM",
  "UNKNOWN",
] as const;

export type ConditionCode = (typeof CONDITION_CODES)[number];
