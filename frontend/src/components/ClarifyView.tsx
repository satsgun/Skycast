import type { Location } from "../contract";
import { formatPopulation } from "../format/population";
import "./ClarifyView.css";

export interface ClarifyViewProps {
  candidates: Location[];
  forLocationName: string;
  onSelect: (candidate: Location) => void;
}

function subtitleFor(candidate: Location): string | null {
  const parts: string[] = [];
  if (candidate.country !== null) parts.push(candidate.country);
  if (candidate.population !== null) {
    parts.push(`pop. ${formatPopulation(candidate.population)}`);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

export function ClarifyView({
  candidates,
  forLocationName,
  onSelect,
}: ClarifyViewProps) {
  return (
    <div className="skycast-clarify-view">
      <p className="skycast-clarify-view__prompt">
        There are a few {forLocationName}s — which one?
      </p>
      <div className="skycast-clarify-view__options">
        {candidates.map((candidate) => {
          const subtitle = subtitleFor(candidate);
          return (
            <button
              key={candidate.id}
              type="button"
              className="skycast-clarify-view__option"
              onClick={() => onSelect(candidate)}
            >
              <span className="skycast-clarify-view__pin" aria-hidden="true">
                📍
              </span>
              <span className="skycast-clarify-view__text">
                <span className="skycast-clarify-view__title">
                  {candidate.name}
                  {candidate.admin1 !== null && `, ${candidate.admin1}`}
                </span>
                {subtitle !== null && (
                  <span className="skycast-clarify-view__subtitle">
                    {subtitle}
                  </span>
                )}
              </span>
              <span
                className="skycast-clarify-view__chevron"
                aria-hidden="true"
              >
                ›
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
