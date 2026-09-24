from typing import TypedDict, List

class DebugState(TypedDict, total=False):
    # ---- INPUT (set by UI) ----
    repo_path: str          # folder containing the broken project
    error_log: str          # failing test output
    source_code: str        # code of the buggy file
    file_path: str

    # ---- ANALYZER writes ----
    analysis: dict          # {"root_cause": str, "file": str, "function": str,
                            #  "line_start": int, "line_end": int}

    # ---- TEST-GENERATOR writes ----
    generated_tests: str    # python test code as a string

    # ---- FIXER writes ----
    fixed_code: str         # full corrected file content
    patch_diff: str         # git-style diff of the changes made to the file

    # ---- VERIFY writes ----
    test_passed: bool
    test_output: str

    # ---- LOOP CONTROL ----
    attempts: int
    max_attempts: int
    logs: List[str]         # human-readable steps, shown live in the UI
    pr_url: str
