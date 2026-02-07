---
name: Python Pre-Commit Validation
description: Execute mandatory pre-commit validation workflow for Python projects using uv, ruff, and pytest
---

# Python Pre-Commit Validation

## Purpose
Execute mandatory pre-commit validation workflow for Python projects using uv, ruff, and pytest.

## When to Use
This skill MUST be invoked before committing ANY changes that include:
- Source code files (`.py`)
- Dependency lock files (`uv.lock`)
- Dependency configuration files (`pyproject.toml`)
- Build configuration files

## Workflow Steps

### 1. Code Formatting
```bash
uv run ruff format .
```
**Expected Result**: All Python files should be formatted according to project style.
- If files are reformatted, continue to next step
- All formatting must complete without errors

### 2. Code Linting
```bash
uv run ruff check --fix .
```
**Expected Result**: All linting checks should pass.
- Auto-fix issues where possible
- All checks must pass with zero errors
- If issues cannot be auto-fixed, stop and address manually

### 3. Test Suite
```bash
uv run pytest
```
**Expected Result**: All tests must pass.
- Zero test failures allowed
- Pay attention to any warnings or deprecations
- If tests fail, fix issues and rerun ALL three steps from the beginning

## Success Criteria
ALL three steps must complete successfully with:
- ✅ Zero formatting errors
- ✅ Zero linting errors  
- ✅ Zero test failures

## Failure Handling
If ANY step fails:
1. **Stop immediately** - do not proceed to commit
2. Fix the reported errors
3. **Rerun ALL three steps** from the beginning (fixing one issue can introduce new ones)
4. Only proceed to commit after all three steps pass

## Enforcement
- This workflow is **NON-NEGOTIABLE** per project constitution
- Exemptions: Only documentation-only commits (README, markdown with no code blocks)
- All commits affecting source code MUST complete this workflow

## Post-Validation
After all checks pass, stage and commit changes:
```bash
git add -A
git commit -m "type: brief description

- Detail 1
- Detail 2"
```

Use conventional commit types: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`

## Quick Reference
```bash
# Full pre-commit workflow (copy-paste friendly)
uv run ruff format . && \
uv run ruff check --fix . && \
uv run pytest && \
echo "✅ Pre-commit checks passed - ready to commit"
```
