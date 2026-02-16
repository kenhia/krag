# Tasks: WSL to Native Linux Migration

**Input**: Design documents from `/specs/003-wsl-migration/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `- [ ] [ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- All paths are relative to repository root

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Branch creation and foundational dependency updates

- [X] T001 Create feature branch `003-wsl-migration` from `main`
- [X] T002 Update pyproject.toml with Python version constraint `requires-python = ">=3.11,<3.14"`
- [X] T003 [P] Validate all dependencies support Python 3.13+ (run `uv lock` and check for errors)
- [X] T004 [P] Update .github/agents/copilot-instructions.md with Python 3.13+ reference (already done, verify)

---

## Phase 2: Foundational (Configuration Model Extensions)

**Purpose**: Extend Configuration model with new fields for all user stories. MUST complete before any user story implementation.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Add `model_cache_path` field to Configuration model in src/krag/models/configuration.py
- [X] T006 Add `corpus_cache_path` field to Configuration model in src/krag/models/configuration.py
- [X] T007 Add `logs_path` field to Configuration model in src/krag/models/configuration.py
- [X] T008 Add `llm_n_gpu_layers` field to Configuration model in src/krag/models/configuration.py
- [X] T009 Add `expand_user_paths` field validator for path tilde expansion in src/krag/models/configuration.py
- [X] T010 Add `validate_absolute_paths` field validator for absolute path enforcement in src/krag/models/configuration.py
- [X] T011 Update default factory functions for new storage paths using XDG helpers in src/krag/models/configuration.py
- [X] T012 Unit test: Test new storage path fields with defaults in tests/unit/test_configuration.py
- [X] T013 [P] Unit test: Test llm_n_gpu_layers field validation (ge=-1) in tests/unit/test_configuration.py
- [X] T014 [P] Unit test: Test tilde expansion validator in tests/unit/test_configuration.py
- [X] T015 [P] Unit test: Test absolute path validator (reject relative paths) in tests/unit/test_configuration.py

**Checkpoint**: Configuration model extensions complete and validated. User story implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Configurable Storage Paths (Priority: P1) 🎯 MVP

**Goal**: Enable users to configure custom storage paths (vector store, model cache, corpus cache, logs) via config.toml, with XDG defaults when not specified.

**Independent Test**: Set custom paths in config.toml, run `krag config validate`, verify krag reads/writes to configured paths.

### Tests for User Story 1

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T016 [P] [US1] Contract test: ConfigManager resolves custom paths from config.toml in tests/unit/test_config_manager.py
- [X] T017 [P] [US1] Contract test: ConfigManager uses XDG defaults when paths not in config in tests/unit/test_config_manager.py
- [X] T018 [P] [US1] Contract test: ConfigManager validates path writability at startup in tests/unit/test_config_manager.py
- [X] T019 [P] [US1] Contract test: ConfigManager creates missing directories with proper parents in tests/unit/test_config_manager.py
- [X] T020 [P] [US1] Contract test: Config.toml explicit paths take precedence over XDG env vars in tests/unit/test_config_manager.py
- [X] T021 [US1] Integration test: End-to-end with custom /krag paths - index, query, verify files created in tests/integration/test_custom_storage_paths.py

### Implementation for User Story 1

- [X] T022 [US1] Implement runtime path validation in ConfigManager.validate() in src/krag/config/settings.py (writability check, directory creation)
- [X] T023 [US1] Update ConfigManager to track path sources (config file vs default) in src/krag/config/settings.py
- [X] T024 [US1] Update config/defaults.py to use new storage path fields from Configuration model
- [X] T025 [US1] Update logging configuration to use logs_path field in src/krag/config/logging.py
- [X] T026 [US1] Extend `krag config show` command to display storage paths table with sources in src/krag/cli/config.py
- [X] T027 [US1] Add `--paths-only` flag to `krag config show` in src/krag/cli/config.py
- [X] T028 [US1] Extend `krag config validate` command to check storage path accessibility in src/krag/cli/config.py
- [X] T029 [US1] Add clear error messages for path permission/writability failures in src/krag/cli/config.py

**Checkpoint**: User Story 1 complete. Users can configure custom storage paths via config.toml, validated at startup, displayed via CLI commands.

---

## Phase 4: User Story 2 - Group-Based Storage Permissions (Priority: P2)

**Goal**: Document setup for shared group access to /krag storage so both user and future service accounts can access without running as root.

**Independent Test**: Create krag group, add user, verify read/write access to /krag subdirectories as non-root user.

### Implementation for User Story 2

- [X] T030 [US2] Verify quickstart.md contains group setup instructions (already present, confirm accuracy)
- [X] T031 [US2] Add troubleshooting section for group permission issues in specs/003-wsl-migration/quickstart.md
- [X] T032 [US2] Add example of verifying group membership and permissions in specs/003-wsl-migration/quickstart.md

**Checkpoint**: User Story 2 complete. Documentation provides clear instructions for group-based permissions setup.

**Note**: This story is documentation-only. No code changes. Can be completed independently of US1/US3.

---

## Phase 5: User Story 3 - GPU-Accelerated Inference (Priority: P3)

**Goal**: Enable GPU acceleration for LLM inference by configuring n_gpu_layers, with automatic GPU detection and graceful CPU fallback.

**Independent Test**: Set `llm.n_gpu_layers = -1` in config, query with LLM, verify GPU utilization (via nvidia-smi or logs).

### Tests for User Story 3

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T033 [P] [US3] Contract test: LLMClient passes n_gpu_layers to Llama() init in tests/contract/test_llm_contract.py
- [X] T034 [P] [US3] Contract test: LLMClient with n_gpu_layers=0 uses CPU only in tests/contract/test_llm_contract.py
- [X] T035 [P] [US3] Contract test: LLMClient with n_gpu_layers=-1 attempts full GPU offload in tests/contract/test_llm_contract.py
- [X] T036 [US3] Unit test: GPU availability detection (torch.cuda.is_available) in tests/unit/test_gpu.py
- [X] T037 [US3] Integration test: Query with GPU offload enabled, verify at least 2x faster than CPU in tests/integration/test_gpu_acceleration.py

### Implementation for User Story 3

- [X] T038 [P] [US3] Create cli/gpu.py module with GPU detection utilities (torch.cuda.is_available, device info)
- [X] T039 [P] [US3] Implement `krag gpu status` command in src/krag/cli/gpu.py (show CUDA availability, device name, VRAM, compute capability)
- [X] T040 [P] [US3] Implement `krag gpu recommend` command in src/krag/cli/gpu.py (suggest optimal n_gpu_layers based on detected GPU)
- [X] T041 [US3] Modify LLMClient._load_model() to pass n_gpu_layers to Llama() in src/krag/synthesis/llm_client.py
- [X] T042 [US3] Add GPU availability check and warning in LLMClient if n_gpu_layers > 0 but no GPU in src/krag/synthesis/llm_client.py
- [X] T043 [US3] Extend `krag config show` to display GPU status section (CUDA available, device, configured n_gpu_layers) in src/krag/cli/config.py
- [X] T044 [US3] Add `--gpu-only` flag to `krag config show` command in src/krag/cli/config.py
- [X] T045 [US3] Register `krag gpu` command group in src/krag/cli/main.py

**Checkpoint**: User Story 3 complete. Users can configure GPU offloading for LLM inference with automatic detection and fallback.

**Note**: This story is independent of US1 (storage paths). Can be implemented in parallel if team capacity allows.

---

## Phase 6: User Story 4 - Python 3.13+ Compatibility (Priority: P4)

**Goal**: Validate that krag runs on Python 3.13+ and all dependencies are compatible.

**Independent Test**: Create Python 3.13 virtual environment, install krag, run full test suite (551 tests should pass).

### Validation for User Story 4

- [X] T046 [US4] Create Python 3.13 test environment with `uv venv --python 3.13`
- [X] T047 [US4] Install krag dependencies in Python 3.13 environment
- [X] T048 [US4] Run full test suite on Python 3.13 (`uv run pytest`)
- [X] T049 [US4] Document any Python 3.13-specific issues or workarounds in specs/003-wsl-migration/research.md
- [X] T050 [US4] Validate backward compatibility: Run test suite on Python 3.11 (`uv venv --python 3.11 && uv run pytest`)
- [X] T051 [US4] Validate backward compatibility: Run test suite on Python 3.12 (`uv venv --python 3.12 && uv run pytest`)

**Checkpoint**: User Story 4 complete. Python 3.13+ compatibility validated, backward compatibility to 3.11/3.12 maintained.

**Note**: This story is validation-only. Primary code changes (pyproject.toml) already in Setup phase. Independent of US1/US3.

---

## Phase 7: User Story 5 - Re-Index on New Machine (Priority: P5)

**Goal**: Validate that re-indexing works end-to-end on new machine with custom storage paths and GPU acceleration.

**Independent Test**: Configure krag with /krag paths, point at corpus, run `krag index`, verify index created, run `krag query`, verify results.

### Validation for User Story 5

- [X] T052 [US5] Create test config.toml with /krag storage paths and GPU settings
- [X] T053 [US5] Prepare test corpus (use examples/ or tests/fixtures/sample_files/)
- [X] T054 [US5] Run `krag index` with custom config, verify vector store created at configured path
- [X] T055 [US5] Run `krag query` with test question, verify response and GPU utilization
- [X] T056 [US5] Run `krag index` again (incremental), verify only changed files processed
- [X] T057 [US5] Validate step-by-step quickstart.md instructions (full migration workflow)

**Checkpoint**: User Story 5 complete. End-to-end migration workflow validated from fresh install to working queries.

**Note**: This story is operational validation. Depends on US1 (storage paths) and optionally US3 (GPU) being complete. Final validation before feature merge.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final improvements and documentation updates

- [X] T058 [P] Update main README.md with Python 3.13+ requirement
- [X] T059 [P] Create docs/migration-guide.md from specs/003-wsl-migration/quickstart.md
- [X] T060 [P] Add example config.toml with /krag paths to docs/ or examples/
- [X] T061 Run full test suite pre-commit validation (`uv run ruff format && uv run ruff check --fix && uv run pytest`)
- [X] T062 Run quickstart.md end-to-end validation on target Arch Linux machine
- [X] T063 Performance benchmark: Compare GPU vs CPU speeds (embedding and LLM inference)
- [X] T064 Create PR description with summary, test results, performance benchmarks

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - starts immediately
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational (Phase 2) completion
  - US1, US3, US4 can proceed in parallel (independent of each other)
  - US2 can proceed anytime (documentation only, no code dependencies)
  - US5 depends on US1 completion (needs storage paths for validation)
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Depends only on Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: No code dependencies - Can start anytime (documentation only)
- **User Story 3 (P3)**: Depends only on Foundational (Phase 2) - Independent of US1
- **User Story 4 (P4)**: Depends on Setup (Phase 1) - Validation task, independent of other stories
- **User Story 5 (P5)**: Depends on US1 (storage paths) - Operational validation, optionally uses US3 (GPU)

### Within Each User Story

- **US1**: Tests first (T016-T021) → Implementation (T022-T029)
- **US3**: Tests first (T033-T037) → Implementation (T038-T045)
- Models/utilities before services (e.g., T038-T040 before T041-T042)
- Core implementation before CLI integration (e.g., T041-T042 before T043-T045)

### Parallel Opportunities

**Setup Phase (Phase 1)**:
- T003 and T004 can run in parallel (different files)

**Foundational Phase (Phase 2)**:
- T005-T011 are sequential (same file: configuration.py)
- T012-T015 can run in parallel (different test files, after T005-T011 complete)

**User Story 1 - Tests**:
- T016-T020 can run in parallel (if testing different aspects, but all in test_config_manager.py - sequential safer)
- T021 independent (different file: test_custom_storage_paths.py)

**User Story 1 - Implementation**:
- T022-T023 sequential (same file: settings.py)
- T024, T025 can run in parallel with each other (different files: defaults.py, logging.py)
- T026-T029 sequential (same file: cli/config.py)

**User Story 3 - Tests**:
- T033-T035 can run in parallel (if testing different scenarios in test_llm_contract.py)
- T036-T037 can run in parallel (different files)

**User Story 3 - Implementation**:
- T038-T040 sequential or parallel depending on function organization (same file: cli/gpu.py)
- T041-T042 sequential (same file: llm_client.py)
- T043-T044 sequential (same file: cli/config.py)
- T045 depends on T038-T040 (registering gpu command group)
- T038-T040 can run in parallel with T041-T042 (different files)

**User Story 4 & 5**:
- Validation tasks are inherently sequential (must test one environment at a time)

**Polish Phase (Phase 8)**:
- T058-T060 can run in parallel (different files)
- T061-T064 sequential (validation workflow)

---

## Parallel Example: Foundational Phase (Phase 2)

```bash
# After T005-T011 complete (configuration.py model fields):
# Launch all test tasks in parallel:
Task T012: "Test new storage path fields with defaults in tests/unit/test_configuration.py"
Task T013: "Test llm_n_gpu_layers field validation in tests/unit/test_configuration.py"
Task T014: "Test tilde expansion validator in tests/unit/test_configuration.py"
Task T015: "Test absolute path validator in tests/unit/test_configuration.py"
```

## Parallel Example: User Story 1 - Implementation

```bash
# After tests (T016-T021) complete and validation logic (T022-T023) done:
# Launch file-isolated tasks in parallel:
Task T024: "Update config/defaults.py to use new storage path fields"
Task T025: "Update logging configuration to use logs_path field in src/krag/config/logging.py"
# Then T026-T029 sequential (same file: cli/config.py)
```

## Parallel Example: User Story 3 - Implementation

```bash
# After tests (T033-T037) complete:
# Launch independent file work in parallel:
Group A (cli/gpu.py): Task T038-T040 (gpu utilities and commands)
Group B (llm_client.py): Task T041-T042 (n_gpu_layers usage)
# Then T043-T045 sequential (cli integration)
```

## Parallel Example: Multiple User Stories (After Foundational Complete)

```bash
# Once Phase 2 (Foundational) is complete:
Developer A: Work on User Story 1 (T016-T029) - Storage paths
Developer B: Work on User Story 3 (T033-T045) - GPU acceleration
Developer C: Work on User Story 2 (T030-T032) - Documentation
Developer D: Work on User Story 4 (T046-T051) - Python 3.13 validation

# Stories complete independently and integrate without conflicts
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup → Python 3.13 support established
2. Complete Phase 2: Foundational → Configuration model extended with all new fields
3. Complete Phase 3: User Story 1 → Custom storage paths working
4. **STOP and VALIDATE**: Test US1 independently - configure /krag paths, verify indexing/querying works
5. Deploy/demo with configurable storage (core migration requirement met)

### Incremental Delivery (Priority Order)

1. Setup + Foundational → Configuration model ready for all stories
2. **US1 (P1)** → Custom storage paths → Test independently → Deploy/Demo (**MVP!**)
3. **US2 (P2)** → Group permissions docs → Test independently → Deploy/Demo
4. **US3 (P3)** → GPU acceleration → Test independently → Deploy/Demo
5. **US4 (P4)** → Python 3.13 validation → Test independently → Deploy/Demo
6. **US5 (P5)** → Re-indexing validation → Test independently → Deploy/Demo
7. Polish → Final documentation and benchmarks

Each story adds value without breaking previous stories.

### Parallel Team Strategy

With multiple developers:

1. **Team completes Setup + Foundational together** (T001-T015)
2. **Once Foundational is done (T015 complete)**:
   - Developer A: User Story 1 (T016-T029) - Configurable storage paths
   - Developer B: User Story 3 (T033-T045) - GPU acceleration
   - Developer C: User Story 2 (T030-T032) + User Story 4 (T046-T051) - Docs & validation
3. **After US1 completes**:
   - Developer D: User Story 5 (T052-T057) - Re-indexing validation
4. **All developers**: Polish (T058-T064)

Stories complete and integrate independently with minimal conflicts.

---

## Notes

- **[P] marker**: Tasks marked [P] use different files or independent aspects, can run in parallel
- **[Story] label**: Maps task to specific user story for traceability (e.g., [US1], [US3])
- **Tests first**: Write tests, ensure they fail, then implement to make them pass (TDD)
- **Sequential by default**: Assume sequential unless marked [P] to avoid conflicts
- **Independent stories**: Each user story should be independently testable and deployable
- **File paths**: All paths explicit in task descriptions for clarity
- **Commit frequently**: Commit after each task or logical group of related tasks
- **Validate at checkpoints**: Each phase checkpoint provides opportunity to validate independently
- **Constitution compliance**: All changes follow TDD, extend existing patterns, maintain backward compatibility

