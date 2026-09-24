"""
Analyzer Agent:
Diagnoses failing tests, traces root causes in source code,
and produces structured analysis coordinates (file, function, line range).
"""

import os
import re
from typing import Dict, Any, List, Optional

from src.state import DebugState
from src.llm import call_llm_json
from src.tools.code_parser import list_functions, extract_function, extract_all_functions


def _load_prompt() -> str:
    """Load system prompt from src/prompts/analyzer.md."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(current_dir, "..", "prompts", "analyzer.md")

    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    raise FileNotFoundError(f"Analyzer prompt file not found at {prompt_path}")


def _find_candidate_functions(error_log: str, available_functions: List[str]) -> List[str]:
    """
    Inspects error logs and stack traces to identify candidate functions.
    Checks traceback patterns and cross-references against AST-parsed functions.
    """
    if not error_log or not available_functions:
        return []

    candidates: List[str] = []

    # 1. Match standard Python traceback patterns: in <function_name>
    tb_matches = re.findall(r"in\s+([a-zA-Z_][a-zA-Z0-9_]*)", error_log)
    for name in tb_matches:
        if name in available_functions and name not in candidates and not name.startswith("test_"):
            candidates.append(name)

    # 2. Check for explicit mentions of available functions in the error log
    for name in available_functions:
        if name not in candidates and not name.startswith("test_"):
            pattern = rf"\b{re.escape(name)}\b"
            if re.search(pattern, error_log):
                candidates.append(name)

    return candidates


def run(state: DebugState) -> dict:
    """
    Execute root cause analysis on the provided state.

    Args:
        state: Shared DebugState dictionary. Requires 'source_code'.

    Returns:
        Dictionary updating ONLY 'analysis' and 'logs' keys:
        {
            "analysis": {
                "root_cause": str,
                "file": str,
                "function": str,
                "line_start": int,
                "line_end": int,
            },
            "logs": List[str]
        }
    """
    # 1. Validate source code presence
    source_code = state.get("source_code", "")
    if not source_code or not source_code.strip():
        raise ValueError("Analyzer requires source_code in DebugState.")

    error_log = state.get("error_log", "")
    file_path = state.get("file_path", "")
    test_output = state.get("test_output", "")
    attempts = state.get("attempts", 0)

    new_logs: List[str] = []

    # 2. Parse source code using Tree-sitter AST parser
    new_logs.append("Analyzer: parsing source code")
    all_parsed_funcs = extract_all_functions(source_code)
    func_names = [f["name"] for f in all_parsed_funcs]
    new_logs.append(f"Analyzer: found {len(func_names)} functions")

    # 3. Handle error log & detect candidate functions
    if not error_log or not error_log.strip():
        new_logs.append("Analyzer: no error log was supplied. Proceeding with source code analysis.")

    candidate_funcs = _find_candidate_functions(error_log, func_names)
    if candidate_funcs:
        primary_candidate = candidate_funcs[0]
        new_logs.append(f"Analyzer: identified candidate function '{primary_candidate}' from error log")

    # 4. Handle previous test output (retry loop)
    if test_output and test_output.strip():
        new_logs.append(f"Analyzer: incorporating previous failed test output for retry attempt #{attempts}")

    # 5. Build function summary catalog for the LLM
    func_catalog = "\n".join(
        [f"- Function '{f['name']}' (lines {f['line_start']}-{f['line_end']})" for f in all_parsed_funcs]
    )

    # 6. Format user prompt with context (efficient for large files)
    prompt_sections = [
        f"File Path: {file_path or 'unknown_file.py'}",
        f"\nParsed Functions Catalog ({len(all_parsed_funcs)} total functions):\n{func_catalog or 'None detected'}",
        "\n--- Error Log / Test Output ---",
        error_log or "No error log provided.",
    ]

    if test_output and test_output.strip():
        prompt_sections.extend([
            f"\n--- Previous Failed Verification (Attempt #{attempts}) ---",
            test_output,
            "Notice: A prior fix attempt failed the verification tests. Re-evaluate the root cause carefully.",
        ])

    # For large files (> 500 lines), if candidates were detected, highlight candidate code snippets
    lines = source_code.splitlines()
    if len(lines) > 500 and candidate_funcs:
        prompt_sections.append("\n--- Primary Candidate Function(s) Extracted by Parser ---")
        for cand in candidate_funcs[:3]:
            cand_info = extract_function(source_code, cand)
            if cand_info:
                prompt_sections.append(
                    f"\n[Candidate: {cand} (Lines {cand_info['line_start']}-{cand_info['line_end']})]:\n"
                    f"{cand_info['code']}"
                )
        prompt_sections.append("\n--- Full Source Code Context ---")
        prompt_sections.append(source_code)
    else:
        prompt_sections.append("\n--- Source Code ---")
        prompt_sections.append(source_code)

    user_prompt = "\n".join(prompt_sections)
    system_prompt = _load_prompt()

    # 7. Call shared LLM interface
    new_logs.append("Analyzer: asking LLM for root-cause analysis")
    try:
        raw_analysis = call_llm_json(system_prompt, user_prompt)
    except Exception as e:
        raise RuntimeError(f"Analyzer LLM call failed: {e}")

    # 8. Validate LLM response schema and values
    required_keys = ("root_cause", "file", "function", "line_start", "line_end")
    for key in required_keys:
        if key not in raw_analysis:
            raise ValueError(f"Analyzer received invalid LLM response: missing key '{key}' in {raw_analysis}")

    root_cause = str(raw_analysis["root_cause"]).strip()
    if not root_cause:
        raise ValueError("Analyzer received invalid LLM response: 'root_cause' cannot be empty.")

    reported_func = str(raw_analysis["function"]).strip()
    if not reported_func:
        raise ValueError("Analyzer received invalid LLM response: 'function' cannot be empty.")

    # Normalize numeric line coordinates
    try:
        line_start = int(raw_analysis["line_start"])
        line_end = int(raw_analysis["line_end"])
    except (ValueError, TypeError) as e:
        raise ValueError(f"Analyzer received invalid non-integer line numbers from LLM: {e}")

    if line_start < 1:
        line_start = 1
    if line_end < line_start:
        raise ValueError(f"Analyzer received invalid line range: line_end ({line_end}) < line_start ({line_start})")

    # 9. Verify function boundaries against Tree-sitter AST
    # LLM identifies the root cause and function, Tree-sitter provides authoritative boundaries
    matched_fn = extract_function(source_code, reported_func)
    if matched_fn:
        # Snap to Tree-sitter verified lines for the detected function
        line_start = matched_fn["line_start"]
        line_end = matched_fn["line_end"]
    elif candidate_funcs and reported_func not in func_names:
        # If LLM invented a function name but candidate was detected, check candidate
        cand_fn = extract_function(source_code, candidate_funcs[0])
        if cand_fn:
            reported_func = cand_fn["name"]
            line_start = cand_fn["line_start"]
            line_end = cand_fn["line_end"]

    # 10. Preserve file path from state if provided
    final_file = file_path if file_path else str(raw_analysis["file"]).strip()

    final_analysis = {
        "root_cause": root_cause,
        "file": final_file,
        "function": reported_func,
        "line_start": line_start,
        "line_end": line_end,
    }

    new_logs.append(f"Analyzer: analysis completed for '{final_analysis['function']}'")

    return {
        "analysis": final_analysis,
        "logs": state.get("logs", []) + new_logs,
    }
