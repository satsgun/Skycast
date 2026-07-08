"""Stage system prompts -- placeholders (Tasks 14.6, 17.4).

The prompt text below is a placeholder, not real content -- the user
authors each one separately. decompose()/synthesize() load these
constants so the real prompts can be swapped in later without touching
pipeline logic.
"""

# Stage-1 decompose system prompt (Task 14.6). Contract this prompt must
# satisfy once authored:
# - Input: the natural-language query plus session context (default
#   location, units hint, carried location/time from the prior turn, and
#   the caller-supplied `now` -- see SessionContext, decompose._build_user_
#   message).
# - Output: exactly one tool call to `emit_data_needs` whose arguments
#   match `DataNeedsSpec`'s schema -- no free text.
# - The model must resolve relative time expressions ("this evening",
#   "tomorrow") to concrete `TimeWindow` bounds itself, using the target
#   location's timezone and the `now` supplied in context -- never assume
#   UTC or guess a timezone-naive "now" of its own.
DECOMPOSE_SYSTEM_PROMPT = "PLACEHOLDER: stage-1 decompose system prompt not yet authored (Task 14.6)."

# Stage-4 synthesize system prompt (Task 17.4). Contract this prompt must
# satisfy once authored:
# - Input: the query intent plus a compact rendering of the resolved
#   Forecast(s) -- see synthesize_stage._build_user_message.
# - Output: exactly one tool call to `emit_synthesis` whose arguments
#   match `SynthesisOutput`'s schema -- no free text.
# - `text` must be answer-first: lead with the decision/exception (e.g.
#   "Yes, bring an umbrella" before the supporting detail), 1-2 sentences.
# - `highlight` identifies which forecast and which reading the answer is
#   about (a forecast index plus a block/index locator), or null if
#   nothing specific is being called out -- the model owns this
#   judgment; never fabricate a highlight it can't back with a specific
#   reading.
# - For QueryIntent.COMPARISON, the prose must actually compare the
#   forecasts (e.g. "Dallas is warmer than Austin today") -- not merely
#   describe one of them.
SYNTHESIZE_SYSTEM_PROMPT = "PLACEHOLDER: stage-4 synthesize system prompt not yet authored (Task 17.4)."
