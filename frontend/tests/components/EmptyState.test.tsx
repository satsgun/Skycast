import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EmptyState } from "../../src/components/EmptyState";
import { STARTER_CHIPS } from "../../src/state/chips";

describe("EmptyState", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders a prompt to set a default location when none is set", () => {
    render(
      <EmptyState
        hasDefaultLocation={false}
        onSubmit={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(screen.getByText(/set a default location/i)).toBeTruthy();
  });

  it("calls onOpenSettings from the location prompt's CTA", () => {
    const onOpenSettings = vi.fn();
    render(
      <EmptyState
        hasDefaultLocation={false}
        onSubmit={vi.fn()}
        onOpenSettings={onOpenSettings}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: /choose a default location/i }),
    );

    expect(onOpenSettings).toHaveBeenCalledOnce();
  });

  it("renders no location prompt when a default location is set", () => {
    render(
      <EmptyState
        hasDefaultLocation={true}
        onSubmit={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(screen.queryByText(/set a default location/i)).toBeNull();
  });

  it("always renders the heading and every starter chip", () => {
    render(
      <EmptyState
        hasDefaultLocation={true}
        onSubmit={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(screen.getByText("What would you like to know?")).toBeTruthy();
    for (const chip of STARTER_CHIPS) {
      expect(screen.getByRole("button", { name: chip })).toBeTruthy();
    }
  });

  it("submits the tapped chip's exact text", () => {
    const onSubmit = vi.fn();
    render(
      <EmptyState
        hasDefaultLocation={true}
        onSubmit={onSubmit}
        onOpenSettings={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: STARTER_CHIPS[0] }));

    expect(onSubmit).toHaveBeenCalledWith(STARTER_CHIPS[0]);
  });
});
