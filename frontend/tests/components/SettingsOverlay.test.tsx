import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SettingsOverlay } from "../../src/components/SettingsOverlay";

describe("SettingsOverlay", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders nothing when closed", () => {
    render(<SettingsOverlay isOpen={false} onClose={vi.fn()} />);

    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders the panel and moves focus to the close button when open", () => {
    render(<SettingsOverlay isOpen={true} onClose={vi.fn()} />);

    const closeButton = screen.getByRole("button", { name: /close/i });
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(document.activeElement).toBe(closeButton);
  });

  it("calls onClose when the close button is clicked", () => {
    const onClose = vi.fn();
    render(<SettingsOverlay isOpen={true} onClose={onClose} />);

    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose on Escape", () => {
    const onClose = vi.fn();
    render(<SettingsOverlay isOpen={true} onClose={onClose} />);

    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });

    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose on backdrop click", () => {
    const onClose = vi.fn();
    render(<SettingsOverlay isOpen={true} onClose={onClose} />);

    fireEvent.click(screen.getByTestId("settings-backdrop"));

    expect(onClose).toHaveBeenCalledOnce();
  });

  it("does not call onClose on other keys", () => {
    const onClose = vi.fn();
    render(<SettingsOverlay isOpen={true} onClose={onClose} />);

    fireEvent.keyDown(screen.getByRole("dialog"), { key: "a" });

    expect(onClose).not.toHaveBeenCalled();
  });
});
