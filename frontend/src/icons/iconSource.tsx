import type { IconBaseProps, IconType } from "react-icons";
import {
  WiCloud,
  WiCloudy,
  WiDaySunny,
  WiDaySunnyOvercast,
  WiFog,
  WiNa,
  WiNightAltPartlyCloudy,
  WiNightClear,
  WiRain,
  WiRainMix,
  WiRainWind,
  WiShowers,
  WiSleet,
  WiSnow,
  WiSnowWind,
  WiSnowflakeCold,
  WiSprinkle,
  WiThunderstorm,
} from "react-icons/wi";

import type { ConditionCode } from "../contract/conditionCodes";
import type { IconName } from "./conditionIcons";
import { getConditionIcon } from "./conditionIcons";

/**
 * Binds every abstract IconName (conditionIcons.ts) to a real
 * react-icons/wi component. See design-tokens.md for the icon-source
 * rationale and the per-entry mapping notes (e.g. snow-showers).
 */
export const ICON_COMPONENTS: Record<IconName, IconType> = {
  "clear-day": WiDaySunny,
  "clear-night": WiNightClear,
  "mainly-clear-day": WiDaySunnyOvercast,
  "mainly-clear-night": WiNightAltPartlyCloudy,
  "partly-cloudy": WiCloud,
  cloudy: WiCloudy,
  fog: WiFog,
  drizzle: WiSprinkle,
  "freezing-drizzle": WiRainMix,
  rain: WiRain,
  "heavy-rain": WiRainWind,
  "freezing-rain": WiSleet,
  snow: WiSnow,
  "heavy-snow": WiSnowWind,
  "rain-showers": WiShowers,
  "snow-showers": WiSnowflakeCold,
  thunderstorm: WiThunderstorm,
  unknown: WiNa,
};

export function ConditionIcon({
  code,
  isDaytime = true,
  ...props
}: { code: ConditionCode; isDaytime?: boolean } & IconBaseProps) {
  const Icon = ICON_COMPONENTS[getConditionIcon(code, isDaytime)];
  return <Icon {...props} />;
}
