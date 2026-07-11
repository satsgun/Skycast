import { useState } from "react";
import type { KeyboardEvent } from "react";

import type { MainState } from "../state/machine";
import "./InputBar.css";

export function placeholderFor(main: MainState): string {
  switch (main.type) {
    case "answer":
      return "Ask a follow-up…";
    case "clarify":
      return "Or type the full city name…";
    case "empty":
    case "thinking":
    case "error":
      return "Ask about the weather…";
  }
}

export interface InputBarProps {
  mainState: MainState;
  onSubmit: (text: string) => void;
}

export function InputBar({ mainState, onSubmit }: InputBarProps) {
  const [value, setValue] = useState("");

  function submit(): void {
    const trimmed = value.trim();
    if (trimmed === "") return;
    onSubmit(trimmed);
    setValue("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key === "Enter") {
      submit();
    }
  }

  return (
    <div className="skycast-input-bar">
      <input
        type="text"
        className="skycast-input-bar__field"
        value={value}
        placeholder={placeholderFor(mainState)}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      <button
        type="button"
        className="skycast-input-bar__send"
        aria-label="Send"
        onClick={submit}
      >
        ↑
      </button>
    </div>
  );
}
