# Feature Specification: Krager Enhancements

**Feature Branch**: `014-krager-enhancements`
**Created**: 2026-03-03
**Status**: Draft
**Input**: User description: "Krager enhancements: settings persistence, query controls, transcript redesign, and UI polish from manual testing observations"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Persistent Connection Settings (Priority: P1)

A user launches krager after having previously connected to a kragd instance. Instead of re-entering the host and port every time, the app remembers the last successful connection and pre-fills those values. The user simply clicks "Connect" to reconnect.

**Why this priority**: This is the most frequently encountered friction point. Every app restart requires re-typing connection info, which is tedious and error-prone. Solving this provides immediate quality-of-life improvement and is the foundation for all other persisted settings.

**Independent Test**: Launch krager, connect to a kragd instance, close the app, relaunch — the host and port fields should be pre-filled with the previously used values.

**Acceptance Scenarios**:

1. **Given** a user has never connected before, **When** they launch krager, **Then** the host field shows "localhost" and port shows "8742" (current defaults).
2. **Given** a user previously connected to "karch9:8742", **When** they relaunch krager, **Then** the host field shows "karch9" and the port field shows "8742".
3. **Given** the persisted config file is missing or corrupted, **When** the user launches krager, **Then** the app falls back to hardcoded defaults without error.
4. **Given** a user connects to host A, then later connects to host B, **When** they relaunch, **Then** the fields show host B (most recent successful connection wins).

---

### User Story 2 — Local Configuration File (Priority: P1)

Krager has a local configuration file on the machine where the client runs. This file stores user preferences (connection info, query defaults, UI settings) so they persist across app restarts. The config is created automatically on first meaningful user action and updated as preferences change.

**Why this priority**: This is the infrastructure that enables all other persistence stories. Without a local config, nothing can be saved across restarts.

**Independent Test**: Change a setting, close the app, relaunch — the setting should still reflect the changed value. Additionally, manually inspect the config file on disk to verify it is human-readable.

**Acceptance Scenarios**:

1. **Given** krager is launched for the first time, **When** no config file exists, **Then** the app runs with hardcoded defaults (an empty config file may be created on initialization — this is acceptable).
2. **Given** a user successfully connects to a kragd instance, **When** the connection succeeds, **Then** the config file is created (if it doesn't exist) and updated with the connection info.
3. **Given** a config file exists with saved preferences, **When** krager launches, **Then** the app loads all saved preferences and applies them.
4. **Given** the config file is manually edited with invalid values, **When** krager loads it, **Then** invalid fields fall back to defaults and the user is not shown an error.
5. **Given** a user changes any persisted setting, **When** the change is applied, **Then** the config file is updated within a few seconds (debounced writes, not on every keystroke).

---

### User Story 3 — Query Controls (Priority: P2)

A user wants fine-grained control over their query parameters, matching the capabilities available in the CLI. The query panel exposes controls for top-k results, preset selection, debug mode, and source inclusion/exclusion so the user can tune retrieval behavior without switching to the CLI.

**Why this priority**: The query panel is the primary interaction surface. Missing controls force power users back to the CLI, undermining the purpose of the GUI.

**Independent Test**: Set top-k to 3, select a preset, toggle sources off, submit a query — verify the request payload includes the correct parameters and the response respects them.

**Acceptance Scenarios**:

1. **Given** the query panel is visible, **When** the user looks at the controls, **Then** they see inputs for: top-k (numeric), preset (dropdown), sources toggle (on/off), and a debug toggle.
2. **Given** the user sets top-k to 5, **When** they submit a query, **Then** the request includes `top_k: 5` and at most 5 source chunks are returned.
3. **Given** the user selects a preset from the dropdown, **When** they submit a query, **Then** the request includes the selected preset name.
4. **Given** no preset is selected, **When** the user submits a query, **Then** the request omits the preset field (server uses its default).
5. **Given** the user toggles "Show Sources" off, **When** they submit a query, **Then** source chunks are not displayed in the response (though the transcript retains them for the transcript page).
6. **Given** the user enables debug mode, **When** they submit a query, **Then** additional debug metadata is shown alongside the answer.
7. **Given** the user changes query control defaults on the settings page, **When** the app restarts, **Then** the configured defaults are restored from the local config (query panel changes are session-only and do not persist).

---

### User Story 4 — Critic Controls (Priority: P2)

A user wants to enable or disable the critic (answer quality evaluation) and set a cut-off score. When the critic is enabled, answers below the cut-off score are flagged, giving the user confidence in answer quality.

**Why this priority**: The critic is a key differentiator of krag's quality pipeline. Exposing it in the GUI lets users tune answer quality without CLI access.

**Independent Test**: Enable the critic, set a cut-off score of 0.7, submit a query — verify the request includes critic parameters and the response reflects the evaluation.

**Acceptance Scenarios**:

1. **Given** the query panel is visible, **When** the user looks at the controls, **Then** they see a critic enable/disable toggle and a cut-off score input.
2. **Given** the critic is disabled (default), **When** the user submits a query, **Then** `include_debug` is not automatically enabled and no critic evaluation is displayed.
3. **Given** the critic is enabled with a cut-off of 0.7, **When** the user submits a query, **Then** `include_debug` is automatically set to true and `DebugMetadata.critic_scores` are used to flag answers below the cut-off threshold.
4. **Given** the critic evaluates an answer below the cut-off, **When** the result is displayed, **Then** the answer is visually flagged as low-confidence (e.g., warning indicator).
5. **Given** the user changes critic settings, **When** the app restarts, **Then** the last-used critic settings are restored from config.

---

### User Story 5 — Settings Page (Priority: P2)

A user wants a dedicated settings page accessible from the sidebar navigation where they can view and adjust all configurable options in one place. Changes are saved automatically and take effect immediately.

**Why this priority**: As the number of configurable options grows (connection, query defaults, UI preferences), scattering them across panels becomes unmanageable. A centralized settings page provides discoverability and a consistent place for all preferences.

**Independent Test**: Navigate to Settings, change the window opacity and default top-k, navigate away, navigate back — verify values are still as set. Close and relaunch — verify values persist.

**Acceptance Scenarios**:

1. **Given** the app is running, **When** the user clicks the Settings icon in the sidebar, **Then** a settings page is displayed.
2. **Given** the settings page is visible, **When** the user looks at available settings, **Then** they see sections for: Connection defaults, Query defaults, Critic defaults, and Display preferences.
3. **Given** the user changes a setting, **When** the change is made, **Then** it takes effect immediately without requiring a save button or app restart.
4. **Given** the user changes a setting on the settings page, **When** they navigate to the relevant panel, **Then** the panel reflects the updated value.
5. **Given** a non-default value is set, **When** the app restarts, **Then** the non-default value is loaded from the config file.

**Behavioral Note — Settings vs. Query Panel Data Flow**: The settings page is the authoritative source for persisted defaults. Changes on the settings page are saved to the config file and propagated to the query panel state immediately on change. Changes on the query panel are session-only overrides — they do NOT propagate back to the settings page or persist to the config file. On app restart, all query controls reset to the settings page defaults.

---

### User Story 6 — Transcript Redesign (Priority: P3)

A user submits a query and wants to see the answer clearly without being overwhelmed by raw source chunks. The current query page shows the latest answer prominently with a source list and optional debug info, while the full transcript (including chunks) lives on a dedicated transcript page for deeper investigation.

**Why this priority**: Source chunks are valuable for debugging but obscure the primary answer. Separating the "current answer" view from the "full history" view reduces cognitive load for the most common workflow. This is a larger UX change that depends on other features being stable first.

**Independent Test**: Submit a query — verify the query page shows the answer and source list without chunk details. Navigate to the transcript page — verify full chunk content is visible there.

**Acceptance Scenarios**:

1. **Given** the user submits a query on the query page, **When** the answer arrives, **Then** the query page displays: the answer text, a list of source references (file name, relevance indicator), and debug info if enabled.
2. **Given** the query page is showing an answer, **When** the user looks at the display, **Then** raw chunk text is NOT shown on the query page.
3. **Given** the user navigates to the Transcript page via sidebar, **When** it loads, **Then** they see the full history of queries and answers with expandable chunk details.
4. **Given** the transcript page is visible, **When** the user expands a source entry, **Then** the full chunk text is displayed.
5. **Given** multiple queries have been submitted, **When** viewing the transcript, **Then** entries are displayed newest-first (already implemented).

---

### User Story 7 — Window Opacity (Priority: P3)

A user wants to adjust the window opacity so they can see through krager to reference material underneath. This is useful when copying text from documents or comparing results side-by-side.

**Why this priority**: A nice-to-have usability improvement for power users who work with overlapping windows. Lower priority because it doesn't affect core functionality.

**Independent Test**: Open settings, adjust opacity slider to 80%, then to 50% — verify the window becomes progressively more transparent.

**Acceptance Scenarios**:

1. **Given** the settings page is open, **When** the user adjusts the opacity control, **Then** the window opacity changes in real-time as a preview.
2. **Given** the user sets opacity to a value between 30% and 100%, **When** applied, **Then** the window renders at the specified opacity.
3. **Given** opacity is set below 30%, **When** applying, **Then** the value is clamped to 30% (minimum usable opacity).
4. **Given** the user sets a custom opacity, **When** the app restarts, **Then** the opacity is restored from config.

---

### User Story 8 — Index Path Selection (Priority: P3)

A user wants to choose which configured source paths to include in an indexing run rather than always indexing everything. The index panel shows the configured paths from the kragd server and lets the user select or deselect paths before triggering a run.

**Why this priority**: Selective indexing saves time when only certain content has changed. However, the current "index everything" behavior is functional, making this an optimization rather than a blocker.

**Independent Test**: Open the index panel, deselect one path, trigger indexing — verify only the selected paths are included in the index request.

**Acceptance Scenarios**:

1. **Given** the user is connected to kragd, **When** they open the index panel, **Then** the configured source paths are listed with checkboxes (all selected by default).
2. **Given** multiple paths are shown, **When** the user deselects one path and triggers indexing, **Then** the index request only includes the selected paths.
3. **Given** no paths are selected, **When** the user tries to trigger indexing, **Then** the Index button is disabled with a tooltip explaining why.
4. **Given** the kragd configuration has only one path, **When** the index panel loads, **Then** the single path is shown selected and the selection UI is still visible (but deselecting it disables the button).

---

### User Story 9 — Embedding Model Display (Priority: P3)

A user wants to see all configured embedding models on the system status page, not just the first one. This gives visibility into the full system configuration when multiple models are in use.

**Why this priority**: Informational improvement. The current display shows only one model which can be misleading. Low priority because it doesn't affect functionality.

**Independent Test**: Connect to a kragd instance with multiple embedding models configured — verify the system status page lists all of them.

**Acceptance Scenarios**:

1. **Given** the user is connected to kragd, **When** they view the system status page, **Then** all configured embedding models are listed.
2. **Given** kragd has one embedding model, **When** viewing system status, **Then** the single model is displayed.
3. **Given** kragd has multiple embedding models, **When** viewing system status, **Then** each model is listed with its name and any status information the server provides.

---

### Edge Cases

- What happens when the config file is on a read-only filesystem? The app should function normally with in-memory defaults and log a warning (no user-facing error).
- What happens when the user connects to a kragd version that doesn't support the `preset` field in `QueryRequest`? Controls should be present but show a "not supported" state or be disabled with an explanation.
- What happens when the kragd server returns no configured paths for indexing? The index panel should display "No paths configured on server" instead of an empty list.
- What happens when opacity is set and the OS or window manager doesn't support transparency? The setting should be silently ignored.
- What happens when the user rapidly toggles settings? Config writes are debounced to avoid file system thrashing.

## Requirements *(mandatory)*

### Functional Requirements

**Configuration & Persistence**

- **FR-001**: System MUST persist user preferences to a local configuration file on the client machine.
- **FR-002**: System MUST load saved preferences on startup and apply them before the user interacts with the app.
- **FR-003**: System MUST fall back to hardcoded defaults when the config file is missing, unreadable, or contains invalid values.
- **FR-004**: System MUST debounce config file writes to avoid excessive disk I/O (no more than one write per second).
- **FR-005**: System MUST save the host and port from the last successful connection to the config.
- **FR-006**: System MUST save non-default query control values (top-k, preset, debug, sources, critic) to the config.
- **FR-007**: System MUST save display preferences (opacity, theme) to the config.

**Query Controls**

- **FR-008**: System MUST expose a top-k control in the query panel that accepts a positive integer.
- **FR-009**: System MUST expose a preset dropdown in the query panel populated with available presets.
- **FR-010**: System MUST expose a sources toggle (show/hide) in the query panel.
- **FR-011**: System MUST expose a debug toggle in the query panel.
- **FR-012**: System MUST include the user-set query parameters in all query and retrieve requests to kragd.

**Critic Controls**

- **FR-013**: System MUST expose a critic enable/disable toggle in the query panel.
- **FR-014**: System MUST expose a critic cut-off score input (numeric, 0.0–1.0) when the critic is enabled.
- **FR-015**: System MUST set `include_debug: true` when critic is enabled to surface critic scores from `DebugMetadata`.
- **FR-016**: System MUST visually indicate when an answer's critic score falls below the cut-off threshold.

**Settings Page**

- **FR-017**: System MUST provide a Settings panel accessible from the sidebar navigation.
- **FR-018**: System MUST organize settings into logical sections (Connection, Query, Critic, Display).
- **FR-019**: System MUST apply setting changes immediately without requiring a save action or restart.

**Transcript Redesign**

- **FR-020**: System MUST display the current/latest answer on the query page with a source reference list (file names and relevance indicators) but without raw chunk text.
- **FR-021**: System MUST provide a dedicated Transcript panel accessible from the sidebar showing the full interaction history.
- **FR-022**: System MUST allow expanding individual source entries on the transcript panel to reveal full chunk text.

**Window Opacity**

- **FR-023**: System MUST allow adjusting window opacity via a slider or numeric input.
- **FR-024**: System MUST enforce a minimum opacity of 30% to maintain usability.
- **FR-025**: System MUST apply opacity changes in real-time as a live preview.

**Index Path Selection**

- **FR-026**: System MUST display configured source paths from kragd in the index panel.
- **FR-027**: System MUST allow users to select/deselect individual paths before triggering an indexing run.
- **FR-028**: System MUST disable the Index button when no paths are selected.

**Embedding Model Display**

- **FR-029**: System MUST display all configured embedding models on the system status page, not just the first one.

### Key Entities

- **UserConfig**: The persisted configuration — contains connection settings, query defaults, critic defaults, display preferences. Stored as a human-readable file on the client machine.
- **QueryParameters**: The set of parameters controlling a query — top-k, preset, mode, retrieve-only, sources visibility, debug mode. Includes critic sub-parameters when enabled.
- **CriticConfig**: Enable/disable flag and cut-off score threshold for answer quality evaluation.
- **TranscriptEntry**: An interaction record containing query text, answer text, source references, chunk data, debug metadata, and timestamp. Extended to support collapsed/expanded chunk display.
- **SourceReference**: A summarized view of a source chunk — file name, relevance score — shown on the query page without raw text.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can reconnect to a previously-used kragd instance in one click (no re-typing) after app restart.
- **SC-002**: All user-configurable preferences survive an app restart cycle without data loss.
- **SC-003**: Users can set top-k, preset, sources, debug, and critic parameters without leaving the query page.
- **SC-004**: The query page displays the answer and source list clearly without showing raw chunk text.
- **SC-005**: Full transcript with expandable chunks is accessible within one click from the query page.
- **SC-006**: Settings page is discoverable from the sidebar navigation and displays all configurable options organized by category.
- **SC-007**: Window opacity can be adjusted between 30% and 100% with immediate visual feedback.
- **SC-008**: ~~Users can selectively index specific source paths rather than all-or-nothing.~~ **DEFERRED** — blocked on kragd API (see research.md R6). FR-026/027/028 deferred.
- **SC-009**: All configured embedding models are visible on the system status page.
- **SC-010**: Config file corruptions or read failures never crash the app — graceful fallback to defaults in all cases.

## Assumptions (with Resolution Status)

- ~~The kragd server's `/status` or similar endpoint provides the list of configured source paths for index path selection (FR-026).~~ **Resolved — see research.md R6**: kragd `/status` does NOT expose source directories. US8 (FR-026/027/028) deferred pending kragd API addition.
- ~~The kragd query API already supports `top_k`, `preset`, `critic`, and `no_sources` parameters based on CLI parity.~~ **Resolved — see research.md R3/R4**: `top_k`, `preset`, and `include_debug` are supported. `no_sources` does not exist as an API parameter (implemented as client-side display filtering). Critic has no per-request override (display-layer only via `DebugMetadata.critic_scores`).
- ~~Tauri v2 provides a native API or plugin for window opacity control.~~ **Resolved — see research.md R2**: No native Tauri opacity API exists. Using CSS `opacity` on root element (cross-platform).
- The config file format will be human-readable (TOML or JSON) to allow manual editing if needed. **Resolved**: JSON via Tauri Store plugin.
- ~~Preset names are available from kragd (either hardcoded in krager or fetched from an endpoint).~~ **Resolved — see research.md R3**: No `/presets` endpoint. Presets hardcoded as `strict/balanced/verbose/code` matching kragd's `VALID_PRESETS`.