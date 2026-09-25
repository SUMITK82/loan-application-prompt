# Loan Application SQL Prompt

A prompt-engineering project that turns Claude into a scoped, read-only SQL
assistant for a `loan_applications` table. It converts plain-English
questions into safe `SELECT` queries, refuses destructive or out-of-scope
requests, and asks for clarification when a question is ambiguous.

## Why this exists

Natural-language-to-SQL assistants are useful, but risky if given unchecked
access: a careless or adversarial prompt like "delete all defaulted
applicants" could destroy data if the assistant complies. This project
constrains the assistant to:

- **Read-only** access (`SELECT` only — no `INSERT`/`UPDATE`/`DELETE`/`DROP`)
- **Schema-faithful** answers (no inventing columns that don't exist)
- **Clarification-seeking** behavior on ambiguous business terms (e.g. "risky")
- **Transparent** output (every query ships with a one-sentence explanation)

## Directory structure

```
loan-application-prompt/
├── README.md                  # This file
├── prompts/
│   ├── system_prompt.txt      # The system prompt given to Claude
│   └── safety_guard.md   # Detailed rules for declining dangerous/invalid tasks
├── examples/
│   ├── valid_applications.json  # Sample Q&A pairs that should pass evaluation
│   └── declined_queries.json    # Sample dangerous/out-of-scope prompts and expected refusals
└── test_script.py             # Optional script to smoke-test the prompt via the Anthropic API
```

## The schema

```sql
loan_applications (
    applicant_id       INT,
    age                INT,
    annual_income      FLOAT,
    loan_amount        FLOAT,
    loan_purpose       TEXT,   -- 'home', 'education', 'business', 'personal'
    credit_score       INT,
    employment_status  TEXT,   -- 'employed', 'self-employed', 'unemployed'
    default_status     TEXT,   -- 'defaulted' or 'paid'
    application_date   DATE
)
```

## How it works

1. **System prompt** (`prompts/system_prompt.txt`) is passed as the `system`
   parameter in an Anthropic API call (or pasted as instructions in claude.ai).
2. The user asks a plain-English question about the `loan_applications` table.
3. Claude responds in a fixed format:
   ```
   SQL: <query>
   Explanation: <one sentence>
   ```
4. If the question is ambiguous (e.g. "show me risky applicants"), Claude asks
   one clarifying question instead of guessing at thresholds or definitions.
5. If the question requires a write/DDL operation or references a
   non-existent column, Claude declines and explains why — see
   `prompts/safety_guardrails.md` for the full rule set.

## Example interaction

**User:** How many applicants defaulted on their loans?

**Claude:**
```
SQL: SELECT COUNT(*) AS defaulted_count FROM loan_applications WHERE default_status = 'defaulted';
Explanation: This query counts the number of applicants whose default_status is marked as 'defaulted'.
```

**User:** Delete all applicants who defaulted

**Claude:**
> I can't run that — I'm only able to generate SELECT statements, not DELETE.
> If you want, I can instead write a SELECT query to show you all the
> applicants who defaulted, so you can review them first: ...

## Running the tests

`test_script.py` is an optional smoke test that runs every example in
`examples/valid_applications.json` and `examples/declined_queries.json`
against the live Anthropic API and does lightweight structural checks
(e.g. "does the response contain a SELECT", "does it avoid forbidden
write/DDL keywords", "does it include an explanation").

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
python test_script.py
```

This is a smoke test, not a rigorous eval harness — it checks structural
properties of the response rather than doing exact string matching against
expected SQL, since correct SQL can be phrased in more than one way.

## Extending this project

Ideas for taking this further:

- Add more example categories to `declined_queries.json` (e.g. queries
  attempting prompt injection, queries asking for other tables that don't
  exist, queries with malformed dates).
- Add a `dialect` parameter so the same prompt can target MySQL or SQLite
  instead of PostgreSQL.
- Add row-level or column-level redaction rules if the schema is extended to
  include PII (e.g. name, SSN, address).
- Wire `test_script.py` into CI so prompt regressions are caught automatically
  when the system prompt is edited.

## Limitations

- The assistant generates SQL text only; it does not execute queries or have
  access to real data, so it cannot verify that a query returns sensible
  results.
- Ambiguity detection relies on the model's judgment — it is not a hardcoded
  keyword list, so edge cases may occasionally require prompt refinement.
