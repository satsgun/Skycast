export type ConditionCode = string; // refined into a real union by F1.3

export interface Location {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  country: string | null;
  country_code: string | null;
  admin1: string | null;
  admin2: string | null;
  population: number | null;
  timezone: string | null;
}

export interface Units {
  temperature: string;
  wind_speed: string;
  precip_amount: string;
  precip_probability: string;
}

export interface HourlyReading {
  timestamp: string;
  temperature: number;
  feels_like: number | null;
  precip_probability: number | null;
  precip_amount: number | null;
  wind_speed: number | null;
  condition_code: ConditionCode;
}

export interface DailyReading {
  date: string;
  temp_min: number;
  temp_max: number;
  precip_probability: number | null;
  precip_amount: number | null;
  wind_speed_max: number | null;
  condition_code: ConditionCode;
  sunrise: string | null;
  sunset: string | null;
}

export interface Forecast {
  location: Location;
  units: Units;
  current: HourlyReading | null;
  hourly: HourlyReading[] | null;
  daily: DailyReading[] | null;
}
