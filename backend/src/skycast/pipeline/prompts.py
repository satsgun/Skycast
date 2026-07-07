"""Stage-1 decompose system prompt -- placeholder (Task 14.6).

Contract this prompt must satisfy once authored:
- Input: the natural-language query plus session context (default
  location, units hint, carried location/time from the prior turn, and
  the caller-supplied `now` -- see SessionContext, decompose._build_user_
  message).
- Output: exactly one tool call to `emit_data_needs` whose arguments
  match `DataNeedsSpec`'s schema -- no free text.
- The model must resolve relative time expressions ("this evening",
  "tomorrow") to concrete `TimeWindow` bounds itself, using the target
  location's timezone and the `now` supplied in context -- never assume
  UTC or guess a timezone-naive "now" of its own.

The prompt text below is a placeholder, not real content -- the user
authors it separately. decompose() loads this constant so the real
prompt can be swapped in later without touching pipeline logic.
"""

DECOMPOSE_SYSTEM_PROMPT = "PLACEHOLDER: stage-1 decompose system prompt not yet authored (Task 14.6)."
