import type {
  AnswerCard,
  AnswerPayload,
  Location,
  ReadingLocator,
} from "../contract";
import type { UnitsSettings } from "../state/settingsStore";
import { ForecastCard } from "./ForecastCard";
import "./AnswerView.css";

export interface AnswerViewProps {
  answer: AnswerPayload;
  isStale: boolean;
  followUpChips: string[];
  units: UnitsSettings;
  onSubmit: (text: string) => void;
  defaultLocation: Location | null;
  onSetDefaultLocation: (location: Location) => void;
}

function resolveHighlightLocator(
  card: AnswerCard,
  forecastIndex: number,
): ReadingLocator | null {
  if (card.highlight === null) return null;
  return card.highlight.forecast_index === forecastIndex
    ? card.highlight.locator
    : null;
}

export function AnswerView({
  answer,
  isStale,
  followUpChips,
  units,
  onSubmit,
  defaultLocation,
  onSetDefaultLocation,
}: AnswerViewProps) {
  return (
    <div className="skycast-answer-view">
      <p className="skycast-answer-view__conclusion">{answer.text}</p>
      {isStale && (
        <p className="skycast-answer-view__stale-note">Showing cached data</p>
      )}
      <div className="skycast-answer-view__forecasts">
        {answer.card.forecasts.map((forecast, index) => (
          <ForecastCard
            key={forecast.location.id}
            forecast={forecast}
            units={units}
            highlightLocator={resolveHighlightLocator(answer.card, index)}
            isDefaultLocation={forecast.location.id === defaultLocation?.id}
            onSetDefault={() => onSetDefaultLocation(forecast.location)}
          />
        ))}
      </div>
      {followUpChips.length > 0 && (
        <div className="skycast-answer-view__chips">
          {followUpChips.map((chip) => (
            <button
              key={chip}
              type="button"
              className="skycast-answer-view__chip"
              onClick={() => onSubmit(chip)}
            >
              {chip}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
