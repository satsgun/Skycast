import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "../src/App";

describe("App", () => {
  it("renders the Skycast wordmark and an active input bar", () => {
    render(<App />);

    expect(screen.getByText("Skycast")).toBeTruthy();

    const input = screen.getByRole("textbox") as HTMLInputElement;
    expect(input.disabled).toBe(false);
    expect(input.getAttribute("placeholder")).toBe("Ask about the weather…");
  });
});
