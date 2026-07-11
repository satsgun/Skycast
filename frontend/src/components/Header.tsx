import "./Header.css";

export interface HeaderProps {
  locationName: string | null;
  onOpenSettings: () => void;
}

export function Header({ locationName, onOpenSettings }: HeaderProps) {
  return (
    <header className="skycast-header">
      <div className="skycast-header__brand">
        <span className="skycast-header__logo" aria-hidden="true">
          ☁
        </span>
        <span className="skycast-header__wordmark">Skycast</span>
      </div>
      <div className="skycast-header__right">
        {locationName !== null && (
          <span
            className="skycast-header__location"
            data-testid="header-location"
          >
            📍 {locationName}
          </span>
        )}
        <button
          type="button"
          className="skycast-header__settings"
          aria-label="Open settings"
          onClick={onOpenSettings}
        >
          ⚙
        </button>
      </div>
    </header>
  );
}
