import type { ErrorPayload } from "../contract";
import { errorKindLabel, isSystemError } from "../format/errorKind";
import type { ErrorAction } from "../state/errorActions";
import "./ErrorView.css";

export interface ErrorViewProps {
  error: ErrorPayload;
  actions: ErrorAction[];
  onRetry: () => void;
  onShowCached: () => void;
  onOpenSettings: () => void;
}

function minutesSince(isoTimestamp: string): number {
  return Math.floor((Date.now() - new Date(isoTimestamp).getTime()) / 60_000);
}

function freshnessLine(cachedAt: string): string {
  const minutes = minutesSince(cachedAt);
  const unit = minutes === 1 ? "minute" : "minutes";
  return `Your last data was from ${minutes} ${unit} ago.`;
}

export function ErrorView({
  error,
  actions,
  onRetry,
  onShowCached,
  onOpenSettings,
}: ErrorViewProps) {
  const isSystem = isSystemError(error.kind);
  const cachedAction = actions.find(
    (action): action is Extract<ErrorAction, { type: "show_cached" }> =>
      action.type === "show_cached",
  );

  return (
    <div className="skycast-error-view">
      <span
        className={
          isSystem
            ? "skycast-error-view__pill skycast-error-view__pill--danger"
            : "skycast-error-view__pill"
        }
      >
        {errorKindLabel(error.kind)}
      </span>
      <div
        className={
          isSystem
            ? "skycast-error-view__card skycast-error-view__card--danger"
            : "skycast-error-view__card"
        }
      >
        <div className="skycast-error-view__header">
          <span className="skycast-error-view__icon" aria-hidden="true">
            {isSystem ? "⊗" : "⊘"}
          </span>
          <p className="skycast-error-view__message">{error.message}</p>
        </div>
        {cachedAction !== undefined && (
          <p className="skycast-error-view__freshness">
            {freshnessLine(cachedAction.cachedAt)}
          </p>
        )}
        <div className="skycast-error-view__actions">
          {actions.map((action, index) => {
            switch (action.type) {
              case "retry":
                return (
                  <button
                    key={index}
                    type="button"
                    className="skycast-error-view__action"
                    onClick={onRetry}
                  >
                    ↻ Retry
                  </button>
                );
              case "show_cached":
                return (
                  <button
                    key={index}
                    type="button"
                    className="skycast-error-view__action"
                    onClick={onShowCached}
                  >
                    Show last cached
                  </button>
                );
              case "open_settings":
                return (
                  <button
                    key={index}
                    type="button"
                    className="skycast-error-view__action"
                    onClick={onOpenSettings}
                  >
                    Review settings
                  </button>
                );
              case "retry_free_text":
                return (
                  <p key={index} className="skycast-error-view__guidance">
                    Try a different spelling, or type a new search below.
                  </p>
                );
            }
          })}
        </div>
      </div>
    </div>
  );
}
