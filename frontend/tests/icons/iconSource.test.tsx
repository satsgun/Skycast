import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CONDITION_CODES } from "../../src/contract/conditionCodes";
import { ConditionIcon } from "../../src/icons/iconSource";

describe("ConditionIcon", () => {
  it("renders a real svg for every condition code, day and night", () => {
    for (const code of CONDITION_CODES) {
      for (const isDaytime of [true, false]) {
        const { container, unmount } = render(
          <ConditionIcon code={code} isDaytime={isDaytime} />,
        );

        expect(container.querySelector("svg")).toBeTruthy();

        unmount();
      }
    }
  });
});
