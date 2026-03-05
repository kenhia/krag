# Tasks: Krager Enhancements

**Input**: Design documents from `/specs/014-krager-enhancements/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Included — TDD required per constitution Principle II. Tests written before implementation within each phase.

**Organization**: Tasks grouped by user story for independent implementation and testing.

**Deferred**: User Story 8 (Index Path Selection) — blocked on kragd API gap (research.md R6). Will be implemented when kragd exposes `source_directories` in `ServiceStatus`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story (US1–US9, excluding deferred US8)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install Tauri Store plugin and configure Rust/capability prerequisites

- [x] T001 Install @tauri-apps/plugin-store dependency in apps/krager/package.json
- [x] T002 [P] Add tauri-plugin-store = "2" to apps/krager/src-tauri/Cargo.toml
- [x] T003 [P] Register store plugin in apps/krager/src-tauri/src/lib.rs
- [x] T004 [P] Create store capability file at apps/krager/src-tauri/capabilities/store.json

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core types, config persistence service, and reusable UI primitives that all user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Types & Config Service

- [x] T005 Add UserConfig, ConnectionConfig, QueryConfig, CriticConfig, DisplayConfig, PresetOption, PresetName, SourceReference types, VALID_PRESETS array, PRESET_OPTIONS array, USER_CONFIG_DEFAULTS constant, and validation constants to apps/krager/src/lib/types.ts
- [x] T006 Write tests for ConfigStoreService (load, save, get, set, getAll, fallback on missing file, fallback on corruption, debounced auto-save, destroy) in apps/krager/src/lib/services/config-store.test.ts
- [x] T007 Implement ConfigStoreService wrapping Tauri Store plugin (load with autoSave:300 and defaults, try/catch with createNew fallback, dot-path get/set, onChange listener) in apps/krager/src/lib/services/config-store.ts

### UI Primitives

- [x] T008 [P] Write tests for Select dropdown (open/close, option selection, keyboard navigation, disabled state) in apps/krager/src/lib/components/ui/Select.test.ts
- [x] T009 [P] Write tests for Toggle switch (on/off state, click toggle, disabled state) in apps/krager/src/lib/components/ui/Toggle.test.ts
- [x] T010 [P] Write tests for Slider range input (value display, min/max clamping, step increments) in apps/krager/src/lib/components/ui/Slider.test.ts
- [x] T011 [P] Create Select.svelte generic dropdown component in apps/krager/src/lib/components/ui/Select.svelte
- [x] T012 [P] Create Toggle.svelte boolean switch component in apps/krager/src/lib/components/ui/Toggle.svelte
- [x] T013 [P] Create Slider.svelte range input component with value label in apps/krager/src/lib/components/ui/Slider.svelte

**Checkpoint**: Foundation ready — types defined, config store operational, UI primitives available

---

## Phase 3: User Story 1+2 — Persistent Connection + Local Config (Priority: P1) 🎯 MVP

**Goal**: App remembers last successful connection and loads all preferences from a local JSON config file on startup. Config is created automatically on first connect and updated as preferences change.

**Independent Test**: Connect to kragd, close app, relaunch — host/port fields pre-filled with previous values. Inspect `~/.local/share/com.krag.krager/settings.json` on disk.

### Tests

- [x] T014 [P] [US1] Extend tests for connection config persistence (load saved host/port on init, save host/port on successful connect, fallback to defaults when no config) in apps/krager/src/lib/state/connection.svelte.test.ts
- [x] T015 [P] [US1] Create test file for ConnectionBar pre-fill from config (initial values from state, no re-typing needed) in apps/krager/src/lib/components/domain/ConnectionBar.test.ts

### Implementation

- [x] T016 [US1] Wire configStore.init() into app startup lifecycle and configStore.destroy() into cleanup in apps/krager/src/routes/+page.svelte
- [x] T017 [US1] Modify connection.svelte.ts to load initial host/port from config store on init and save on successful connect via configStore.set() in apps/krager/src/lib/state/connection.svelte.ts
- [x] T018 [US1] Modify ConnectionBar.svelte to read pre-filled host/port values from connection state (removing hardcoded defaults from component) in apps/krager/src/lib/components/domain/ConnectionBar.svelte

**Checkpoint**: US1+US2 complete — connection persists across restarts, config file created/loaded automatically

---

## Phase 4: User Story 3 — Query Controls (Priority: P2)

**Goal**: Query panel exposes top-k, preset, debug, and sources controls matching CLI capabilities. Parameters included in all query/retrieve requests.

**Independent Test**: Set top-k=3, select "strict" preset, toggle sources off, submit query — verify request payload includes correct parameters and response respects them.

### Tests

- [x] T019 [P] [US3] Write tests for query state module (init from config, mutation, preset validation, top-k range validation, show_sources toggle, include_debug toggle, persistence via configStore.set) in apps/krager/src/lib/state/query.svelte.test.ts
- [x] T020 [P] [US3] Write tests for QueryPanel query controls (top-k input renders, preset dropdown populates with PRESET_OPTIONS, debug toggle renders, sources toggle renders, parameter binding to state) in apps/krager/src/lib/components/domain/QueryPanel.test.ts

### Implementation

- [x] T021 [US3] Create query.svelte.ts state module with $state for top_k, preset, include_debug, show_sources, retrieve_only; init from config; mutation functions that persist via configStore.set() in apps/krager/src/lib/state/query.svelte.ts
- [x] T022 [US3] Add top-k numeric input, preset Select dropdown, debug Toggle, sources Toggle controls to QueryPanel.svelte bound to query state in apps/krager/src/lib/components/domain/QueryPanel.svelte
- [x] T023 [US3] Wire query state parameters (top_k, preset, include_debug) into query/retrieve request payload construction in apps/krager/src/lib/components/domain/QueryPanel.svelte

**Checkpoint**: US3 complete — all query controls functional, persisted, and included in API requests

---

## Phase 5: User Story 4 — Critic Controls (Priority: P2)

**Goal**: Critic toggle + cut-off score flag low-quality answers using DebugMetadata.critic_scores. Enabling critic auto-sets include_debug: true.

**Independent Test**: Enable critic, set cut-off 0.7, submit query — verify debug mode auto-enabled and answers with critic scores below 0.7 are visually flagged.

### Tests

- [x] T024 [P] [US4] Extend tests for critic state in query.svelte.ts (critic enabled/disabled, cut_off validation 0.0–1.0, auto-enable include_debug when critic enabled, persistence) in apps/krager/src/lib/state/query.svelte.test.ts
- [x] T025 [P] [US4] Write tests for critic score flagging display (warning indicator when score < cut_off, no indicator when above, no indicator when critic disabled) in apps/krager/src/lib/components/domain/QueryAnswer.test.ts

### Implementation

- [x] T026 [US4] Add critic state (enabled, cut_off) to query.svelte.ts with auto-include_debug logic (when critic.enabled=true, force include_debug=true) and persistence in apps/krager/src/lib/state/query.svelte.ts
- [x] T027 [US4] Add critic Toggle and cut-off Slider (0.0–1.0, step 0.05) controls to QueryPanel.svelte bound to critic state in apps/krager/src/lib/components/domain/QueryPanel.svelte
- [x] T028 [US4] Add low-confidence warning indicator to QueryAnswer display when DebugMetadata.critic_scores exist and any score < cut_off in apps/krager/src/lib/components/domain/QueryAnswer.svelte

**Checkpoint**: US4 complete — critic controls functional, answers flagged when below threshold

---

## Phase 6: User Story 5 — Settings Page (Priority: P2)

**Goal**: Centralized settings page with Connection, Query, Critic, Display sections accessible from sidebar. All changes applied immediately without save button.

**Independent Test**: Navigate to Settings, change default top-k and window opacity, navigate away and back — values persist. Close and relaunch — values restored.

### Tests

- [x] T029 [P] [US5] Write tests for settings state module (opacity init/clamping, theme init, persistence, reset to defaults) in apps/krager/src/lib/state/settings.svelte.test.ts
- [x] T030 [P] [US5] Write tests for SettingsPanel (renders 4 sections, Connection fields bind to connection state, Query fields bind to query state, Critic fields bind to critic state, Display fields bind to settings state, changes propagate immediately) in apps/krager/src/lib/components/domain/SettingsPanel.test.ts

### Implementation

- [x] T031 [US5] Create settings.svelte.ts state module for display preferences (opacity with 0.3–1.0 clamping, theme) with init from config and persistence via configStore.set() in apps/krager/src/lib/state/settings.svelte.ts
- [x] T032 [US5] Create SettingsPanel.svelte with Connection (host, port), Query (top-k, preset, debug, sources), Critic (enabled, cut-off), and Display (opacity, theme) sections using Select/Toggle/Slider/Input primitives in apps/krager/src/lib/components/domain/SettingsPanel.svelte
- [x] T033 [US5] Add Settings entry (⚙) to sidebar navigation between System and Debug in apps/krager/src/routes/+page.svelte

**Checkpoint**: US5 complete — all settings accessible, changes immediate and persisted

---

## Phase 7: User Story 6 — Transcript Redesign (Priority: P3)

**Goal**: Query page shows latest answer + compact source references (file path, score) without chunk text. Dedicated Transcript panel shows full history with expandable chunk content per source.

**Independent Test**: Submit query — query page shows answer + source list without chunks. Navigate to Transcript — see full history with expandable chunk details.

### Tests

- [x] T034 [P] [US6] Write tests for QueryAnswer component (renders answer text, renders SourceReference list with file_path and score, does NOT render chunk_content, handles empty sources) in apps/krager/src/lib/components/domain/QueryAnswer.test.ts
- [x] T035 [P] [US6] Extend tests for chunksExpanded toggle (default false, toggle to true shows chunk content, toggle back hides it) in apps/krager/src/lib/state/transcript.svelte.test.ts

### Implementation

- [x] T036 [US6] Add chunksExpanded boolean state per transcript entry and toggle function to transcript.svelte.ts in apps/krager/src/lib/state/transcript.svelte.ts
- [x] T037 [US6] Create QueryAnswer.svelte displaying latest transcript entry answer text + compact SourceReference list (file_path, score, collection, rank) without chunk_content; conditionally hide SourceReference list when query.show_sources is false in apps/krager/src/lib/components/domain/QueryAnswer.svelte
- [x] T038 [US6] Modify TranscriptView.svelte to add expand/collapse toggle per source entry that reveals full chunk_content text when expanded in apps/krager/src/lib/components/domain/TranscriptView.svelte
- [x] T039 [US6] Add Transcript sidebar entry (📝) between Query and Index, wire QueryAnswer.svelte into query page replacing TranscriptView, wire TranscriptView into Transcript page in apps/krager/src/routes/+page.svelte

**Checkpoint**: US6 complete — clean query answer view, full transcript with expandable chunks on separate panel

---

## Phase 8: User Story 7 — Window Opacity (Priority: P3)

**Goal**: Adjustable window transparency (30%–100%) via CSS opacity on root element with real-time preview and persistence.

**Independent Test**: Open Settings, adjust opacity to 80% then 50% — window becomes progressively transparent. Restart — opacity restored.

### Tests

- [x] T040 [US7] Extend tests for opacity state (init from config, clamping to 0.3–1.0, values below 0.3 clamped up, values above 1.0 clamped down, persistence) in apps/krager/src/lib/state/settings.svelte.test.ts

### Implementation

- [x] T041 [US7] ~~Add opacity state with 0.3–1.0 clamping to settings.svelte.ts~~ Completed by T031 (opacity state included in settings.svelte.ts creation)
- [x] T042 [US7] Implement $effect that applies CSS opacity to document.documentElement based on settings.opacity state in apps/krager/src/routes/+page.svelte
- [x] T043 [US7] Add opacity Slider (min 0.3, max 1.0, step 0.05) to Display section in SettingsPanel.svelte in apps/krager/src/lib/components/domain/SettingsPanel.svelte

**Checkpoint**: US7 complete — window opacity adjustable from settings with real-time preview and persistence

---

## Phase 9: User Story 9 — Embedding Model Display (Priority: P3)

**Goal**: System status page shows all configured embedding models by iterating the embedding_models array instead of showing only the first entry.

**Independent Test**: Connect to kragd — verify system status page lists all embedding models (currently one, but code handles multiple).

### Tests

- [x] T044 [US9] Write test for multiple embedding model display (single model, multiple models, empty list) in apps/krager/src/lib/components/domain/SystemStatus.test.ts

### Implementation

- [x] T045 [US9] Modify SystemStatus.svelte to iterate embedding_models array and display each model instead of only showing embedding_models[0] in apps/krager/src/lib/components/domain/SystemStatus.svelte

**Checkpoint**: US9 complete — all embedding models visible on system status page

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Validation, integration verification, and final cleanup

- [x] T046 [P] Verify config store lifecycle handles edge cases (read-only filesystem logs warning, rapid setting toggles debounced, external file modification synced) and measure config load time (<50ms target) and debounce frequency (≤1 write/sec) in apps/krager/src/lib/services/config-store.test.ts — if targets not met, discuss with user before optimizing
- [x] T047 Run full test suite (all existing 172 + new tests pass) via pnpm test in apps/krager/
- [x] T048 Run biome check --write, svelte-check (0 errors), type validation via pre-commit checklist in apps/krager/
- [x] T049 Run quickstart.md validation steps end-to-end (install, build, dev mode, config file inspection)
- [ ] T050 [P] Write live tests for query parameter overrides (top_k, preset, include_debug, show_sources) against running kragd in tests/live/ *(deferred — requires running kragd instance)*

---

## Deferred: User Story 8 — Index Path Selection (P3)

> **Blocked**: kragd `/status` does not expose configured source directories. See research.md R6.
>
> **Recommendation**: Extend `ServiceStatus` with `source_directories: list[str]` in a future kragd sprint.
>
> **Affected FRs**: FR-026, FR-027, FR-028 will be implemented when API support is available.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1+US2 (Phase 3)**: Depends on Phase 2 — MVP milestone
- **US3 (Phase 4)**: Depends on Phase 2 (+ Phase 3 for full config persistence)
- **US4 (Phase 5)**: Depends on Phase 4 (builds on query state module)
- **US5 (Phase 6)**: Depends on Phase 2 (uses config store + UI primitives)
- **US6 (Phase 7)**: Depends on Phase 2 (minimal dependencies)
- **US7 (Phase 8)**: Depends on Phase 6 (settings state + SettingsPanel)
- **US9 (Phase 9)**: Depends on Phase 2 only (trivial, no config dependency)
- **Polish (Phase 10)**: Depends on all implemented phases

### User Story Dependencies

- **US1+US2 (P1)**: After Phase 2 — no other story dependencies
- **US3 (P2)**: After Phase 2 — independent of US1 (config adds persistence but isn't required for controls)
- **US4 (P2)**: After US3 — builds on query state module
- **US5 (P2)**: After Phase 2 — reads from all state modules but can reference them before they exist
- **US6 (P3)**: After Phase 2 — independent
- **US7 (P3)**: After US5 — uses settings state and SettingsPanel
- **US9 (P3)**: After Phase 2 — fully independent

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD — constitution Principle II)
- State modules before components
- Core implementation before integration/wiring
- Story complete and independently testable before moving to next priority

### Parallel Opportunities

**After Phase 2 completes, these can start in parallel**:
- US1+US2 (Phase 3) ‖ US3 (Phase 4) ‖ US5 (Phase 6) ‖ US6 (Phase 7) ‖ US9 (Phase 9)

**Sequential dependencies**:
- US4 must follow US3 (shared query state module)
- US7 must follow US5 (shared settings state + SettingsPanel)

---

## Parallel Example: User Story 1+2

```bash
# Tests in parallel (different files):
Task T014: "Extend tests for connection config persistence"
Task T015: "Write tests for ConnectionBar pre-fill from config"

# Implementation sequential (shared state):
Task T016 → T017 → T018
```

## Parallel Example: UI Primitives (Phase 2)

```bash
# All test files in parallel:
Task T008: "Write tests for Select"
Task T009: "Write tests for Toggle"
Task T010: "Write tests for Slider"

# All implementations in parallel:
Task T011: "Create Select.svelte"
Task T012: "Create Toggle.svelte"
Task T013: "Create Slider.svelte"
```

## Parallel Example: After Phase 2

```bash
# Five stories can start simultaneously:
Phase 3 (US1+US2): Config persistence + connection
Phase 4 (US3): Query controls
Phase 6 (US5): Settings page
Phase 7 (US6): Transcript redesign
Phase 9 (US9): Embedding model display
```

---

## Implementation Strategy

### MVP First (US1+US2 Only)

1. Complete Phase 1: Setup (plugin installation)
2. Complete Phase 2: Foundational (types, config store, UI primitives)
3. Complete Phase 3: US1+US2 (persistent connection + local config)
4. **STOP and VALIDATE**: Connect, restart, verify pre-fill. Inspect settings.json.
5. Commit and continue to P2 stories

### Incremental Delivery

1. Setup + Foundational → Infrastructure ready
2. US1+US2 → Config persists across restarts → **MVP! ✅**
3. US3 → Query controls functional → Test independently
4. US4 → Critic controls functional → Test independently
5. US5 → Settings page centralized → Test independently
6. US6 → Transcript redesigned → Test independently
7. US7 → Window opacity adjustable → Test independently
8. US9 → All embedding models visible → Test independently
9. Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps to spec.md user stories (US1–US9, US8 deferred)
- US1 and US2 combined — they share config infrastructure and are both P1
- Presets hardcoded: strict, balanced, verbose, code (no kragd `/presets` endpoint)
- Critic is display-layer only — uses `DebugMetadata.critic_scores` when `include_debug: true`
- Window opacity via CSS `opacity` on root element (no native Tauri API)
- Config writes debounced 300ms via Tauri Store `autoSave` (FR-004)
- FR-026/027/028 (Index Path Selection) deferred to future sprint pending kragd API
- Commit after each story checkpoint per constitution

**Total**: 50 tasks | 10 phases (+ deferred US8) | 7 user stories implemented
**Task breakdown**: 4 setup + 9 foundational + 5 US1/US2 + 5 US3 + 5 US4 + 5 US5 + 6 US6 + 4 US7 (T041 completed by T031) + 2 US9 + 5 polish
**New test files**: 12 | **Extended test files**: 3 (connection, transcript, query state)
