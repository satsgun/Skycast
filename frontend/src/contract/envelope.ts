import type { Forecast, Location } from "./domain";

export type PipelineStage =
  "decompose" | "plan" | "execute_geocode" | "execute_forecast" | "synthesize";

export interface StepPayload {
  label: string;
  stage: PipelineStage;
}

export interface ClarifyPayload {
  candidates: Location[];
}

export type ForecastBlock = "current" | "hourly" | "daily";

export interface ReadingLocator {
  block: ForecastBlock;
  index: number | null;
}

export interface Highlight {
  forecast_index: number;
  locator: ReadingLocator;
}

export interface AnswerCard {
  forecasts: Forecast[];
  highlight: Highlight | null;
}

export interface AnswerPayload {
  text: string;
  card: AnswerCard;
}

export type ErrorKind =
  "not_found" | "provider_unreachable" | "bad_input" | "internal";

export interface ErrorPayload {
  kind: ErrorKind;
  message: string;
}

export type SSEEventType = "step" | "clarify" | "answer" | "error";

export interface StepEvent {
  type: "step";
  data: StepPayload;
}

export interface ClarifyEvent {
  type: "clarify";
  data: ClarifyPayload;
}

export interface AnswerEvent {
  type: "answer";
  data: AnswerPayload;
}

export interface ErrorEvent {
  type: "error";
  data: ErrorPayload;
}

export type SSEEvent = StepEvent | ClarifyEvent | AnswerEvent | ErrorEvent;
