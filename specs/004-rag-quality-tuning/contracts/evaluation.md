# Contract: Evaluation Module

**Module**: `src/krag/evaluation/` (NEW)  
**Status**: New module

## Module Structure

```
src/krag/evaluation/
├── __init__.py
├── loader.py       # TOML test case loading
├── checks.py       # Check implementations
├── runner.py       # EvalRunner orchestration
└── reporter.py     # JSON report + stderr summary
```

## Interfaces

### loader.py

```python
@dataclass
class EvalCheck:
    """Single expected check for a query."""
    type: str           # "substring" | "source_cited" | "no_hallucination"
    value: str | None   # expected substring or source path; None for no_hallucination

@dataclass
class EvalQuery:
    """A single test case from the TOML file."""
    query: str
    checks: list[EvalCheck]

def load_eval_file(path: Path) -> list[EvalQuery]:
    """Load evaluation queries from a TOML file.

    TOML format:
        [[queries]]
        query = "What is X?"

        [[queries.checks]]
        type = "substring"
        value = "expected text"

        [[queries.checks]]
        type = "source_cited"
        value = "path/to/file.md"

        [[queries.checks]]
        type = "no_hallucination"

    Raises:
        EvalLoadError: On invalid TOML or missing required fields.
    """
    ...
```

### checks.py

```python
@dataclass
class CheckResult:
    """Result of a single check evaluation."""
    check: EvalCheck
    passed: bool
    detail: str   # human-readable explanation

def evaluate_check(
    check: EvalCheck,
    answer: str,
    sources: list[QueryResult],
) -> CheckResult:
    """Evaluate a single check against an answer.

    Check types:
    - "substring": case-insensitive substring match of check.value in answer
    - "source_cited": check.value appears in any source path
    - "no_hallucination": answer contains "I don't know" / "not enough information"
      OR answer does NOT contain those phrases AND sources are non-empty
    """
    ...
```

### runner.py

```python
@dataclass
class EvalQueryResult:
    """Result of running a single eval query."""
    query: str
    answer: str
    sources: list[str]   # source paths
    checks: list[CheckResult]
    passed: bool         # all checks passed

class EvalRunner:
    """Runs evaluation queries through QueryEngine and checks results."""

    def __init__(self, query_engine: QueryEngine) -> None: ...

    def run(self, queries: list[EvalQuery]) -> list[EvalQueryResult]:
        """Execute all eval queries and check results.

        Runs each query through the QueryEngine, then evaluates all
        checks against the answer and sources.
        """
        ...
```

### reporter.py

```python
@dataclass
class EvalReport:
    """Complete evaluation report."""
    total: int
    passed: int
    failed: int
    pass_rate: float
    results: list[EvalQueryResult]

def generate_report(results: list[EvalQueryResult]) -> EvalReport:
    """Generate summary report from eval results."""
    ...

def format_json(report: EvalReport) -> str:
    """Format report as JSON for stdout."""
    ...

def format_summary(report: EvalReport) -> str:
    """Format human-readable summary for stderr."""
    ...
```

## CLI Contract

```python
# In src/krag/cli/main.py or src/krag/cli/eval.py

@app.command()
def eval(
    eval_file: Path = typer.Argument(..., help="Path to TOML evaluation file"),
    config: Path | None = typer.Option(None, help="Path to config file"),
    preset: str | None = typer.Option(None, help="Prompt preset name"),
    top_k: int | None = typer.Option(None, help="Number of results to retrieve"),
) -> None:
    """Run evaluation queries and report results.

    JSON report → stdout, human summary → stderr.
    Exit code 0 if all pass, 1 if any fail.
    """
    ...
```

## Behavioral Contract

- `load_eval_file` validates TOML structure; raises `EvalLoadError` for malformed input.
- `EvalRunner.run()` processes queries sequentially (LLM is not concurrent).
- `no_hallucination` check: passes if answer acknowledges lack of knowledge OR if answer has sources backing it.
- CLI exit code: 0 = all pass, 1 = any failure.
- JSON output to stdout is machine-parseable; stderr summary is human-readable.
- No new dependencies — uses stdlib `json` and existing `tomllib`.
