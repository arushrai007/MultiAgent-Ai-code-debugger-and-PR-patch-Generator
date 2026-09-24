# 🤖 Multi-Agent AI Code Debugger & PR Patch Generator

An autonomous multi-agent pipeline that debugs software defects, generates reproducing test cases, produces surgical code fixes, verifies them against test suites, and opens pull requests automatically.

---

## 🔄 System Architecture

```text
  Analyzer (Member 1) ──> Test-Generator (Member 2) ──> Fixer (Member 3) ──> Verify (Pytest)
         ▲                                                                        │
         │                                                                        │
         └───────────── [Fail: retry with test_output] ───────────────────────────┤
                                                                                  │
                                                                        [Pass: Open PR] ──> GitHub PR
```

Every agent interacts via a single frozen contract: **`DebugState`** in [`src/state.py`](src/state.py).

---

## 👥 Team Split & Responsibilities

| Role | Member | Responsibilities | Files Owned | Status |
|---|---|---|---|:---:|
| **Analyzer Agent** | **Member 1 (Current)** | AST parsing, root-cause diagnosis, coordinate extraction, retry analysis | `src/agents/analyzer.py`<br>`src/tools/code_parser.py`<br>`src/prompts/analyzer.md`<br>`test_analyzer_standalone.py` | **✅ COMPLETED** |
| **Test-Generator** | Member 2 | Generate 3-5 reproducing pytest cases covering edge cases | `src/agents/test_generator.py`<br>`src/tools/test_runner.py`<br>`src/prompts/test_generator.md` | ⏳ In Progress |
| **Fixer + PR** | Member 3 | Unified diff generation, patch application, GitHub PR creation | `src/agents/fixer.py`<br>`src/tools/git_pr.py`<br>`src/prompts/fixer.md` | ⏳ In Progress |
| **UI & Graph** | Member 4 | Gradio web UI and LangGraph loop orchestrator | `app.py`<br>`src/graph.py` | ⏳ In Progress |
| **Lead / Architecture** | Lead | Skeleton, frozen state dictionary, shared LLM helpers | `src/state.py`<br>`src/llm.py`<br>`src/config.py`<br>`main.py` | ✅ Ready |

---

## 🔍 Member 1: Analyzer Agent (Completed Deliverables)

Member 1 is responsible for diagnosing the bug, identifying the target file and function, and pinpointing the exact line coordinates.

### Key Components Implemented:

1. **Tree-sitter Code Parser ([`src/tools/code_parser.py`](src/tools/code_parser.py))**:
   - Uses `tree-sitter` and `tree-sitter-python` to parse Python code into an AST.
   - Includes automatic fallback to Python's native `ast` module for environment portability.
   - `list_functions(source_code)`: Discovers all function names in the target file.
   - `extract_function(source_code, function_name)`: Extracts the exact code body and 1-indexed `line_start` and `line_end` bounds (including decorated functions and async definitions).

2. **System Prompt Engineering ([`src/prompts/analyzer.md`](src/prompts/analyzer.md))**:
   - Directs the LLM to inspect stack traces, exception messages, code logic, and previous test failure outputs.
   - Enforces strict JSON output conforming to the system contract:
     ```json
     {
       "root_cause": "Detailed explanation of the defect",
       "file": "path/to/file.py",
       "function": "target_function_name",
       "line_start": 6,
       "line_end": 8
     }
     ```

3. **Analyzer Agent Execution ([`src/agents/analyzer.py`](src/agents/analyzer.py))**:
   - Implements `run(state: DebugState) -> dict`.
   - Reads `source_code`, `error_log`, `file_path`, and optional `test_output` (for retries).
   - Combines AST function discovery with LLM reasoning.
   - Snaps coordinates to Tree-sitter verified line numbers.
   - Updates `state["analysis"]` and appends human-readable progress updates to `state["logs"]`.

4. **Standalone Verification Suite ([`test_analyzer_standalone.py`](test_analyzer_standalone.py))**:
   - Validates parser accuracy, AST boundary detection, single-pass diagnosis, and multi-turn retry behavior using a hardcoded state dictionary.

---

## 🚀 Quickstart & Testing Member 1

### 1. Set Up Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure API Key (Optional for offline mock mode)
Create a `.env` file in the project root:
```bash
ANTHROPIC_API_KEY=your_anthropic_key_here
# or OPENAI_API_KEY=your_openai_key_here
# or GEMINI_API_KEY=your_gemini_key_here
```
*(If no API key is set, the built-in offline mock mode runs automatically without error).*

### 3. Run Standalone Analyzer Test
```bash
python test_analyzer_standalone.py
```

### 4. Direct Python Usage Example
```python
from src.state import DebugState
from src.agents import analyzer

state: DebugState = {
    "file_path": "calculator.py",
    "source_code": """def sum_list(numbers):
    total = 0
    for i in range(len(numbers) - 1): # bug: skips last element
        total += numbers[i]
    return total
""",
    "error_log": "AssertionError: assert sum_list([1, 2, 3, 4]) == 10 failed (got 6)",
    "attempts": 0,
    "max_attempts": 3,
    "logs": ["Starting debugging process"],
}

# Run analyzer
result = analyzer.run(state)

print("Analysis:", result["analysis"])
print("Logs:", result["logs"])
```
