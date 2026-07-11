import type { Location } from "../contract";
import type { SettingsState, UnitsSettings } from "../state/settingsStore";
import { SegmentedControl } from "./SegmentedControl";
import "./SettingsPanel.css";

export interface SettingsPanelProps {
  settings: SettingsState;
  onSetUnits: (units: Partial<UnitsSettings>) => void;
  onSetDefaultLocation: (location: Location | null) => void;
}

const TEMPERATURE_OPTIONS: {
  value: UnitsSettings["temperature"];
  label: string;
}[] = [
  { value: "C", label: "°C" },
  { value: "F", label: "°F" },
];

const WIND_SPEED_OPTIONS: {
  value: UnitsSettings["windSpeed"];
  label: string;
}[] = [
  { value: "kmh", label: "km/h" },
  { value: "mph", label: "mph" },
  { value: "ms", label: "m/s" },
];

const TIME_FORMAT_OPTIONS: {
  value: UnitsSettings["timeFormat"];
  label: string;
}[] = [
  { value: "12h", label: "12h" },
  { value: "24h", label: "24h" },
];

export function SettingsPanel({
  settings,
  onSetUnits,
  onSetDefaultLocation,
}: SettingsPanelProps) {
  return (
    <div className="skycast-settings-body">
      <section className="skycast-settings-body__group">
        <p className="skycast-settings-body__group-label">Location</p>
        <div className="skycast-settings-body__row">
          <div>
            <p className="skycast-settings-body__row-label">Default location</p>
            <p className="skycast-settings-body__row-sublabel">
              Used when you don't name a city
            </p>
          </div>
          <div className="skycast-settings-body__location-value">
            <span>{settings.defaultLocation?.name ?? "Not set"}</span>
            {settings.defaultLocation !== null && (
              <button
                type="button"
                className="skycast-settings-body__clear"
                onClick={() => onSetDefaultLocation(null)}
              >
                Clear
              </button>
            )}
          </div>
        </div>
      </section>

      <section className="skycast-settings-body__group">
        <p className="skycast-settings-body__group-label">Units</p>
        <SegmentedControl
          label="Temperature"
          options={TEMPERATURE_OPTIONS}
          value={settings.units.temperature}
          onChange={(value) => onSetUnits({ temperature: value })}
        />
        <SegmentedControl
          label="Wind speed"
          options={WIND_SPEED_OPTIONS}
          value={settings.units.windSpeed}
          onChange={(value) => onSetUnits({ windSpeed: value })}
        />
        <SegmentedControl
          label="Time format"
          options={TIME_FORMAT_OPTIONS}
          value={settings.units.timeFormat}
          onChange={(value) => onSetUnits({ timeFormat: value })}
        />
      </section>
    </div>
  );
}
