import type { Forecast, ReadingLocator } from "../contract";
import { conditionLabel } from "../format/condition";
import { isDaytimeAt } from "../format/daylight";
import { celsiusToFahrenheit, formatTemperature } from "../format/temperature";
import { formatDayLabel, formatTime } from "../format/time";
import { formatWindSpeed } from "../format/windSpeed";
import { ConditionIcon } from "../icons/iconSource";
import type { UnitsSettings } from "../state/settingsStore";
import "./ForecastCard.css";

export interface ForecastCardProps {
  forecast: Forecast;
  units: UnitsSettings;
  highlightLocator: ReadingLocator | null;
}

// Strip cells show a bare degree (matching 02-multiday.svg's daily
// cards) -- the unit letter is shown once, on the current-conditions
// hero temp, not repeated on every cell.
function shortTemp(
  celsius: number,
  unit: UnitsSettings["temperature"],
): string {
  const value = unit === "F" ? celsiusToFahrenheit(celsius) : celsius;
  return `${Math.round(value)}°`;
}

function cellClass(base: string, isActive: boolean): string {
  return isActive ? `${base} ${base}--active` : base;
}

export function ForecastCard({
  forecast,
  units,
  highlightLocator,
}: ForecastCardProps) {
  const { location, current, hourly, daily } = forecast;

  return (
    <div className="skycast-forecast-card">
      <p className="skycast-forecast-card__location">{location.name}</p>

      {current !== null && (
        <div
          data-testid="forecast-current"
          className={cellClass(
            "skycast-forecast-card__current",
            highlightLocator?.block === "current",
          )}
        >
          <ConditionIcon
            code={current.condition_code}
            isDaytime={isDaytimeAt(current.timestamp, daily)}
            className="skycast-forecast-card__current-icon"
          />
          <p className="skycast-forecast-card__current-temp">
            {formatTemperature(current.temperature, units.temperature)}
          </p>
          <p className="skycast-forecast-card__current-line">
            {conditionLabel(current.condition_code)} in {location.name}
            {current.feels_like !== null &&
              ` · feels like ${formatTemperature(current.feels_like, units.temperature)}`}
          </p>
          {(current.wind_speed !== null ||
            current.precip_probability !== null) && (
            <p
              data-testid="forecast-current-stats"
              className="skycast-forecast-card__current-stats"
            >
              {current.wind_speed !== null &&
                formatWindSpeed(current.wind_speed, units.windSpeed)}
              {current.wind_speed !== null &&
                current.precip_probability !== null &&
                " · "}
              {current.precip_probability !== null &&
                `${Math.round(current.precip_probability)}% chance of rain`}
            </p>
          )}
        </div>
      )}

      {hourly !== null && hourly.length > 0 && (
        <div className="skycast-forecast-card__hourly">
          {hourly.map((reading, index) => (
            <div
              key={reading.timestamp}
              data-testid="forecast-hourly-cell"
              className={cellClass(
                "skycast-forecast-card__hourly-cell",
                highlightLocator?.block === "hourly" &&
                  highlightLocator.index === index,
              )}
            >
              <p className="skycast-forecast-card__cell-label">
                {formatTime(
                  reading.timestamp,
                  units.timeFormat,
                  location.timezone,
                )}
              </p>
              <ConditionIcon
                code={reading.condition_code}
                isDaytime={isDaytimeAt(reading.timestamp, daily)}
                className="skycast-forecast-card__cell-icon"
              />
              <p className="skycast-forecast-card__cell-temp">
                {shortTemp(reading.temperature, units.temperature)}
              </p>
            </div>
          ))}
        </div>
      )}

      {daily !== null && daily.length > 0 && (
        <div className="skycast-forecast-card__daily">
          {daily.map((reading, index) => (
            <div
              key={reading.date}
              data-testid="forecast-daily-cell"
              className={cellClass(
                "skycast-forecast-card__daily-cell",
                highlightLocator?.block === "daily" &&
                  highlightLocator.index === index,
              )}
            >
              <p className="skycast-forecast-card__cell-label">
                {formatDayLabel(reading.date)}
              </p>
              <ConditionIcon
                code={reading.condition_code}
                isDaytime={true}
                className="skycast-forecast-card__cell-icon"
              />
              <p className="skycast-forecast-card__cell-temp">
                {shortTemp(reading.temp_max, units.temperature)}
              </p>
              <p className="skycast-forecast-card__cell-temp-low">
                {shortTemp(reading.temp_min, units.temperature)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
