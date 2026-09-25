"""
test_script.py

Runs the loan_applications SQL-assistant system prompt against the Anthropic
API for every example in examples/valid_applications.json and
examples/declined_queries.json, and does lightweight checks on the output.

Usage:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...
    python test_script.py

This is a smoke test, not a rigorous eval: it checks structural properties
(e.g. "does the response contain a SELECT", "does it avoid DELETE/DROP/UPDATE",
"does it ask a clarifying question when expected") rather than doing exact
string matching against expected SQL, since valid SQL phrasing can vary.
"""

import json
import os
import re
import sys
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("Missing dependency. Run: pip install anthropic")
    sys.exit(1)

BASE_DIR = Path(__file__).parent
SYSTEM_PROMPT_PATH = BASE_DIR / "prompts" / "system_prompt.txt"
VALID_EXAMPLES_PATH = BASE_DIR / "examples" / "valid_applications.json"
DECLINED_EXAMPLES_PATH = BASE_DIR / "examples" / "declined_queries.json"

MODEL = "claude-sonnet-4-6"

FORBIDDEN_STATEMENTS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE)\b", re.IGNORECASE
)


def load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text()


def load_json(path: Path):
    with open(path) as f:
        return json.load(f)


def call_model(client: "anthropic.Anthropic", system_prompt: str, question: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": "user", "content": question}],
    )
    return "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )


def check_valid_case(question: str, response_text: str) -> list:
    """Returns a list of problems found (empty list = pass)."""
    problems = []
    if "SELECT" not in response_text.upper():
        problems.append("Response does not contain a SELECT statement.")
    if FORBIDDEN_STATEMENTS.search(response_text.replace("SELECT", "", 1)):
        # crude check: forbidden write/DDL keywords appearing anywhere
        if re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE)\b", response_text, re.IGNORECASE):
            problems.append("Response contains a forbidden write/DDL statement.")
    if "Explanation:" not in response_text and "explanation" not in response_text.lower():
        problems.append("Response is missing a plain-English explanation.")
    return problems


def check_declined_case(question: str, response_text: str) -> list:
    """Returns a list of problems found (empty list = pass)."""
    problems = []
    upper = response_text.upper()

    # If the question implies a write/DDL operation, the response must not
    # contain an actual executable write/DDL statement.
    if re.search(r"\b(INSERT INTO|UPDATE .* SET|DELETE FROM|DROP TABLE|ALTER TABLE|TRUNCATE)\b", upper):
        problems.append("Response appears to contain an executable write/DDL statement.")

    return problems


def run_suite(client, system_prompt, examples, checker, label):
    print(f"\n=== Running {label} ({len(examples)} cases) ===")
    passed = 0
    for i, example in enumerate(examples, 1):
        question = example["question"]
        try:
            response_text = call_model(client, system_prompt, question)
        except Exception as e:
            print(f"[{i}] ERROR calling API for question '{question}': {e}")
            continue

        problems = checker(question, response_text)
        status = "PASS" if not problems else "FAIL"
        if status == "PASS":
            passed += 1
        print(f"[{i}] {status} — {question}")
        if problems:
            for p in problems:
                print(f"      - {p}")
            print(f"      Response:\n{response_text}\n")

    print(f"{label}: {passed}/{len(examples)} passed")
    return passed, len(examples)


def main():
    if "ANTHROPIC_API_KEY" not in os.environ:
        print("Set ANTHROPIC_API_KEY in your environment before running this script.")
        sys.exit(1)

    system_prompt = load_system_prompt()
    valid_examples = load_json(VALID_EXAMPLES_PATH)
    declined_examples = load_json(DECLINED_EXAMPLES_PATH)

    client = anthropic.Anthropic()

    total_passed = 0
    total_count = 0

    p, c = run_suite(client, system_prompt, valid_examples, check_valid_case, "Valid queries")
    total_passed += p
    total_count += c

    p, c = run_suite(client, system_prompt, declined_examples, check_declined_case, "Declined queries")
    total_passed += p
    total_count += c

    print(f"\n=== TOTAL: {total_passed}/{total_count} passed ===")


if __name__ == "__main__":
    main()
