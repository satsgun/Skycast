import { useEffect, useRef } from "react";
import type { KeyboardEvent } from "react";

import "./SettingsOverlay.css";

export interface SettingsOverlayProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SettingsOverlay({ isOpen, onClose }: SettingsOverlayProps) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (isOpen) {
      closeButtonRef.current?.focus();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    if (event.key === "Escape") {
      onClose();
    }
  }

  return (
    <>
      <div
        className="skycast-settings-backdrop"
        data-testid="settings-backdrop"
        onClick={onClose}
      />
      <div
        className="skycast-settings-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
        onKeyDown={handleKeyDown}
      >
        <div className="skycast-settings-panel__header">
          <h2>⚙ Settings</h2>
          <button
            ref={closeButtonRef}
            type="button"
            className="skycast-settings-panel__close"
            aria-label="Close settings"
            onClick={onClose}
          >
            ✕
          </button>
        </div>
        <p className="skycast-settings-panel__placeholder">
          Settings coming soon.
        </p>
      </div>
    </>
  );
}
