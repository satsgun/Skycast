import { STARTER_CHIPS } from "../state/chips";
import "./EmptyState.css";

const STARTER_CHIP_ICONS = ["👕", "☂", "📅", "⇄"];

export interface EmptyStateProps {
  hasDefaultLocation: boolean;
  onSubmit: (text: string) => void;
}

export function EmptyState({ hasDefaultLocation, onSubmit }: EmptyStateProps) {
  return (
    <div className="skycast-empty-state">
      {!hasDefaultLocation && (
        <div className="skycast-empty-state__location-prompt">
          <p>Ask about a place to see current conditions here.</p>
        </div>
      )}
      <p className="skycast-empty-state__heading">
        What would you like to know?
      </p>
      <div className="skycast-empty-state__chips">
        {STARTER_CHIPS.map((chip, index) => (
          <button
            key={chip}
            type="button"
            className="skycast-empty-state__chip"
            onClick={() => onSubmit(chip)}
          >
            <span aria-hidden="true">{STARTER_CHIP_ICONS[index]}</span>
            <span>{chip}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
