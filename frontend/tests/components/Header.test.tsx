import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Header } from "../../src/components/Header";

describe("Header", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the product wordmark", () => {
    render(<Header locationName={null} onOpenSettings={vi.fn()} />);

    expect(screen.getByText("Skycast")).toBeTruthy();
  });

  it("shows the location name when set", () => {
    render(<Header locationName="Hyderabad" onOpenSettings={vi.fn()} />);

    expect(screen.getByText(/Hyderabad/)).toBeTruthy();
  });

  it("shows no location text when null", () => {
    render(<Header locationName={null} onOpenSettings={vi.fn()} />);

    expect(screen.queryByTestId("header-location")).toBeNull();
  });

  it("calls onOpenSettings when the settings button is clicked", () => {
    const onOpenSettings = vi.fn();
    render(<Header locationName={null} onOpenSettings={onOpenSettings} />);

    fireEvent.click(screen.getByRole("button", { name: /settings/i }));

    expect(onOpenSettings).toHaveBeenCalledOnce();
  });
});
