import { useReducer, type Dispatch } from "react";

import type {
  AnswerPayload,
  ClarifyPayload,
  ErrorKind,
  ErrorPayload,
  Forecast,
  Location,
  StepPayload,
} from "../contract";

export interface ErrorAction {
  type: "retry"; // widened by F2.5 when it lands
}

export type MainState =
  | { type: "empty"; currentConditionsGlance: Forecast | null }
  | { type: "thinking"; query: string; steps: StepPayload[] }
  | {
      type: "answer";
      query: string;
      answer: AnswerPayload;
      isStale: boolean;
      followUpChips: string[];
    }
  | { type: "clarify"; query: string; candidates: Location[] }
  | {
      type: "error";
      query: string;
      error: ErrorPayload;
      actions: ErrorAction[];
    };

export interface MachineState {
  main: MainState;
  isSettingsOpen: boolean;
}

export type MachineEvent =
  | { type: "SUBMIT"; query: string }
  | { type: "STEP"; payload: StepPayload }
  | { type: "ANSWER"; payload: AnswerPayload }
  | { type: "CLARIFY"; payload: ClarifyPayload }
  | { type: "ERROR"; payload: ErrorPayload }
  | { type: "SHOW_CACHED"; payload: AnswerPayload }
  | { type: "SESSION_EXPIRED" }
  | { type: "OPEN_SETTINGS" }
  | { type: "CLOSE_SETTINGS" };

function unhandledTransition(
  stateType: MainState["type"],
  eventType: string,
): never {
  throw new Error(
    `SkyCast machine: no transition for (${stateType}, ${eventType})`,
  );
}

function toEmpty(): MainState {
  return { type: "empty", currentConditionsGlance: null };
}

function toThinking(query: string): MainState {
  return { type: "thinking", query, steps: [] };
}

function generateFollowUpChips(
  _query: string,
  _answer: AnswerPayload,
): string[] {
  return []; // placeholder -- real heuristic lands in F2.4
}

function actionsFor(_kind: ErrorKind): ErrorAction[] {
  return [{ type: "retry" }]; // placeholder -- real policy lands in F2.5
}

function appendStep(main: MainState, payload: StepPayload): MainState {
  if (main.type !== "thinking") return unhandledTransition(main.type, "STEP");
  return { ...main, steps: [...main.steps, payload] };
}

function toAnswerFromThinking(
  main: MainState,
  payload: AnswerPayload,
): MainState {
  if (main.type !== "thinking") return unhandledTransition(main.type, "ANSWER");
  return {
    type: "answer",
    query: main.query,
    answer: payload,
    isStale: false,
    followUpChips: generateFollowUpChips(main.query, payload),
  };
}

function toClarifyFromThinking(
  main: MainState,
  payload: ClarifyPayload,
): MainState {
  if (main.type !== "thinking")
    return unhandledTransition(main.type, "CLARIFY");
  return { type: "clarify", query: main.query, candidates: payload.candidates };
}

function toErrorFromThinking(
  main: MainState,
  payload: ErrorPayload,
): MainState {
  if (main.type !== "thinking") return unhandledTransition(main.type, "ERROR");
  return {
    type: "error",
    query: main.query,
    error: payload,
    actions: actionsFor(payload.kind),
  };
}

function toStaleAnswerFromError(
  main: MainState,
  payload: AnswerPayload,
): MainState {
  if (main.type !== "error")
    return unhandledTransition(main.type, "SHOW_CACHED");
  return {
    type: "answer",
    query: main.query,
    answer: payload,
    isStale: true,
    followUpChips: generateFollowUpChips(main.query, payload),
  };
}

export function initialMachineState(): MachineState {
  return { main: toEmpty(), isSettingsOpen: false };
}

export function machineReducer(
  state: MachineState,
  event: MachineEvent,
): MachineState {
  switch (event.type) {
    case "SUBMIT":
      return { ...state, main: toThinking(event.query) };
    case "SESSION_EXPIRED":
      return { ...state, main: toEmpty() };
    case "OPEN_SETTINGS":
      return { ...state, isSettingsOpen: true };
    case "CLOSE_SETTINGS":
      return { ...state, isSettingsOpen: false };
    case "STEP":
      return { ...state, main: appendStep(state.main, event.payload) };
    case "ANSWER":
      return {
        ...state,
        main: toAnswerFromThinking(state.main, event.payload),
      };
    case "CLARIFY":
      return {
        ...state,
        main: toClarifyFromThinking(state.main, event.payload),
      };
    case "ERROR":
      return { ...state, main: toErrorFromThinking(state.main, event.payload) };
    case "SHOW_CACHED":
      return {
        ...state,
        main: toStaleAnswerFromError(state.main, event.payload),
      };
    default:
      return unhandledTransition(
        state.main.type,
        (event as { type: string }).type,
      );
  }
}

export function useMachine(): [MachineState, Dispatch<MachineEvent>] {
  return useReducer(machineReducer, initialMachineState());
}
