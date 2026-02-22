# Feature Specification: Polish and Bugs Sprint

**Feature Branch**: `008-polish-and-bugs`  
**Created**: 2026-02-21  
**Status**: Draft  
**Input**: User description: "polish and bugs sprint — ad-hoc manual testing and fixes"

## Overview

An ad-hoc sprint focused on manual end-to-end testing of the kragd service architecture (Sprint 007) and fixing bugs discovered during real-world usage. Tasks will be added incrementally as issues are discovered rather than planned upfront.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fix Runtime Bugs Found During Manual Testing (Priority: P1)

As a krag user, I run every CLI command (`krag query`, `krag index`, `krag status`, `krag debug qdrant`, etc.) against the kragd service and expect them to work without 500 errors or crashes.

**Why this priority**: Core functionality must work reliably before any polish work.

**Independent Test**: Run each CLI command manually and verify it returns expected results without server-side errors.

**Acceptance Scenarios**:

1. **Given** kragd is running with a populated index, **When** the user runs any CLI command, **Then** no 500 errors or unhandled exceptions occur
2. **Given** a bug is discovered during manual testing, **When** the fix is applied, **Then** all existing tests continue to pass (1056+)

---

### User Story 2 - Polish UX and Output Quality (Priority: P2)

As a krag user, I expect CLI output to be clear, well-formatted, and informative — status displays should show accurate data, error messages should be actionable, and logging should capture useful diagnostic info.

**Why this priority**: Good UX builds confidence in the tool's reliability.

**Independent Test**: Review CLI output for each command and verify it reads well and contains accurate information.

**Acceptance Scenarios**:

1. **Given** kragd is running, **When** the user runs `krag status`, **Then** all displayed metrics are accurate and well-formatted
2. **Given** an operation fails, **When** the error is displayed to the user, **Then** the message explains what went wrong and how to fix it

---

### User Story 3 - Async Indexing with Immediate Response (Priority: P1)

As a krag user, when I run `krag index`, I expect the service to acknowledge the request immediately rather than blocking until indexing completes — because large indexes can take many minutes and the HTTP client times out.

**Why this priority**: The current synchronous design causes client timeouts on any non-trivial index operation, making indexing effectively broken for real workloads.

**Independent Test**: Run `krag index -d ~/src` against kragd and verify the CLI returns immediately with an acknowledgment. Then verify `krag index --status` shows indexing in progress. After indexing completes, verify queries work normally.

**Acceptance Scenarios**:

1. **Given** kragd is running, **When** the user runs `krag index -d ~/src`, **Then** the CLI returns immediately with a message like "Indexing started — use `krag index --status` to check progress"
2. **Given** indexing is in progress, **When** the user runs `krag index --status`, **Then** the status shows "running" with current progress if available
3. **Given** indexing is in progress, **When** the user runs `krag query`, **Then** the service responds with a clear message that indexing is underway and queries are temporarily unavailable
4. **Given** any HTTP request fails with a timeout, **When** the error is displayed to the user, **Then** the CLI shows a clean one-line error (not a raw stack trace) and logs the full trace to the log file
5. **Given** the user runs `krag index -d ~/src --wait`, **Then** the CLI polls for status and shows periodic progress until indexing completes (nice-to-have)

---

### Edge Cases

- Issues will be discovered ad-hoc during manual testing — this list grows during the sprint
- Known areas to exercise: query with different spaces, indexing with overrides, debug filters, LLM hot-swap
- Large indexing jobs can take 10+ minutes — client must not block for the duration
- Duplicate index requests while one is already running should be rejected gracefully

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: All bugs discovered during manual testing MUST be fixed and verified with passing tests
- **FR-002**: Fixes MUST NOT break existing test suite (maintain 1056+ passing tests)
- **FR-003**: Each fix MUST be tracked as a task in the sprint task list for clear record-keeping
- **FR-004**: The `/index` endpoint MUST return immediately after validating the request, running indexing in the background
- **FR-005**: The service MUST track indexing state and report it via `/index/status`
- **FR-006**: The service MUST respond to queries during indexing with a clear "indexing in progress" message rather than silently queuing or timing out
- **FR-007**: The CLI MUST handle expected HTTP errors (timeouts, connection refused) with clean user-facing messages, logging stack traces to the log file

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All CLI commands work end-to-end against kragd without 500 errors
- **SC-002**: Test suite passes at or above the pre-sprint baseline (1056 passed, 2 skipped)
- **SC-003**: All discovered issues are tracked and resolved in the sprint task list
- **SC-004**: `krag index` returns within 2 seconds regardless of index size
- **SC-005**: Users never see raw Python stack traces for expected operational errors
