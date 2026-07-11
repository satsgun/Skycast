import type { StepPayload } from "../contract";
import "./ThinkingState.css";

export interface ThinkingStateProps {
  steps: StepPayload[];
}

export function ThinkingState({ steps }: ThinkingStateProps) {
  return (
    <div className="skycast-thinking" role="status" aria-live="polite">
      <p className="skycast-thinking__header">
        Working on it <span aria-hidden="true">• • •</span>
      </p>
      {steps.length > 0 && (
        <ul className="skycast-thinking__steps">
          {steps.map((step, index) => {
            const isActive = index === steps.length - 1;
            return (
              <li
                key={index}
                className={
                  isActive
                    ? "skycast-thinking__step skycast-thinking__step--active"
                    : "skycast-thinking__step skycast-thinking__step--done"
                }
              >
                <span
                  className="skycast-thinking__indicator"
                  aria-hidden="true"
                >
                  {isActive ? "◍" : "✓"}
                </span>
                <span>{step.label}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
