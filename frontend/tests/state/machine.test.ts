import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  AnswerPayload,
  ClarifyPayload,
  ErrorKind,
  ErrorPayload,
  Location,
  StepPayload,
} from "../../src/contract";
import {
  initialMachineState,
  machineReducer,
  useMachine,
  type MachineEvent,
  type MachineState,
} from "../../src/state/machine";

const LOCATION: Location = {
  id: "1",
  name: "Austin",
  latitude: 30.27,
  longitude: -97.74,
  country: null,
  country_code: "US",
  admin1: null,
  admin2: null,
  population: null,
  timezone: null,
};

const STEP: StepPayload = {
  label: "Understanding your question...",
  stage: "decompose",
};

const ANSWER: AnswerPayload = {
  text: "Yes, bring an umbrella.",
  card: { forecasts: [], highlight: null },
};

const CLARIFY: ClarifyPayload = { candidates: [LOCATION] };

function errorPayload(kind: ErrorKind): ErrorPayload {
  return { kind, message: `something went wrong: ${kind}` };
}

function thinkingState(query = "what's the weather?"): MachineState {
  return machineReducer(initialMachineState(), { type: "SUBMIT", query });
}

function answerState(): MachineState {
  return machineReducer(thinkingState(), { type: "ANSWER", payload: ANSWER });
}

function clarifyState(): MachineState {
  return machineReducer(thinkingState(), { type: "CLARIFY", payload: CLARIFY });
}

function errorState(kind: ErrorKind = "internal"): MachineState {
  return machineReducer(thinkingState(), {
    type: "ERROR",
    payload: errorPayload(kind),
  });
}

const ALL_MAIN_STATES: Record<string, () => MachineState> = {
  empty: () => initialMachineState(),
  thinking: () => thinkingState(),
  answer: () => answerState(),
  clarify: () => clarifyState(),
  error: () => errorState(),
};

describe("initialMachineState", () => {
  it("starts empty, with no glance and settings closed", () => {
    expect(initialMachineState()).toEqual({
      main: { type: "empty", currentConditionsGlance: null },
      isSettingsOpen: false,
    });
  });
});

describe("SUBMIT", () => {
  for (const [name, buildState] of Object.entries(ALL_MAIN_STATES)) {
    it(`transitions ${name} to a fresh thinking state`, () => {
      const state = buildState();

      const next = machineReducer(state, {
        type: "SUBMIT",
        query: "new query",
      });

      expect(next.main).toEqual({
        type: "thinking",
        query: "new query",
        steps: [],
      });
    });
  }

  it("clears any accumulated steps when submitting while already thinking", () => {
    let state = thinkingState();
    state = machineReducer(state, { type: "STEP", payload: STEP });
    expect((state.main as { steps: StepPayload[] }).steps).toHaveLength(1);

    state = machineReducer(state, { type: "SUBMIT", query: "restarted query" });

    expect(state.main).toEqual({
      type: "thinking",
      query: "restarted query",
      steps: [],
    });
  });
});

describe("STEP accumulation", () => {
  it("appends steps in arrival order, producing a new array each time", () => {
    let state = thinkingState();
    const arrays: StepPayload[][] = [];

    for (let i = 0; i < 3; i++) {
      state = machineReducer(state, {
        type: "STEP",
        payload: { label: `step ${i}`, stage: "plan" },
      });
      arrays.push((state.main as { steps: StepPayload[] }).steps);
    }

    expect(arrays[2]).toEqual([
      { label: "step 0", stage: "plan" },
      { label: "step 1", stage: "plan" },
      { label: "step 2", stage: "plan" },
    ]);
    expect(arrays[0]).not.toBe(arrays[1]);
    expect(arrays[1]).not.toBe(arrays[2]);
  });
});

describe("ANSWER", () => {
  it("transitions thinking to a fresh (non-stale) answer, preserving the query", () => {
    const state = machineReducer(thinkingState("what's the weather?"), {
      type: "ANSWER",
      payload: ANSWER,
    });

    expect(state.main).toEqual({
      type: "answer",
      query: "what's the weather?",
      answer: ANSWER,
      isStale: false,
      followUpChips: [],
    });
  });
});

describe("CLARIFY", () => {
  it("transitions thinking to clarify, carrying candidates and the original query", () => {
    const state = machineReducer(thinkingState("Springfield weather?"), {
      type: "CLARIFY",
      payload: CLARIFY,
    });

    expect(state.main).toEqual({
      type: "clarify",
      query: "Springfield weather?",
      candidates: [LOCATION],
    });
  });
});

describe("ERROR", () => {
  const kinds: ErrorKind[] = [
    "not_found",
    "provider_unreachable",
    "bad_input",
    "internal",
  ];

  for (const kind of kinds) {
    it(`transitions thinking to error for kind=${kind} with at least one action`, () => {
      const payload = errorPayload(kind);

      const state = machineReducer(thinkingState("query text"), {
        type: "ERROR",
        payload,
      });

      expect(state.main.type).toBe("error");
      const errorMain = state.main as {
        query: string;
        error: ErrorPayload;
        actions: unknown[];
      };
      expect(errorMain.query).toBe("query text");
      expect(errorMain.error).toEqual(payload);
      expect(errorMain.actions.length).toBeGreaterThanOrEqual(1);
    });
  }
});

describe("clarify re-query loop", () => {
  it("re-submitting the original query from clarify starts a fresh thinking state", () => {
    const state = machineReducer(thinkingState("Springfield weather?"), {
      type: "CLARIFY",
      payload: CLARIFY,
    });
    const original = (state.main as { query: string }).query;

    const next = machineReducer(state, { type: "SUBMIT", query: original });

    expect(next.main).toEqual({
      type: "thinking",
      query: "Springfield weather?",
      steps: [],
    });
  });
});

describe("SHOW_CACHED", () => {
  it("transitions a provider_unreachable error to a stale answer", () => {
    const state = machineReducer(errorState("provider_unreachable"), {
      type: "SHOW_CACHED",
      payload: ANSWER,
    });

    expect(state.main).toEqual({
      type: "answer",
      query: "what's the weather?",
      answer: ANSWER,
      isStale: true,
      followUpChips: [],
    });
  });

  it("does not gate on the error's kind -- any error state accepts SHOW_CACHED", () => {
    const state = machineReducer(errorState("not_found"), {
      type: "SHOW_CACHED",
      payload: ANSWER,
    });

    expect(state.main.type).toBe("answer");
    expect((state.main as { isStale: boolean }).isStale).toBe(true);
  });
});

describe("SESSION_EXPIRED", () => {
  for (const [name, buildState] of Object.entries(ALL_MAIN_STATES)) {
    for (const isSettingsOpen of [true, false]) {
      it(`resets ${name} to empty, leaving isSettingsOpen=${isSettingsOpen} unchanged`, () => {
        const state: MachineState = { ...buildState(), isSettingsOpen };

        const next = machineReducer(state, { type: "SESSION_EXPIRED" });

        expect(next.main).toEqual({
          type: "empty",
          currentConditionsGlance: null,
        });
        expect(next.isSettingsOpen).toBe(isSettingsOpen);
      });
    }
  }
});

describe("OPEN_SETTINGS / CLOSE_SETTINGS", () => {
  it("opens settings without touching main state", () => {
    const state = thinkingState();

    const next = machineReducer(state, { type: "OPEN_SETTINGS" });

    expect(next.isSettingsOpen).toBe(true);
    expect(next.main).toEqual(state.main);
  });

  it("closes settings without touching main state", () => {
    const state: MachineState = { ...answerState(), isSettingsOpen: true };

    const next = machineReducer(state, { type: "CLOSE_SETTINGS" });

    expect(next.isSettingsOpen).toBe(false);
    expect(next.main).toEqual(state.main);
  });

  it("is idempotent when opening settings that are already open", () => {
    const state: MachineState = {
      ...initialMachineState(),
      isSettingsOpen: true,
    };

    const next = machineReducer(state, { type: "OPEN_SETTINGS" });

    expect(next.isSettingsOpen).toBe(true);
  });

  it("does not interfere with an unrelated thinking-to-answer transition", () => {
    const state: MachineState = { ...thinkingState(), isSettingsOpen: true };

    const next = machineReducer(state, { type: "ANSWER", payload: ANSWER });

    expect(next.isSettingsOpen).toBe(true);
    expect(next.main.type).toBe("answer");
  });
});

describe("unhandled (state, event) pairs throw", () => {
  const nonThinkingStates = Object.entries(ALL_MAIN_STATES).filter(
    ([name]) => name !== "thinking",
  );

  for (const [name, buildState] of nonThinkingStates) {
    it(`STEP from ${name} throws`, () => {
      expect(() =>
        machineReducer(buildState(), { type: "STEP", payload: STEP }),
      ).toThrow();
    });

    it(`ANSWER from ${name} throws`, () => {
      expect(() =>
        machineReducer(buildState(), { type: "ANSWER", payload: ANSWER }),
      ).toThrow();
    });

    it(`CLARIFY from ${name} throws`, () => {
      expect(() =>
        machineReducer(buildState(), { type: "CLARIFY", payload: CLARIFY }),
      ).toThrow();
    });

    it(`ERROR from ${name} throws`, () => {
      expect(() =>
        machineReducer(buildState(), {
          type: "ERROR",
          payload: errorPayload("internal"),
        }),
      ).toThrow();
    });
  }

  const nonErrorStates = Object.entries(ALL_MAIN_STATES).filter(
    ([name]) => name !== "error",
  );

  for (const [name, buildState] of nonErrorStates) {
    it(`SHOW_CACHED from ${name} throws`, () => {
      expect(() =>
        machineReducer(buildState(), { type: "SHOW_CACHED", payload: ANSWER }),
      ).toThrow();
    });
  }

  it("an unrecognized event type throws", () => {
    const bogusEvent = { type: "BOGUS_EVENT" } as unknown as MachineEvent;

    expect(() => machineReducer(initialMachineState(), bogusEvent)).toThrow();
  });
});

describe("useMachine", () => {
  it("returns the initial state on first render", () => {
    const { result } = renderHook(() => useMachine());

    expect(result.current[0]).toEqual(initialMachineState());
  });

  it("dispatches events through useReducer", () => {
    const { result } = renderHook(() => useMachine());

    act(() => {
      result.current[1]({ type: "SUBMIT", query: "hook query" });
    });

    expect(result.current[0].main).toEqual({
      type: "thinking",
      query: "hook query",
      steps: [],
    });
  });
});
