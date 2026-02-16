# Tasks: RAG Quality Tuning & Hallucination Reduction

**Input**: Design documents from `/specs/004-rag-quality-tuning/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — TDD is NON-NEGOTIABLE per project constitution.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1–US5) from spec.md
- Exact file paths included in all descriptions

---

## Phase 1: Setup

**Purpose**: Create new module skeleton and test fixtures

- [x] T001 [P] Create evaluation module skeleton in src/krag/evaluation/__init__.py
- [x] T002 [P] Create sample evaluation TOML fixture in tests/fixtures/eval_queries.toml

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared configuration infrastructure needed by ALL user stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 [P] Add new default constants (DEFAULT_SIMILARITY_THRESHOLD=0.3, DEFAULT_LLM_TOP_P=0.9, DEFAULT_LLM_REPEAT_PENALTY=1.1, DEFAULT_LLM_MIN_P=0.05, DEFAULT_PROMPT_PRESET="balanced") and update DEFAULT_LLM_TEMPERATURE from 0.7 to 0.2 in src/krag/config/defaults.py
- [x] T004 [P] Add new config fields (similarity_threshold, llm_top_p, llm_repeat_penalty, llm_min_p, prompt_preset, prompt_system_override) with validators per data-model.md to src/krag/models/configuration.py
- [x] T005 Update settings parser to handle new [prompt] section and expanded [retrieval]/[llm] fields in src/krag/config/settings.py

**Checkpoint**: Configuration infrastructure ready — user story implementation can begin

---

## Phase 3: User Story 1 — Grounded, Accurate Answers (Priority: P1) 🎯 MVP

**Goal**: Answers are grounded in retrieved context, never fabricated; system acknowledges insufficient context when appropriate.

**Independent Test**: Index known documents, ask factual questions, verify answers cite correct sources. Ask out-of-scope questions, verify "insufficient context" response.

### Tests for User Story 1

> **Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T006 [P] [US1] Write unit tests for PromptPreset dataclass (built-in presets, validation, available_presets()) and PromptBuilder.build() returning chat messages with numbered citations in tests/unit/test_prompt_builder.py
- [ ] T007 [P] [US1] Write unit tests for LLMClient.generate() accepting chat messages list, per-call param overrides, and error handling in tests/unit/test_llm_client.py

### Implementation for User Story 1

- [ ] T008 [P] [US1] Implement PromptPreset dataclass with strict/balanced/verbose built-in presets (system prompts, generation params per research.md) in src/krag/synthesis/prompt_builder.py
- [ ] T009 [US1] Refactor PromptBuilder.build() to return list[dict[str, str]] chat messages with numbered [1], [2] source citations and "insufficient context" system message for empty results in src/krag/synthesis/prompt_builder.py
- [ ] T010 [P] [US1] Migrate LLMClient.generate() from model() text completion to model.create_chat_completion(), change signature from (query, context) to (messages), add top_p/repeat_penalty/min_p params in src/krag/synthesis/llm_client.py
- [ ] T011 [US1] Add prompt field to QueryResponse dataclass, update QueryEngine to pass preset_name and system_prompt_override to PromptBuilder, skip LLM call on empty retrieval results in src/krag/orchestration/query_engine.py

**Checkpoint**: Queries return grounded answers with source citations; out-of-scope queries return "insufficient context"

---

## Phase 4: User Story 2 — Relevant Context Retrieval (Priority: P1)

**Goal**: Low-relevance chunks are filtered out before reaching the LLM, improving context quality.

**Independent Test**: Query against known documents, verify only chunks meeting similarity threshold appear in results; verify INFO log shows "Retrieved N, kept M after threshold T".

### Tests for User Story 2

> **Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T012 [US2] Write contract tests for Retriever.retrieve() similarity_threshold parameter — verify filtering, empty results when all below threshold, score ordering in tests/contract/test_retriever_contract.py

### Implementation for User Story 2

- [ ] T013 [US2] Add similarity_threshold parameter to Retriever.retrieve() with post-retrieval filtering (fetch top_k from Qdrant, filter by threshold in Python) and INFO-level summary logging in src/krag/retrieval/retriever.py
- [ ] T014 [US2] Wire similarity_threshold from QueryEngine constructor to Retriever.retrieve() calls in src/krag/orchestration/query_engine.py

**Checkpoint**: Low-scoring chunks filtered; retriever logs show filtering summary

---

## Phase 5: User Story 3 — Tunable Configuration (Priority: P2)

**Goal**: Users can adjust retrieval, prompt, and LLM settings via config file or CLI without code changes.

**Independent Test**: Set different presets and thresholds in krag.toml, verify queries reflect changed settings. Use --preset CLI flag to override in-flight.

### Implementation for User Story 3

- [ ] T015 [US3] Add --preset CLI option (typer.Option with choices from PromptBuilder.available_presets()) to query command in src/krag/cli/query.py
- [ ] T016 [US3] Wire all new config fields (similarity_threshold, prompt_preset, prompt_system_override, llm_top_p, llm_repeat_penalty, llm_min_p) through QueryEngine construction in src/krag/cli/query.py

**Checkpoint**: Config file and CLI flags control prompt preset, similarity threshold, and LLM parameters

---

## Phase 6: User Story 4 — Quality Evaluation Workflow (Priority: P2)

**Goal**: Users can run a suite of test queries from a TOML file and see pass/fail results with JSON output.

**Independent Test**: Create eval TOML with known-answer queries, run `krag eval`, verify JSON report on stdout and summary on stderr, exit code reflects pass/fail.

### Tests for User Story 4

> **Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T017 [P] [US4] Write unit tests for load_eval_file() — valid TOML parsing, missing fields error, all check types in tests/unit/test_eval_loader.py
- [ ] T018 [P] [US4] Write unit tests for evaluate_check() — substring match, source_cited match, no_hallucination logic (with/without sources) in tests/unit/test_eval_checks.py
- [ ] T019 [P] [US4] Write unit tests for EvalRunner.run() — sequential execution, per-query check aggregation, passed flag in tests/unit/test_eval_runner.py
- [ ] T020 [P] [US4] Write unit tests for generate_report(), format_json(), format_summary() in tests/unit/test_eval_report.py

### Implementation for User Story 4

- [ ] T021 [US4] Implement EvalQuery/EvalCheck dataclasses and load_eval_file() TOML loader with validation in src/krag/evaluation/loader.py
- [ ] T022 [P] [US4] Implement CheckResult dataclass and evaluate_check() for substring, source_cited, no_hallucination check types in src/krag/evaluation/checks.py
- [ ] T023 [US4] Implement EvalRunner class wrapping QueryEngine — sequential query execution, check evaluation, result aggregation in src/krag/evaluation/runner.py
- [ ] T024 [P] [US4] Implement EvalReport dataclass, generate_report(), format_json() for stdout, format_summary() for stderr in src/krag/evaluation/reporter.py
- [ ] T025 [US4] Implement eval CLI command (typer) with JSON stdout, summary stderr, exit code 0/1 in src/krag/cli/eval.py
- [ ] T026 [US4] Register eval command in CLI app entry point in src/krag/cli/main.py

**Checkpoint**: `krag eval eval-tests.toml` produces JSON report on stdout, human summary on stderr, correct exit code

---

## Phase 7: User Story 5 — Diagnostic Logging (Priority: P3)

**Goal**: Debug logging reveals the full pipeline state for any query — retrieval scores, full prompt, generation params — enabling root-cause diagnosis.

**Independent Test**: Run a query with DEBUG logging, verify log contains retrieved chunks with scores, complete prompt/messages, and generation summary.

### Tests for User Story 5

- [ ] T027 [US5] Write integration test verifying DEBUG log output contains chunk scores, threshold filtering, complete prompt, and generation summary for a full query pipeline run in tests/integration/test_query_pipeline.py

### Implementation for User Story 5

- [ ] T028 [P] [US5] Add DEBUG-level logging for each retrieved chunk (score, source file, threshold pass/fail) in src/krag/retrieval/retriever.py
- [ ] T029 [P] [US5] Add DEBUG-level logging for complete chat messages before generation in src/krag/synthesis/llm_client.py
- [ ] T030 [P] [US5] Add DEBUG-level logging for pipeline stages (retrieval count, prompt size, generation duration) in src/krag/orchestration/query_engine.py

**Checkpoint**: `krag query --log-level DEBUG` reveals full pipeline state for diagnosis

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, and final quality gates

- [ ] T031 [P] Update docs with quality tuning guidance (preset reference, threshold tuning, eval workflow) in docs/troubleshooting.md
- [ ] T032 [P] Write end-to-end evaluation pipeline integration test in tests/integration/test_evaluation_pipeline.py
- [ ] T033 Run quickstart.md scenario validation against implementation
- [ ] T034 Run pre-commit validation (uv run ruff format . && uv run ruff check --fix . && uv run pytest)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Foundational — delivers MVP
- **US2 (Phase 4)**: Depends on Foundational — can run in parallel with US1
- **US3 (Phase 5)**: Depends on US1 + US2 (needs preset and threshold implementations to wire)
- **US4 (Phase 6)**: Depends on Foundational — can start after US1 (needs QueryEngine with preset support)
- **US5 (Phase 7)**: Depends on US1 + US2 (enhances logging in those components)
- **Polish (Phase 8)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: After Foundational → no dependencies on other stories
- **US2 (P1)**: After Foundational → no dependencies on other stories
- **US3 (P2)**: After US1 + US2 → wires their features to config/CLI
- **US4 (P2)**: After US1 → uses QueryEngine for eval runs
- **US5 (P3)**: After US1 + US2 → adds logging to their implementations

### Within Each User Story

1. Tests MUST be written and FAIL before implementation (TDD)
2. Models/dataclasses before services
3. Services before CLI integration
4. Core implementation before cross-component wiring

### Parallel Opportunities

```
Phase 1:  T001 ║ T002
Phase 2:  T003 ║ T004  →  T005
Phase 3:  T006 ║ T007  →  T008 ║ T010  →  T009  →  T011
Phase 4:  T012  →  T013  →  T014
Phase 5:  T015  →  T016
Phase 6:  T017 ║ T018 ║ T019 ║ T020  →  T021 ║ T022  →  T023 ║ T024  →  T025  →  T026
Phase 7:  T027  →  T028 ║ T029 ║ T030
Phase 8:  T031 ║ T032  →  T033  →  T034
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: US1 — Grounded, Accurate Answers
4. **STOP and VALIDATE**: Test US1 independently — queries return grounded answers
5. This alone delivers the core quality improvement

### Incremental Delivery

1. Setup + Foundational → Config infrastructure ready
2. US1 → Grounded answers with source citations (MVP!)
3. US2 → Relevant retrieval with threshold filtering
4. US3 → Full config/CLI control over quality levers
5. US4 → Evaluation harness for measuring quality
6. US5 → Diagnostic logging for debugging
7. Polish → Docs, integration tests, validation

### Suggested MVP Scope

**US1 only** — delivers the highest-impact quality improvement (grounded answers, "I don't know" responses, source citations) with the smallest implementation surface. Can be validated independently before proceeding.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to user story for traceability
- Constitution: TDD is non-negotiable — write tests, watch them fail, implement, pass
- Commit after each task or logical group
- Pre-commit: `uv run ruff format . && uv run ruff check --fix . && uv run pytest`
- All new code: type hints, docstrings, ruff-compliant
