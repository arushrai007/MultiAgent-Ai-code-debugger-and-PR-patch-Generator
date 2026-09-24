"""
Unit tests for Member 1 - Tree-sitter Code Parser (src/tools/code_parser.py).
Tests function listing, function extraction, class methods, nested functions,
decorators, syntax error resilience, and large 1000+ line files.
"""

import pytest
from src.tools.code_parser import list_functions, extract_function, extract_all_functions


def test_1_function_listing():
    """Test 1: Verify list_functions finds basic top-level functions."""
    source = """
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
"""
    funcs = list_functions(source)
    assert "add" in funcs
    assert "subtract" in funcs
    assert funcs == ["add", "subtract"]


def test_2_function_extraction():
    """Test 2: Verify extract_function returns correct name, code, line_start, line_end."""
    source = """def add(a, b):
    # Sum two numbers
    return a + b
"""
    fn_info = extract_function(source, "add")
    assert fn_info is not None
    assert fn_info["name"] == "add"
    assert "return a + b" in fn_info["code"]
    assert fn_info["line_start"] == 1
    assert fn_info["line_end"] == 3


def test_3_class_method():
    """Test 3: Verify parser detects methods defined inside classes."""
    source = """
class Calculator:
    def __init__(self):
        self.history = []

    def multiply(self, a, b):
        result = a * b
        self.history.append(result)
        return result
"""
    funcs = list_functions(source)
    assert "__init__" in funcs
    assert "multiply" in funcs

    mult_info = extract_function(source, "multiply")
    assert mult_info is not None
    assert mult_info["name"] == "multiply"
    assert "result = a * b" in mult_info["code"]
    assert mult_info["line_start"] == 6
    assert mult_info["line_end"] == 9


def test_4_large_source_file():
    """Test 4: Verify Tree-sitter parses a 1000+ line file and locates key functions."""
    # Generate a realistic synthetic file with 1000+ lines
    blocks = [
        "\"\"\"Large synthetic e-commerce module.\"\"\"\n",
        "def calculate_cart_total(items):\n    return sum(item['price'] for item in items)\n\n",
        "def apply_discount(amount, percent):\n    return amount * (1.0 - percent / 100.0)\n\n",
    ]

    # Pad with intermediate functions to reach 1000+ lines
    for i in range(1, 180):
        blocks.append(
            f"def helper_service_operation_{i:03d}(x, y):\n"
            f"    \"\"\"Service operation {i}.\"\"\"\n"
            f"    factor = {i} * 2.5\n"
            f"    intermediate = (x + y) * factor\n"
            f"    return intermediate / (factor + 1.0)\n\n"
        )

    blocks.append("def reserve_inventory(product_id, quantity):\n    return True\n")
    large_source = "".join(blocks)

    lines = large_source.splitlines()
    assert len(lines) >= 1000, f"Generated file has {len(lines)} lines, expected >= 1000"

    funcs = list_functions(large_source)
    assert "calculate_cart_total" in funcs
    assert "apply_discount" in funcs
    assert "reserve_inventory" in funcs

    cart_fn = extract_function(large_source, "calculate_cart_total")
    assert cart_fn is not None
    assert cart_fn["line_start"] == 2
    assert cart_fn["line_end"] == 3

    reserve_fn = extract_function(large_source, "reserve_inventory")
    assert reserve_fn is not None
    assert reserve_fn["line_start"] > 1000


def test_nested_and_async_functions():
    """Verify parser extracts inner nested functions and async functions."""
    source = """
async def fetch_user(user_id):
    def validate_id():
        return user_id > 0
    if validate_id():
        return {"id": user_id}
    return None
"""
    funcs = list_functions(source)
    assert "fetch_user" in funcs
    assert "validate_id" in funcs

    inner_info = extract_function(source, "validate_id")
    assert inner_info is not None
    assert inner_info["name"] == "validate_id"
    assert inner_info["line_start"] == 3
    assert inner_info["line_end"] == 4


def test_decorated_function():
    """Verify decorated functions include decorator lines in line_start."""
    source = """@staticmethod
@pytest.fixture
def sample_fixture():
    return 42
"""
    info = extract_function(source, "sample_fixture")
    assert info is not None
    assert info["line_start"] == 1
    assert info["line_end"] == 4
    assert "@staticmethod" in info["code"]


def test_nonexistent_function_returns_none():
    """Verify searching for a non-existent function returns None."""
    source = "def foo(): pass"
    assert extract_function(source, "does_not_exist") is None


def test_syntax_error_graceful_handling():
    """Verify code with syntax errors does not crash the parser."""
    broken_source = """def good_func():
    return 1

def broken_func(x, y):
    # Operator syntax error
    return x +* y

def another_good_func():
    return 2
"""
    funcs = list_functions(broken_source)
    assert "good_func" in funcs
    assert "broken_func" in funcs
    assert "another_good_func" in funcs
