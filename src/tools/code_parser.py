"""
Code parser tool using Tree-sitter and tree-sitter-python.
Provides AST extraction of Python functions and their line ranges.
"""

from typing import List, Optional, Dict, Any

# Initialize Tree-sitter Python parser
_tree_sitter_available = False
_parser = None

try:
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser

    _py_lang = Language(tspython.language())
    _parser = Parser(_py_lang)
    _tree_sitter_available = True
except Exception:
    _tree_sitter_available = False


def _parse_with_tree_sitter(source_code: str) -> List[Dict[str, Any]]:
    """Parse python code using Tree-sitter to find all function definitions."""
    if not source_code or not _parser:
        return []

    code_bytes = source_code.encode("utf-8")
    tree = _parser.parse(code_bytes)
    results = []

    def traverse(node):
        if node.type in ("function_definition", "async_function_definition"):
            name_node = node.child_by_field_name("name")
            if name_node:
                func_name = code_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8")
                # Include decorator lines if function is decorated
                target_node = (
                    node.parent
                    if (node.parent and node.parent.type == "decorated_definition")
                    else node
                )
                func_code = code_bytes[target_node.start_byte:target_node.end_byte].decode("utf-8")

                # 1-indexed line numbers
                line_start = target_node.start_point[0] + 1
                line_end = target_node.end_point[0] + 1

                results.append({
                    "name": func_name,
                    "code": func_code,
                    "line_start": line_start,
                    "line_end": line_end,
                })

        for child in node.children:
            traverse(child)

    traverse(tree.root_node)
    return results


def _parse_with_ast_fallback(source_code: str) -> List[Dict[str, Any]]:
    """Fallback parser using Python's built-in ast module if Tree-sitter is unavailable."""
    import ast
    if not source_code:
        return []

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    lines = source_code.splitlines(keepends=True)
    results = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_name = node.name
            start_line = node.lineno
            end_line = getattr(node, "end_lineno", start_line)
            func_code = "".join(lines[start_line - 1:end_line])
            results.append({
                "name": func_name,
                "code": func_code,
                "line_start": start_line,
                "line_end": end_line,
            })

    return results


def extract_all_functions(source_code: str) -> List[Dict[str, Any]]:
    """
    Extracts all functions from source code with code snippet and line ranges.
    Uses Tree-sitter if available, with automatic fallback to standard AST.
    """
    if _tree_sitter_available:
        try:
            return _parse_with_tree_sitter(source_code)
        except Exception:
            return _parse_with_ast_fallback(source_code)
    return _parse_with_ast_fallback(source_code)


def list_functions(source_code: str) -> list:
    """
    Returns a list of all function and method names present in the source code.
    
    Supports:
    - Standard functions
    - Methods inside classes
    - Async functions
    - Nested / inner functions

    Example:
        >>> source = "def add(a, b): return a + b\\ndef calculate_total(items): return sum(items)"
        >>> list_functions(source)
        ['add', 'calculate_total']
    """
    if not source_code or not source_code.strip():
        return []
    funcs = extract_all_functions(source_code)
    return [f["name"] for f in funcs]


def extract_function(source_code: str, function_name: str) -> Optional[dict]:
    """
    Finds and extracts a specific function by name using Tree-sitter.

    Args:
        source_code: Python source code string.
        function_name: Name of the function to extract.

    Returns:
        A dictionary containing:
            {
                "name": function_name,
                "code": "...full function source...",
                "line_start": 10,
                "line_end": 25
            }
        Or None if the function cannot be found.
    """
    if not source_code or not function_name:
        return None

    funcs = extract_all_functions(source_code)
    for f in funcs:
        if f["name"] == function_name:
            return f
    return None
