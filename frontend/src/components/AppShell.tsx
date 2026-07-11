import type { MainState } from "../state/machine";
import type { UseQueryResult } from "../state/useQuery";
import type {
  UnitsSettings,
  UseSettingsStoreResult,
} from "../state/settingsStore";
import { AnswerView } from "./AnswerView";
import { EmptyState } from "./EmptyState";
import { Header } from "./Header";
import { InputBar } from "./InputBar";
import { SettingsOverlay } from "./SettingsOverlay";
import { ThinkingState } from "./ThinkingState";
import "./AppShell.css";

export interface AppShellProps {
  query: UseQueryResult;
  settings: UseSettingsStoreResult;
}

interface ConversationContext {
  units: UnitsSettings;
  onSubmit: (text: string) => void;
}

/**
 * Minimal, mockup-unstyled placeholder per main-state type -- just
 * enough to prove the state wiring works end-to-end. F3.5-F3.7 each
 * replace their own case here with the real, mockup-accurate view.
 * "empty" is handled separately by AppShell -- it's the only state
 * with a real view (EmptyState, F3.2) and needs extra props.
 */
function renderConversation(
  main: Exclude<MainState, { type: "empty" }>,
  context: ConversationContext,
) {
  switch (main.type) {
    case "thinking":
      return (
        <div>
          <p>{main.query}</p>
          <ThinkingState steps={main.steps} />
        </div>
      );
    case "answer":
      return (
        <div>
          <p>{main.query}</p>
          <AnswerView
            answer={main.answer}
            isStale={main.isStale}
            followUpChips={main.followUpChips}
            units={context.units}
            onSubmit={context.onSubmit}
          />
        </div>
      );
    case "clarify":
      return <p>{main.query}</p>;
    case "error":
      return (
        <div>
          <p>{main.query}</p>
          <p>{main.error.message}</p>
        </div>
      );
  }
}

export function AppShell({ query, settings }: AppShellProps) {
  const { state, dispatch, submitQuery } = query;

  function openSettings(): void {
    dispatch({ type: "OPEN_SETTINGS" });
  }

  return (
    <div className="skycast-app-shell">
      <Header
        locationName={settings.settings.defaultLocation?.name ?? null}
        onOpenSettings={openSettings}
      />
      <main className="skycast-app-shell__conversation">
        {state.main.type === "empty" ? (
          <EmptyState
            hasDefaultLocation={settings.settings.defaultLocation !== null}
            onSubmit={submitQuery}
            onOpenSettings={openSettings}
          />
        ) : (
          renderConversation(state.main, {
            units: settings.settings.units,
            onSubmit: submitQuery,
          })
        )}
      </main>
      <InputBar mainState={state.main} onSubmit={submitQuery} />
      <SettingsOverlay
        isOpen={state.isSettingsOpen}
        onClose={() => dispatch({ type: "CLOSE_SETTINGS" })}
      />
    </div>
  );
}
