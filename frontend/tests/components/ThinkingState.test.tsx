import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ThinkingState } from "../../src/components/ThinkingState";
import type { StepPayload } from "../../src/contract";

const STEP_1: StepPayload = { label: "Understood request", stage: "decompose" };
const STEP_2: StepPayload = { label: "Resolved locations", stage: "plan" };

describe("ThinkingState", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders only the header when there are no steps yet", () => {
    render(<ThinkingState steps={[]} />);

    expect(screen.getByText(/working on it/i)).toBeTruthy();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });

  it("renders one list item per step, in order", () => {
    render(<ThinkingState steps={[STEP_1, STEP_2]} />);

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toContain("Understood request");
    expect(items[1].textContent).toContain("Resolved locations");
  });

  it("marks the last step active and earlier steps done", () => {
    render(<ThinkingState steps={[STEP_1, STEP_2]} />);

    const items = screen.getAllByRole("listitem");
    expect(items[0].className).toContain("done");
    expect(items[1].className).toContain("active");
  });

  it("promotes a step from active to done as a new step arrives", () => {
    const { rerender } = render(<ThinkingState steps={[STEP_1]} />);

    let items = screen.getAllByRole("listitem");
    expect(items[0].className).toContain("active");

    rerender(<ThinkingState steps={[STEP_1, STEP_2]} />);

    items = screen.getAllByRole("listitem");
    expect(items[0].className).toContain("done");
    expect(items[1].className).toContain("active");
  });

  it("exposes the progress as an accessible live region", () => {
    render(<ThinkingState steps={[STEP_1]} />);

    const status = screen.getByRole("status");
    expect(status.getAttribute("aria-live")).toBe("polite");
  });
});
