import pytest
from pydantic import ValidationError

from skycast.pipeline.synthesis_output import SynthesisOutput
from skycast.sse.payloads import ForecastBlock, Highlight, ReadingLocator


def _highlight(forecast_index: int = 0) -> Highlight:
    return Highlight(
        forecast_index=forecast_index, locator=ReadingLocator(block=ForecastBlock.CURRENT)
    )


def test_constructs_with_text_and_highlight() -> None:
    highlight = _highlight()
    output = SynthesisOutput(text="Yes, bring an umbrella.", highlight=highlight)
    assert output.text == "Yes, bring an umbrella."
    assert output.highlight == highlight


def test_constructs_with_text_and_no_highlight() -> None:
    output = SynthesisOutput(text="Clear skies all day.")
    assert output.highlight is None


def test_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        SynthesisOutput(text="")


def test_rejects_highlight_with_negative_forecast_index() -> None:
    with pytest.raises(ValidationError):
        SynthesisOutput(
            text="Yes.",
            highlight=Highlight(
                forecast_index=-1, locator=ReadingLocator(block=ForecastBlock.CURRENT)
            ),
        )


def test_rejects_structurally_invalid_nested_locator() -> None:
    with pytest.raises(ValidationError):
        SynthesisOutput(
            text="Yes.",
            highlight=Highlight(
                forecast_index=0, locator=ReadingLocator(block=ForecastBlock.CURRENT, index=0)
            ),
        )


def test_is_frozen() -> None:
    output = SynthesisOutput(text="Yes.")
    with pytest.raises(ValidationError):
        output.text = "No."


def test_round_trips_through_json_with_highlight() -> None:
    output = SynthesisOutput(text="Yes, bring an umbrella.", highlight=_highlight())
    restored = SynthesisOutput.model_validate_json(output.model_dump_json())
    assert restored == output


def test_round_trips_through_json_with_no_highlight() -> None:
    output = SynthesisOutput(text="Clear skies all day.")
    restored = SynthesisOutput.model_validate_json(output.model_dump_json())
    assert restored == output
