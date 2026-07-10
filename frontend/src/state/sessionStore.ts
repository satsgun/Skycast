import { useState } from "react";

import type { Location } from "../contract";
import { readPersisted, writePersisted } from "./persistence";

export interface TimeWindow {
  start: string;
  end: string;
}

export interface SessionState {
  lastLocation: Location | null;
  lastTimeWindow: TimeWindow | null;
  queryHistory: string[];
  lastActivityAt: string;
}

export interface RecordActivityEntry {
  query: string;
  location?: Location;
  timeWindow?: TimeWindow;
}

export interface UseSessionStoreResult {
  session: SessionState;
  recordActivity: (entry: RecordActivityEntry) => void;
  clearSession: () => void;
}

const STORAGE_KEY = "skycast:session";
const SESSION_WINDOW_MS = 30 * 60 * 1000;
const MAX_QUERY_HISTORY = 10;

function emptySession(): SessionState {
  return {
    lastLocation: null,
    lastTimeWindow: null,
    queryHistory: [],
    lastActivityAt: new Date(0).toISOString(),
  };
}

function loadSession(): SessionState {
  const stored = readPersisted<SessionState>(STORAGE_KEY, emptySession());
  const isExpired =
    Date.now() - new Date(stored.lastActivityAt).getTime() > SESSION_WINDOW_MS;
  return isExpired ? emptySession() : stored;
}

export function useSessionStore(): UseSessionStoreResult {
  const [session, setSession] = useState<SessionState>(loadSession);

  function recordActivity(entry: RecordActivityEntry): void {
    setSession((previous) => {
      const next: SessionState = {
        lastLocation: entry.location ?? previous.lastLocation,
        lastTimeWindow: entry.timeWindow ?? previous.lastTimeWindow,
        queryHistory: [...previous.queryHistory, entry.query].slice(
          -MAX_QUERY_HISTORY,
        ),
        lastActivityAt: new Date().toISOString(),
      };
      writePersisted(STORAGE_KEY, next);
      return next;
    });
  }

  function clearSession(): void {
    const next = emptySession();
    writePersisted(STORAGE_KEY, next);
    setSession(next);
  }

  return { session, recordActivity, clearSession };
}
