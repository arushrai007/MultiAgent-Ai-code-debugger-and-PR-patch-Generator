from src.state import DebugState
from src.llm import call_llm_json


def run(state: DebugState) -> dict:
    analysis = state.get("analysis", {})
    source_code = state.get("source_code", "")

    prompt = f"""
Generate 3-5 pytest tests that reproduce the identified bug.

Analysis:
{analysis}

Source code:
{source_code}

The tests must:
- Reproduce the bug in the current code
- Pass after the bug is fixed
- Cover relevant edge cases

Return JSON in this format:
{{
    "tests": "complete pytest code as a string"
}}
"""

    result = call_llm_json(
        "You are a test-generation expert. Generate precise pytest tests.",
        prompt
    )

    return {
        "generated_tests": result["tests"],
        "logs": state.get("logs", []) + ["Test Generator: generated tests"]
    }