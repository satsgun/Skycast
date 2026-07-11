import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InputBar, placeholderFor } from "../../src/components/InputBar";
import type { MainState } from "../../src/state/machine";

const EMPTY: MainState = { type: "empty" };
const THINKING: MainState = { type: "thinking", query: "q", steps: [] };
const ANSWER: MainState = {
  type: "answer",
  query: "q",
  answer: { text: "answer", card: { forecasts: [], highlight: null } },
  isStale: false,
  followUpChips: [],
};
const CLARIFY: MainState = { type: "clarify", query: "q", candidates: [] };
const ERROR: MainState = {
  type: "error",
  query: "q",
  error: { kind: "internal", message: "boom" },
  actions: [],
};

describe("placeholderFor", () => {
  it("returns the empty-state placeholder", () => {
    expect(placeholderFor(EMPTY)).toBe("Ask about the weather…");
  });

  it("returns the follow-up placeholder after an answer", () => {
    expect(placeholderFor(ANSWER)).toBe("Ask a follow-up…");
  });

  it("returns the clarify placeholder", () => {
    expect(placeholderFor(CLARIFY)).toBe("Or type the full city name…");
  });

  it("falls back to the empty-state placeholder while thinking", () => {
    expect(placeholderFor(THINKING)).toBe("Ask about the weather…");
  });

  it("falls back to the empty-state placeholder on error", () => {
    expect(placeholderFor(ERROR)).toBe("Ask about the weather…");
  });
});

describe("InputBar", () => {
  afterEach(() => {
    cleanup();
  });

  it("submits the trimmed text and clears the field on Enter", () => {
    const onSubmit = vi.fn();
    render(<InputBar mainState={EMPTY} onSubmit={onSubmit} />);

    const input = screen.getByRole("textbox") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "  hello  " } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onSubmit).toHaveBeenCalledWith("hello");
    expect(input.value).toBe("");
  });

  it("submits on button click", () => {
    const onSubmit = vi.fn();
    render(<InputBar mainState={EMPTY} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(onSubmit).toHaveBeenCalledWith("hello");
  });

  it("does not submit blank or whitespace-only text", () => {
    const onSubmit = vi.fn();
    render(<InputBar mainState={EMPTY} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "   " },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("is never disabled, including in clarify state", () => {
    render(<InputBar mainState={CLARIFY} onSubmit={vi.fn()} />);

    const input = screen.getByRole("textbox") as HTMLInputElement;
    expect(input.disabled).toBe(false);
  });

  it("does not submit on a non-Enter key press", () => {
    const onSubmit = vi.fn();
    render(<InputBar mainState={EMPTY} onSubmit={onSubmit} />);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "hello" } });
    fireEvent.keyDown(input, { key: "a" });

    expect(onSubmit).not.toHaveBeenCalled();
  });
});
