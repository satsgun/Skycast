import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EmptyState } from "../../src/components/EmptyState";
import { STARTER_CHIPS } from "../../src/state/chips";

describe("EmptyState", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders guidance text, not a button, when no default location is set", () => {
    render(<EmptyState hasDefaultLocation={false} onSubmit={vi.fn()} />);

    expect(
      screen.getByText("Ask about a place to see current conditions here."),
    ).toBeTruthy();
    expect(screen.queryAllByRole("button")).toHaveLength(STARTER_CHIPS.length);
  });

  it("renders no location guidance when a default location is set", () => {
    render(<EmptyState hasDefaultLocation={true} onSubmit={vi.fn()} />);

    expect(
      screen.queryByText("Ask about a place to see current conditions here."),
    ).toBeNull();
  });

  it("always renders the heading and every starter chip", () => {
    render(<EmptyState hasDefaultLocation={true} onSubmit={vi.fn()} />);

    expect(screen.getByText("What would you like to know?")).toBeTruthy();
    for (const chip of STARTER_CHIPS) {
      expect(screen.getByRole("button", { name: chip })).toBeTruthy();
    }
  });

  it("submits the tapped chip's exact text", () => {
    const onSubmit = vi.fn();
    render(<EmptyState hasDefaultLocation={true} onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole("button", { name: STARTER_CHIPS[0] }));

    expect(onSubmit).toHaveBeenCalledWith(STARTER_CHIPS[0]);
  });
});
