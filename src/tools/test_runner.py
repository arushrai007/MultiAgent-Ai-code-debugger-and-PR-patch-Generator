import os
import subprocess
import tempfile


def run_tests(state) -> tuple[bool, str]:
    source_code = state.get("source_code", "")
    generated_tests = state.get("generated_tests", "")
    file_path = state.get("file_path", "solution.py")

    with tempfile.TemporaryDirectory() as temp_dir:
        source_file = os.path.join(temp_dir, os.path.basename(file_path))

        with open(source_file, "w", encoding="utf-8") as f:
            f.write(source_code)

        test_file = os.path.join(temp_dir, "test_generated.py")

        with open(test_file, "w", encoding="utf-8") as f:
            f.write(generated_tests)

        try:
            result = subprocess.run(
                ["pytest", "-q"],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=20
            )

            output = result.stdout + result.stderr
            return result.returncode == 0, output

        except subprocess.TimeoutExpired:
            return False, "Test execution timed out after 20 seconds."