import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ClarifyView } from "../../src/components/ClarifyView";
import type { Location } from "../../src/contract";

const ILLINOIS: Location = {
  id: "1",
  name: "Springfield",
  latitude: 39.8,
  longitude: -89.6,
  country: "USA",
  country_code: "US",
  admin1: "Illinois",
  admin2: null,
  population: 114_000,
  timezone: "America/Chicago",
};

const MISSOURI: Location = {
  id: "2",
  name: "Springfield",
  latitude: 37.2,
  longitude: -93.3,
  country: "USA",
  country_code: "US",
  admin1: "Missouri",
  admin2: null,
  population: 169_000,
  timezone: "America/Chicago",
};

const SPARSE: Location = {
  id: "3",
  name: "Springfield",
  latitude: 0,
  longitude: 0,
  country: null,
  country_code: null,
  admin1: null,
  admin2: null,
  population: null,
  timezone: null,
};

describe("ClarifyView", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the agent line with the shared candidate name interpolated", () => {
    render(
      <ClarifyView candidates={[ILLINOIS, MISSOURI]} onSelect={vi.fn()} />,
    );

    expect(
      screen.getByText("There are a few Springfields — which one?"),
    ).toBeTruthy();
  });

  it("renders one button per candidate, in order, with title and subtitle", () => {
    render(
      <ClarifyView candidates={[ILLINOIS, MISSOURI]} onSelect={vi.fn()} />,
    );

    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(2);
    expect(buttons[0].textContent).toContain("Springfield, Illinois");
    expect(buttons[0].textContent).toContain("USA");
    expect(buttons[0].textContent).toContain("114k");
    expect(buttons[1].textContent).toContain("Springfield, Missouri");
    expect(buttons[1].textContent).toContain("169k");
  });

  it("omits subtitle parts gracefully when country/population/admin1 are null", () => {
    render(<ClarifyView candidates={[SPARSE, ILLINOIS]} onSelect={vi.fn()} />);

    const buttons = screen.getAllByRole("button");
    expect(buttons[0].textContent).toContain("Springfield");
    expect(buttons[0].textContent).not.toContain(",");
    expect(buttons[0].textContent).not.toContain("pop.");
  });

  it("calls onSelect with the exact candidate that was tapped", () => {
    const onSelect = vi.fn();
    render(
      <ClarifyView candidates={[ILLINOIS, MISSOURI]} onSelect={onSelect} />,
    );

    fireEvent.click(screen.getAllByRole("button")[1]);

    expect(onSelect).toHaveBeenCalledWith(MISSOURI);
  });
});
