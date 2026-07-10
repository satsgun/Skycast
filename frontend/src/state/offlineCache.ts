import { useState } from "react";

import type { AnswerPayload } from "../contract";
import { clearPersisted, readPersisted, writePersisted } from "./persistence";

export interface CachedAnswer {
  answer: AnswerPayload;
  cachedAt: string;
}

export interface UseOfflineCacheResult {
  cached: CachedAnswer | null;
  cacheAnswer: (answer: AnswerPayload) => void;
  clearCache: () => void;
  minutesSinceCached: () => number | null;
}

const STORAGE_KEY = "skycast:offline-cache";

export function useOfflineCache(): UseOfflineCacheResult {
  const [cached, setCached] = useState<CachedAnswer | null>(() =>
    readPersisted<CachedAnswer | null>(STORAGE_KEY, null),
  );

  function cacheAnswer(answer: AnswerPayload): void {
    const next: CachedAnswer = { answer, cachedAt: new Date().toISOString() };
    writePersisted(STORAGE_KEY, next);
    setCached(next);
  }

  function clearCache(): void {
    clearPersisted(STORAGE_KEY);
    setCached(null);
  }

  function minutesSinceCached(): number | null {
    if (cached === null) {
      return null;
    }
    return Math.floor(
      (Date.now() - new Date(cached.cachedAt).getTime()) / 60000,
    );
  }

  return { cached, cacheAnswer, clearCache, minutesSinceCached };
}
