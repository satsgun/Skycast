import type { MainState } from "../state/machine";
import type { UseQueryResult } from "../state/useQuery";
import type { UseSettingsStoreResult } from "../state/settingsStore";
import { Header } from "./Header";
import { InputBar } from "./InputBar";
import { SettingsOverlay } from "./SettingsOverlay";
import "./AppShell.css";

export interface AppShellProps {
  query: UseQueryResult;
  settings: UseSettingsStoreResult;
}

/**
 * Minimal, mockup-unstyled placeholder per main-state type -- just
 * enough to prove the state wiring works end-to-end. F3.2-F3.7 each
 * replace their own case here with the real, mockup-accurate view.
 */
function renderConversation(main: MainState) {
  switch (main.type) {
    case "empty":
      return (
        <p data-testid="conversation-empty">What would you like to know?</p>
      );
    case "thinking":
      return <p>Thinking about "{main.query}"…</p>;
    case "answer":
      return (
        <div>
          <p>{main.query}</p>
          <p>{main.answer.text}</p>
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

  return (
    <div className="skycast-app-shell">
      <Header
        locationName={settings.settings.defaultLocation?.name ?? null}
        onOpenSettings={() => dispatch({ type: "OPEN_SETTINGS" })}
      />
      <main className="skycast-app-shell__conversation">
        {renderConversation(state.main)}
      </main>
      <InputBar mainState={state.main} onSubmit={submitQuery} />
      <SettingsOverlay
        isOpen={state.isSettingsOpen}
        onClose={() => dispatch({ type: "CLOSE_SETTINGS" })}
      />
    </div>
  );
}
