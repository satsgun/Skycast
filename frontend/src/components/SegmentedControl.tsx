import "./SegmentedControl.css";

export interface SegmentedControlOption<T extends string> {
  value: T;
  label: string;
}

export interface SegmentedControlProps<T extends string> {
  label: string;
  options: SegmentedControlOption<T>[];
  value: T;
  onChange: (value: T) => void;
}

export function SegmentedControl<T extends string>({
  label,
  options,
  value,
  onChange,
}: SegmentedControlProps<T>) {
  return (
    <div className="skycast-segmented">
      <span className="skycast-segmented__label">{label}</span>
      <div className="skycast-segmented__track" role="group" aria-label={label}>
        {options.map((option) => {
          const isSelected = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={isSelected}
              className={
                isSelected
                  ? "skycast-segmented__option skycast-segmented__option--selected"
                  : "skycast-segmented__option"
              }
              onClick={() => onChange(option.value)}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
