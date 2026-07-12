import type { Location } from "./domain";

export interface QueryRequest {
  query: string;
  now: string;
  default_location?: Location;
  resolved_locations?: Record<string, Location>;
  units?: string;
}
