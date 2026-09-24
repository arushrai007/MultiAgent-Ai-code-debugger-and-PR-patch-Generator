"""
Unit tests for Member 1 - Analyzer Agent (src/agents/analyzer.py).
Tests contract adherence, input validation, LLM response validation,
Tree-sitter coordinate snapping, retry handling, and realistic bug diagnosis.
"""

import pytest
from unittest.mock import patch

from src.state import DebugState
from src.agents import analyzer


def test_analyzer_empty_source_code_raises_error():
    """Verify analyzer raises clear ValueError when source_code is missing."""
    empty_state: DebugState = {
        "source_code": "",
        "error_log": "AssertionError",
    }
    with pytest.raises(ValueError, match="Analyzer requires source_code"):
        analyzer.run(empty_state)


def test_analyzer_missing_error_log_proceeds():
    """Verify analyzer handles empty error_log gracefully and logs the event."""
    source = "def add(a, b):\n    return a + b\n"
    state: DebugState = {
        "file_path": "math_ops.py",
        "source_code": source,
        "error_log": "",
        "logs": [],
    }

    mock_llm_response = {
        "root_cause": "Inspection of source code without explicit error log.",
        "file": "math_ops.py",
        "function": "add",
        "line_start": 1,
        "line_end": 2,
    }

    with patch("src.agents.analyzer.call_llm_json", return_value=mock_llm_response):
        result = analyzer.run(state)

    assert "analysis" in result
    assert "logs" in result
    assert any("no error log was supplied" in log for log in result["logs"])
    assert result["analysis"]["function"] == "add"
    assert result["analysis"]["line_start"] == 1
    assert result["analysis"]["line_end"] == 2


def test_5_analyzer_with_hardcoded_state():
    """Test 5: Verify analyzer runs on a hardcoded state dict and returns required keys."""
    source_code = """class Cart:
    def calculate_total(self, items):
        return sum(items)

    def apply_coupon(self, code):
        return 0.10
"""
    error_log = "FAILED test_cart.py::test_total - AssertionError: assert 0 == 100\nCart.py:2: in calculate_total"

    state: DebugState = {
        "repo_path": "/workspace/ecommerce",
        "file_path": "large_ecommerce_app.py",
        "source_code": source_code,
        "error_log": error_log,
        "test_output": "",
        "logs": [],
        "attempts": 0,
        "max_attempts": 3,
    }

    mock_response = {
        "root_cause": "Empty cart items produces 0 instead of expected minimum subtotal.",
        "file": "large_ecommerce_app.py",
        "function": "calculate_total",
        "line_start": 2,
        "line_end": 3,
    }

    with patch("src.agents.analyzer.call_llm_json", return_value=mock_response):
        result = analyzer.run(state)

    # Verify result structure
    assert set(result.keys()) == {"analysis", "logs"}
    analysis = result["analysis"]
    assert "root_cause" in analysis
    assert "file" in analysis
    assert "function" in analysis
    assert "line_start" in analysis
    assert "line_end" in analysis

    assert analysis["file"] == "large_ecommerce_app.py"
    assert analysis["function"] == "calculate_total"
    assert isinstance(analysis["line_start"], int)
    assert isinstance(analysis["line_end"], int)
    assert analysis["line_start"] == 2
    assert analysis["line_end"] == 3


def test_analyzer_off_by_one_cart_total():
    """
    Test against off-by-one loop bug described in requirement 25:
    calculate_cart_total uses range(len(items) - 1), skipping the last item.
    """
    source_code = """def calculate_item_total(product_id, quantity):
    price_map = {"p1": 10.0, "p2": 20.0}
    return price_map.get(product_id, 0.0) * quantity

def calculate_cart_total(items):
    total = 0
    # BUG: range(len(items) - 1) skips the final item
    for i in range(len(items) - 1):
        total += calculate_item_total(items[i].product_id, items[i].quantity)
    return total
"""
    error_log = (
        "FAILED test_cart.py::test_cart_total - AssertionError: assert 10.0 == 30.0\n"
        "cart.py:8: in calculate_cart_total\n"
        "E   AssertionError: Final cart item is missing from total"
    )

    state: DebugState = {
        "file_path": "cart.py",
        "source_code": source_code,
        "error_log": error_log,
        "logs": ["Session initialized"],
        "attempts": 0,
        "max_attempts": 3,
    }

    mock_llm_response = {
        "root_cause": "Loop boundary range(len(items) - 1) skips the last item in the cart list.",
        "file": "cart.py",
        "function": "calculate_cart_total",
        "line_start": 5,
        "line_end": 11,
    }

    with patch("src.agents.analyzer.call_llm_json", return_value=mock_llm_response):
        result = analyzer.run(state)

    analysis = result["analysis"]
    assert analysis["function"] == "calculate_cart_total"
    assert "skips the last item" in analysis["root_cause"]
    # Tree-sitter verified coordinates
    assert analysis["line_start"] == 5
    assert analysis["line_end"] == 10


def test_analyzer_snaps_lines_to_treesitter_boundaries():
    """
    Verify that if the LLM hallucinates arbitrary or inaccurate line numbers,
    Tree-sitter provides the authoritative start and end lines for the function.
    """
    source = """def first_func():
    return 1

def target_function(a, b):
    # Important function
    return a + b

def last_func():
    return 3
"""
    state: DebugState = {
        "file_path": "example.py",
        "source_code": source,
        "error_log": "error in target_function",
    }

    # LLM hallucinates line 99 to 105
    mock_hallucinated_response = {
        "root_cause": "Logic error in target_function",
        "file": "example.py",
        "function": "target_function",
        "line_start": 99,
        "line_end": 105,
    }

    with patch("src.agents.analyzer.call_llm_json", return_value=mock_hallucinated_response):
        result = analyzer.run(state)

    # Snapped to Tree-sitter's true line bounds (lines 4 to 6)
    assert result["analysis"]["function"] == "target_function"
    assert result["analysis"]["line_start"] == 4
    assert result["analysis"]["line_end"] == 6


def test_analyzer_retry_with_test_output():
    """Verify analyzer incorporates test_output from prior failed verification attempt."""
    source = "def compute():\n    return 42\n"
    state: DebugState = {
        "file_path": "compute.py",
        "source_code": source,
        "error_log": "Initial failure",
        "test_output": "FAILED: previous patch caused regression in edge case test",
        "attempts": 1,
        "max_attempts": 3,
        "logs": ["Attempt 0 finished with test failure"],
    }

    captured_prompts = []

    def mock_call(sys_prompt, user_prompt):
        captured_prompts.append(user_prompt)
        return {
            "root_cause": "Previous fix introduced regression, adjusting diagnosis.",
            "file": "compute.py",
            "function": "compute",
            "line_start": 1,
            "line_end": 2,
        }

    with patch("src.agents.analyzer.call_llm_json", side_effect=mock_call):
        result = analyzer.run(state)

    assert len(captured_prompts) == 1
    prompt_text = captured_prompts[0]
    assert "Previous Failed Verification (Attempt #1)" in prompt_text
    assert "previous patch caused regression" in prompt_text
    assert any("incorporating previous failed test output" in log for log in result["logs"])


def test_analyzer_invalid_llm_response_raises_error():
    """Verify invalid LLM response schemas trigger a descriptive ValueError."""
    state: DebugState = {
        "file_path": "foo.py",
        "source_code": "def foo(): pass",
        "error_log": "traceback",
    }

    # Missing 'line_end'
    incomplete_response = {
        "root_cause": "Bug found",
        "file": "foo.py",
        "function": "foo",
        "line_start": 1,
    }

    with patch("src.agents.analyzer.call_llm_json", return_value=incomplete_response):
        with pytest.raises(ValueError, match="missing key 'line_end'"):
            analyzer.run(state)


def test_analyzer_llm_failure_raises_clear_runtime_error():
    """Verify that an LLM network or API failure raises a clear RuntimeError without fake stubs."""
    state: DebugState = {
        "file_path": "foo.py",
        "source_code": "def foo(): pass",
        "error_log": "traceback",
    }

    with patch("src.agents.analyzer.call_llm_json", side_effect=Exception("API connection timeout")):
        with pytest.raises(RuntimeError, match="Analyzer LLM call failed"):
            analyzer.run(state)
