import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("API_BASE_URL", () => {
  it("falls back to the local-dev default when unset", async () => {
    vi.stubEnv("VITE_API_BASE_URL", undefined);

    const { API_BASE_URL } = await import("../../src/config/env");

    expect(API_BASE_URL).toBe("http://localhost:8000");
  });

  it("respects VITE_API_BASE_URL when set", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://skycast-api.onrender.com");

    const { API_BASE_URL } = await import("../../src/config/env");

    expect(API_BASE_URL).toBe("https://skycast-api.onrender.com");
  });
});
