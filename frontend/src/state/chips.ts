import type { AnswerCard, AnswerPayload, ForecastBlock } from "../contract";

const DECISION_KEYWORDS = [
  "umbrella",
  "jacket",
  "coat",
  "rain",
  "wear",
  "need",
];

export const STARTER_CHIPS: string[] = [
  "What should I wear today?",
  "Do I need an umbrella this evening?",
  "What's the weather like this weekend?",
  "Compare the weather in two cities",
];

export function generateFollowUpChips(
  query: string,
  answer: AnswerPayload,
): string[] {
  const isComparison = answer.card.forecasts.length > 1;
  const granularity = primaryGranularity(answer.card);
  const alreadyDecided =
    mentionsDecision(query) || mentionsDecision(answer.text);

  const [primaryShift, alternateShift] = timeframeChips(
    granularity,
    isComparison,
  );
  return [
    primaryShift,
    alreadyDecided ? alternateShift : decisionChip(isComparison),
  ];
}

function timeframeChips(
  granularity: ForecastBlock,
  isComparison: boolean,
): [string, string] {
  const suffix = isComparison ? " for both?" : "?";
  switch (granularity) {
    case "daily":
      return [
        `What's it like right now${suffix}`,
        `What about next week${suffix}`,
      ];
    case "hourly":
      return [
        `What about tomorrow${suffix}`,
        `What about this weekend${suffix}`,
      ];
    case "current":
      return [
        `What about this weekend${suffix}`,
        `What about tomorrow${suffix}`,
      ];
  }
}

function decisionChip(isComparison: boolean): string {
  return isComparison
    ? "Which one needs an umbrella?"
    : "Do I need an umbrella?";
}

function primaryGranularity(card: AnswerCard): ForecastBlock {
  if (card.highlight !== null) return card.highlight.locator.block;
  const forecast = card.forecasts[0];
  if (
    forecast !== undefined &&
    forecast.daily !== null &&
    forecast.daily.length > 0
  ) {
    return "daily";
  }
  if (
    forecast !== undefined &&
    forecast.hourly !== null &&
    forecast.hourly.length > 0
  ) {
    return "hourly";
  }
  return "current";
}

function mentionsDecision(text: string): boolean {
  const lower = text.toLowerCase();
  return DECISION_KEYWORDS.some((keyword) => lower.includes(keyword));
}
