import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SegmentedControl } from "../../src/components/SegmentedControl";

type Unit = "C" | "F";

const OPTIONS = [
  { value: "C" as Unit, label: "°C" },
  { value: "F" as Unit, label: "°F" },
];

describe("SegmentedControl", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders one button per option", () => {
    render(
      <SegmentedControl
        label="Temperature"
        options={OPTIONS}
        value="C"
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "°C" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "°F" })).toBeTruthy();
  });

  it("renders the label", () => {
    render(
      <SegmentedControl
        label="Temperature"
        options={OPTIONS}
        value="C"
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByText("Temperature")).toBeTruthy();
  });

  it("marks only the current value's option as selected", () => {
    render(
      <SegmentedControl
        label="Temperature"
        options={OPTIONS}
        value="C"
        onChange={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: "°C" }).getAttribute("aria-pressed"),
    ).toBe("true");
    expect(
      screen.getByRole("button", { name: "°F" }).getAttribute("aria-pressed"),
    ).toBe("false");
  });

  it("calls onChange with the tapped option's value", () => {
    const onChange = vi.fn();
    render(
      <SegmentedControl
        label="Temperature"
        options={OPTIONS}
        value="C"
        onChange={onChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "°F" }));

    expect(onChange).toHaveBeenCalledWith("F");
  });
});
