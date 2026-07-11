import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ErrorView } from "../../src/components/ErrorView";
import type { ErrorPayload } from "../../src/contract";
import type { ErrorAction } from "../../src/state/errorActions";

const NOT_FOUND: ErrorPayload = {
  kind: "not_found",
  message: 'I couldn\'t find "Atlantisburg".',
};

const OFFLINE: ErrorPayload = {
  kind: "provider_unreachable",
  message: "The forecast provider isn't responding right now.",
};

const NOW = new Date("2026-07-11T12:00:00Z");

describe("ErrorView", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
    cleanup();
  });

  it("uses a neutral treatment for a user-correctable error", () => {
    render(
      <ErrorView
        error={NOT_FOUND}
        actions={[{ type: "retry_free_text" }]}
        onRetry={vi.fn()}
        onShowCached={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(screen.getByText("Location not found")).toBeTruthy();
  });

  it("uses a danger treatment for a system error", () => {
    render(
      <ErrorView
        error={OFFLINE}
        actions={[{ type: "retry" }]}
        onRetry={vi.fn()}
        onShowCached={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(screen.getByText("Service offline")).toBeTruthy();
  });

  it("renders the error message", () => {
    render(
      <ErrorView
        error={OFFLINE}
        actions={[{ type: "retry" }]}
        onRetry={vi.fn()}
        onShowCached={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(
      screen.getByText("The forecast provider isn't responding right now."),
    ).toBeTruthy();
  });

  it("renders a retry action and calls onRetry when tapped", () => {
    const onRetry = vi.fn();
    render(
      <ErrorView
        error={OFFLINE}
        actions={[{ type: "retry" }]}
        onRetry={onRetry}
        onShowCached={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("renders a show_cached action with the freshness line and calls onShowCached", () => {
    const onShowCached = vi.fn();
    const actions: ErrorAction[] = [
      { type: "retry" },
      { type: "show_cached", cachedAt: "2026-07-11T11:52:00Z" },
    ];
    render(
      <ErrorView
        error={OFFLINE}
        actions={actions}
        onRetry={vi.fn()}
        onShowCached={onShowCached}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(
      screen.getByText("Your last data was from 8 minutes ago."),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /show last cached/i }));

    expect(onShowCached).toHaveBeenCalledOnce();
  });

  it("uses singular phrasing for a one-minute-old cache", () => {
    const actions: ErrorAction[] = [
      { type: "show_cached", cachedAt: "2026-07-11T11:59:00Z" },
    ];
    render(
      <ErrorView
        error={OFFLINE}
        actions={actions}
        onRetry={vi.fn()}
        onShowCached={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(
      screen.getByText("Your last data was from 1 minute ago."),
    ).toBeTruthy();
  });

  it("renders an open_settings action labeled distinctly from the header's settings button", () => {
    const onOpenSettings = vi.fn();
    render(
      <ErrorView
        error={{ kind: "bad_input", message: "Units look invalid." }}
        actions={[{ type: "open_settings" }, { type: "retry_free_text" }]}
        onRetry={vi.fn()}
        onShowCached={vi.fn()}
        onOpenSettings={onOpenSettings}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Review settings" }));

    expect(onOpenSettings).toHaveBeenCalledOnce();
  });

  it("renders retry_free_text as guidance text, not a button", () => {
    render(
      <ErrorView
        error={NOT_FOUND}
        actions={[{ type: "retry_free_text" }]}
        onRetry={vi.fn()}
        onShowCached={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(screen.getByText(/type a new search below/i)).toBeTruthy();
  });

  it("renders cleanly with a single action", () => {
    render(
      <ErrorView
        error={{ kind: "internal", message: "Something broke." }}
        actions={[{ type: "retry" }]}
        onRetry={vi.fn()}
        onShowCached={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("button")).toHaveLength(1);
  });
});
