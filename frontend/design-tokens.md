# Design tokens (F3.0)

Values below are derived from the SkyCast UX mockups (GitHub wiki,
`03-‐-SkyCast-—-UX-Design` page), not freshly designed. Six of the
seven mockups are schematic SVGs with literal hex colors, coordinates,
and text; the seventh (`01-primary-response.png`) is a rendered PNG
confirming the same visual language but has no extractable literal
values, so it isn't cited as a per-value source below.

Implementation: `src/styles/tokens.css` (`:root`-scoped CSS custom
properties, prefixed `--skycast-`). Loaded once, globally, via
`src/main.tsx`.

## Color

| Token                                    | Value     | Source                                                       |
| ---------------------------------------- | --------- | ------------------------------------------------------------ |
| `--skycast-color-bg`                     | `#F1EFE8` | root `<rect>` fill, every mockup                             |
| `--skycast-color-surface`                | `#FFFFFF` | card/panel fill, every mockup                                |
| `--skycast-color-border-subtle`          | `#D3D1C7` | hairline dividers, card outlines                             |
| `--skycast-color-border-default`         | `#B4B2A9` | button/input/chip borders                                    |
| `--skycast-color-text-primary`           | `#2C2C2A` | headings, primary body text                                  |
| `--skycast-color-text-secondary`         | `#5F5E5A` | secondary body text                                          |
| `--skycast-color-text-tertiary`          | `#888780` | placeholder/tertiary text                                    |
| `--skycast-color-text-muted`             | `#B4B2A9` | faintest labels (e.g. low-temp readout in `02-multiday.svg`) |
| `--skycast-color-text-on-surface-action` | `#444441` | secondary button labels                                      |
| `--skycast-color-accent`                 | `#185FA5` | brand blue -- icons, links, active state                     |
| `--skycast-color-accent-bg`              | `#E6F1FB` | chip/badge/user-bubble/highlighted-card background           |
| `--skycast-color-accent-strong`          | `#0C447C` | user-message text                                            |
| `--skycast-color-accent-border`          | `#378ADD` | highlighted-card border (Sunday in `02-multiday.svg`)        |
| `--skycast-color-success`                | `#1D9E75` | completed-step checkmarks, `03-thinking.svg`                 |
| `--skycast-color-danger`                 | `#A32D2D` | error icon/text, `04-errors.svg`                             |
| `--skycast-color-danger-border`          | `#E24B4A` | offline-error card border, `04-errors.svg`                   |
| `--skycast-color-danger-bg`              | `#FCEBEB` | offline-error badge background, `04-errors.svg`              |

## Typography

`--skycast-font-family` is `-apple-system, "Segoe UI", Roboto,
sans-serif` in every mockup.

Size scale, collected from every observed `font-size` across
`02`-`07`: `xs` 11px (tiny badges), `sm` 12px (chip/secondary text),
`base` 13px (body -- the most common size), `md` 14px (settings row
labels), `lg` 15px (wordmark), `xl` 16px (empty-state prompt), `2xl`
18px (settings header), `3xl` 22px (daily-card weather glyph), `4xl`
30px (current-temp readout), `5xl` 44px (hero condition icon).

Weight: `regular` 400 (default), `medium` 500 (`font-weight="500"` in
mockups -- headers, wordmark, temps, active labels).

## Radii

Three-tier scale used consistently across every mockup: `lg` 16px
(outer view containers), `md` 12px (cards -- message bubbles, daily
cards, thinking card, error card), `sm` 8px (buttons, chips, inputs,
badges, icon badges). `07-settings.svg`'s unit-selector segmented
control adds a fourth tier, `xs` 6px, for its inner selected pill.
`full` (999px) covers fully-rounded pill controls (e.g. the settings
toggle switch, `rx=12` at `height=24` -- exactly a capsule, not a
fixed-px radius).

`--skycast-size-icon-badge` (28px): the Skycast logo badge and the
agent-avatar circle are consistently 28px square/diameter across
every mockup that has them.

## Spacing

Inferred base-4 scale (4/8/12/16/20/24/32px) fitting the observed
edge padding (20-28px) and stacked-element gaps. This is an
**inference**, not a literal per-pixel match to every mockup
coordinate -- some observed deltas are text baseline/leading
artifacts, not layout gaps, and weren't used to derive the scale.

## Borders

Mockups specify `stroke-width="0.5"` on every card/button/input
border. Sub-pixel CSS borders render inconsistently across browsers
and zoom levels, so `--skycast-border-width` is rounded up to the
minimum reliably-renderable value, 1px. This is a deliberate rounding,
not a mockup-literal value.

## Motion

Mockups are static images -- no durations to derive. The
`prefers-reduced-motion: reduce` override in `tokens.css` is standard,
view-independent boilerplate. `--skycast-motion-duration-fast` (150ms)
and `--skycast-motion-duration-base` (250ms) are placeholder tokens
for F3.1+ to consume; they are conventional defaults, not
mockup-derived.

## Icon source

`react-icons/wi` (Erik Flowers' "Weather Icons" font, wrapped as
tree-shakeable SVG React components; MIT wrapper license, SIL OFL 1.1
icon license) was chosen over Meteocons (the ticket's own listed
example) because Weather Icons' flat monochrome line style matches
the mockups' black glyph aesthetic, where Meteocons' colorful gradient
illustrations don't -- and because Weather Icons has granular
WMO-shaped condition coverage (drizzle vs. freezing-drizzle vs.
freezing-rain vs. sleet) that a generic UI icon set lacks. Every
export referenced below was verified against the npm-published
`react-icons@5.7.0` `.d.ts`, not assumed from memory.

`src/icons/iconSource.tsx` binds every `IconName` (defined in
`src/icons/conditionIcons.ts`, F1.3) to a real component:

| IconName             | Component                |
| -------------------- | ------------------------ |
| `clear-day`          | `WiDaySunny`             |
| `clear-night`        | `WiNightClear`           |
| `mainly-clear-day`   | `WiDaySunnyOvercast`     |
| `mainly-clear-night` | `WiNightAltPartlyCloudy` |
| `partly-cloudy`      | `WiCloud`                |
| `cloudy`             | `WiCloudy`               |
| `fog`                | `WiFog`                  |
| `drizzle`            | `WiSprinkle`             |
| `freezing-drizzle`   | `WiRainMix`              |
| `rain`               | `WiRain`                 |
| `heavy-rain`         | `WiRainWind`             |
| `freezing-rain`      | `WiSleet`                |
| `snow`               | `WiSnow`                 |
| `heavy-snow`         | `WiSnowWind`             |
| `rain-showers`       | `WiShowers`              |
| `snow-showers`       | `WiSnowflakeCold`        |
| `thunderstorm`       | `WiThunderstorm`         |
| `unknown`            | `WiNa`                   |

Notes:

- All 17 non-`unknown` glyphs deliberately use each icon family's
  **neutral** (non `Day`/`Night`-prefixed) export where one exists.
  Every `IconName` other than `clear-*`/`mainly-clear-*` is
  day/night-invariant per `conditionIcons.ts`'s
  `NIGHT_ICON_OVERRIDES`, so a glyph shown at any time of day
  shouldn't carry a `Day`/`Night` prefix in its own design.
  `clear-*`/`mainly-clear-*` are the only entries that intentionally
  use time-of-day-prefixed components, matching their day/night split.
- `snow-showers` -> `WiSnowflakeCold` is the one imperfect fit: no
  neutral "snow shower" glyph exists in the set. Accepted as an
  engineering judgment call, not a mockup-derived choice -- the
  mockups render weather glyphs as plain emoji (`☀ ☁ ⛈ 🌧`), so they
  dictate icon _style_ (simple monochrome line art), not the specific
  _choice_ of icon for every condition.
- The `Record<IconName, IconType>` type on `ICON_COMPONENTS` makes a
  missing entry a compile-time error, the same exhaustiveness pattern
  `conditionIcons.ts` already uses for `CONDITION_ICON_MAP`.

## Token-usage check

`tests/styles/tokenUsage.test.ts` scans `src/**/*.{ts,tsx}` for raw
hex-color literals and fails if any exist outside `styles/tokens.css`.
This is deliberately scoped to hex colors only, not `px`: `px` has too
many legitimate non-themed uses (hairline border widths, `1px`
resets) to flag categorically, where a raw hex color virtually always
means a value that should have come from a token instead.
