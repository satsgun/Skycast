import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ForecastCard } from "../../src/components/ForecastCard";
import type { Forecast, ReadingLocator } from "../../src/contract";
import type { UnitsSettings } from "../../src/state/settingsStore";

const LOCATION = {
  id: "1",
  name: "Hyderabad",
  latitude: 17.4,
  longitude: 78.5,
  country: "India",
  country_code: "IN",
  admin1: null,
  admin2: null,
  population: 1_000_000,
  timezone: "UTC",
};

const CONTRACT_UNITS = {
  temperature: "celsius",
  wind_speed: "kmh",
  precip_amount: "mm",
  precip_probability: "percent",
};

const UNITS: UnitsSettings = {
  temperature: "C",
  windSpeed: "kmh",
  timeFormat: "24h",
};

const CURRENT = {
  timestamp: "2026-07-10T12:00:00Z",
  temperature: 31,
  feels_like: 34,
  precip_probability: 10,
  precip_amount: 0,
  wind_speed: 12,
  condition_code: "CLEAR" as const,
};

const HOURLY = [
  {
    timestamp: "2026-07-10T12:00:00Z",
    temperature: 31,
    feels_like: 34,
    precip_probability: 10,
    precip_amount: 0,
    wind_speed: 12,
    condition_code: "CLEAR" as const,
  },
  {
    timestamp: "2026-07-10T13:00:00Z",
    temperature: 32,
    feels_like: 35,
    precip_probability: 15,
    precip_amount: 0,
    wind_speed: 14,
    condition_code: "PARTLY_CLOUDY" as const,
  },
];

const DAILY = [
  {
    date: "2026-07-10",
    temp_min: 24,
    temp_max: 32,
    precip_probability: 10,
    precip_amount: 0,
    wind_speed_max: 14,
    condition_code: "CLEAR" as const,
    sunrise: "2026-07-10T06:00:00Z",
    sunset: "2026-07-10T18:00:00Z",
  },
  {
    date: "2026-07-11",
    temp_min: 23,
    temp_max: 29,
    precip_probability: 60,
    precip_amount: 4,
    wind_speed_max: 18,
    condition_code: "THUNDERSTORM" as const,
    sunrise: "2026-07-11T06:00:00Z",
    sunset: "2026-07-11T18:00:00Z",
  },
];

function forecast(overrides: Partial<Forecast>): Forecast {
  return {
    location: LOCATION,
    units: CONTRACT_UNITS,
    current: null,
    hourly: null,
    daily: null,
    ...overrides,
  };
}

describe("ForecastCard", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the location name", () => {
    render(
      <ForecastCard
        forecast={forecast({})}
        units={UNITS}
        highlightLocator={null}
      />,
    );

    expect(screen.getByText("Hyderabad")).toBeTruthy();
  });

  it("renders the current-conditions summary, unit-formatted", () => {
    render(
      <ForecastCard
        forecast={forecast({ current: CURRENT })}
        units={UNITS}
        highlightLocator={null}
      />,
    );

    expect(screen.getByText("31°C")).toBeTruthy();
    expect(screen.getByText(/34/)).toBeTruthy();
    expect(screen.getByText(/Sunny/)).toBeTruthy();
    expect(screen.getByText(/12 km\/h/)).toBeTruthy();
    expect(screen.getByText(/10%/)).toBeTruthy();
  });

  it("converts the current temperature to the selected unit", () => {
    render(
      <ForecastCard
        forecast={forecast({ current: CURRENT })}
        units={{ ...UNITS, temperature: "F" }}
        highlightLocator={null}
      />,
    );

    expect(screen.getByText("88°F")).toBeTruthy();
  });

  it("omits the current-conditions block when there is no current reading", () => {
    render(
      <ForecastCard
        forecast={forecast({})}
        units={UNITS}
        highlightLocator={null}
      />,
    );

    expect(screen.queryByText("31°C")).toBeNull();
  });

  it("renders one cell per hourly reading, in order", () => {
    render(
      <ForecastCard
        forecast={forecast({ hourly: HOURLY })}
        units={UNITS}
        highlightLocator={null}
      />,
    );

    expect(screen.getByText("31°")).toBeTruthy();
    expect(screen.getByText("32°")).toBeTruthy();
  });

  it("converts hourly and daily strip temperatures to the selected unit", () => {
    render(
      <ForecastCard
        forecast={forecast({ hourly: HOURLY, daily: DAILY })}
        units={{ ...UNITS, temperature: "F" }}
        highlightLocator={null}
      />,
    );

    expect(screen.getByText("88°")).toBeTruthy(); // hourly 31C -> 88F
    expect(screen.getByText("75°")).toBeTruthy(); // daily temp_min 24C -> 75F
  });

  it("omits the stats line when wind and precipitation are both unavailable", () => {
    render(
      <ForecastCard
        forecast={forecast({
          current: { ...CURRENT, wind_speed: null, precip_probability: null },
        })}
        units={UNITS}
        highlightLocator={null}
      />,
    );

    expect(screen.queryByText(/chance of rain/)).toBeNull();
    expect(screen.queryByText(/km\/h/)).toBeNull();
  });

  it("renders wind speed without a separator when precipitation is unavailable", () => {
    render(
      <ForecastCard
        forecast={forecast({
          current: { ...CURRENT, precip_probability: null },
        })}
        units={UNITS}
        highlightLocator={null}
      />,
    );

    const stats = screen.getByTestId("forecast-current-stats");
    expect(stats.textContent).toBe("12 km/h");
  });

  it("renders one cell per daily reading with high/low, in order", () => {
    render(
      <ForecastCard
        forecast={forecast({ daily: DAILY })}
        units={UNITS}
        highlightLocator={null}
      />,
    );

    expect(screen.getByText("Fri")).toBeTruthy();
    expect(screen.getByText("Sat")).toBeTruthy();
    expect(screen.getByText("32°")).toBeTruthy();
    expect(screen.getByText("24°")).toBeTruthy();
  });

  it("highlights the current block when the locator points at it", () => {
    const locator: ReadingLocator = { block: "current", index: null };
    render(
      <ForecastCard
        forecast={forecast({ current: CURRENT })}
        units={UNITS}
        highlightLocator={locator}
      />,
    );

    const el = screen.getByTestId("forecast-current");
    expect(el.className).toContain("active");
  });

  it("highlights only the matching hourly cell", () => {
    const locator: ReadingLocator = { block: "hourly", index: 1 };
    render(
      <ForecastCard
        forecast={forecast({ hourly: HOURLY })}
        units={UNITS}
        highlightLocator={locator}
      />,
    );

    const cells = screen.getAllByTestId("forecast-hourly-cell");
    expect(cells[0].className).not.toContain("active");
    expect(cells[1].className).toContain("active");
  });

  it("highlights only the matching daily cell", () => {
    const locator: ReadingLocator = { block: "daily", index: 0 };
    render(
      <ForecastCard
        forecast={forecast({ daily: DAILY })}
        units={UNITS}
        highlightLocator={locator}
      />,
    );

    const cells = screen.getAllByTestId("forecast-daily-cell");
    expect(cells[0].className).toContain("active");
    expect(cells[1].className).not.toContain("active");
  });

  it("emphasizes nothing when highlightLocator is null", () => {
    render(
      <ForecastCard
        forecast={forecast({ current: CURRENT, daily: DAILY })}
        units={UNITS}
        highlightLocator={null}
      />,
    );

    expect(screen.getByTestId("forecast-current").className).not.toContain(
      "active",
    );
    for (const cell of screen.getAllByTestId("forecast-daily-cell")) {
      expect(cell.className).not.toContain("active");
    }
  });
});
