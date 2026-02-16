# Feature Specification: WSL to Native Linux Migration

**Feature Branch**: `003-wsl-migration`  
**Created**: 2026-02-15  
**Status**: Draft  
**Input**: User description: "Migrate krag from WSL to native Arch Linux with configurable storage paths, group-based /krag permissions, GPU acceleration, and Python 3.13+ support"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configurable Storage Paths (Priority: P1)

As a user running krag on a machine with a dedicated storage drive, I want to configure where krag stores its data (vector index, corpus cache, models, etc.) through the existing configuration system, so that I can take advantage of fast dedicated storage without relying on symlinks or XDG environment variable overrides.

**Why this priority**: Storage path configuration is the foundation for using krag on any machine with non-default storage layouts. Without this, the dedicated 2TB NVME drive cannot be properly utilized and all other migration goals are blocked.

**Independent Test**: Can be fully tested by setting custom paths in `config.toml`, running `krag config validate`, and verifying that krag reads from and writes to the configured paths. Delivers configurable storage independent of all other migration work.

**Acceptance Scenarios**:

1. **Given** a fresh krag installation with no custom paths configured, **When** krag starts, **Then** it uses the existing XDG-based default paths (`~/.cache/krag/storage`, `~/.cache/krag/models`, etc.)
2. **Given** a `config.toml` with custom storage paths set (e.g., `vector_store_path = "/krag/index"`, `model_cache_path = "/krag/models"`), **When** krag starts, **Then** it uses the configured paths for all storage operations
3. **Given** a `config.toml` with a custom path that does not yet exist but whose parent is writable, **When** krag starts, **Then** it creates the necessary directory structure and proceeds normally
4. **Given** a `config.toml` with a custom path pointing to a location where the user lacks write permissions, **When** krag starts, **Then** it reports a clear error identifying the path and the permission issue
5. **Given** a `config.toml` with some paths customized and others omitted, **When** krag starts, **Then** omitted paths fall back to their XDG defaults while customized paths are honored

---

### User Story 2 - Group-Based Storage Permissions (Priority: P2)

As a system administrator, I want to set up a shared group for krag storage access so that both my personal user account and a future service account can access the dedicated storage directory without running as root.

**Why this priority**: Proper permissions are required before krag can actually use `/krag`. This is a one-time system setup task that must happen before indexing/querying on the new machine, but does not require code changes.

**Independent Test**: Can be fully tested by creating the group, adding the user, changing ownership, and verifying read/write access to `/krag` subdirectories as the non-root user.

**Acceptance Scenarios**:

1. **Given** `/krag` and its subdirectories owned by root, **When** a `krag` group is created and the user is added to it, **Then** the user can read and write files in all `/krag` subdirectories
2. **Given** the `krag` group exists with the user as a member, **When** a future `krag` service user is added to the same group, **Then** both users can access the storage directories without permission conflicts
3. **Given** the group and permissions are configured, **When** krag writes data to `/krag/index`, **Then** new files inherit the group ownership so they remain accessible to all group members

---

### User Story 3 - GPU-Accelerated Inference (Priority: P3)

As a user with an NVIDIA GPU, I want krag to use my GPU for embedding generation and LLM inference so that indexing and query response times are significantly faster than CPU-only operation.

**Why this priority**: GPU acceleration is the primary performance benefit of migrating to a dedicated machine. However, krag is fully functional without it (CPU fallback exists for embeddings; LLM offloading is additive), making it lower priority than storage configuration.

**Independent Test**: Can be tested by setting `embedding_device = "cuda"` in config, indexing a small corpus, and verifying the GPU is utilized. LLM GPU offloading can be tested by querying with `n_gpu_layers` configured.

**Acceptance Scenarios**:

1. **Given** the configuration has `embedding_device = "cuda"` and CUDA drivers are installed, **When** krag generates embeddings, **Then** it uses the GPU and completes at least 5x faster than CPU-only mode
2. **Given** the configuration specifies GPU layers for LLM offloading, **When** krag performs a query, **Then** it offloads the configured number of model layers to the GPU and completes at least 2x faster than CPU-only
3. **Given** the configuration has `embedding_device = "cuda"` but no GPU is available, **When** krag starts, **Then** it reports a clear warning and falls back to CPU operation gracefully

---

### User Story 4 - Python 3.13+ Compatibility (Priority: P4)

As a developer, I want krag to run on Python 3.13+ so that I can use the latest language features and avoid maintaining older Python versions on my system.

**Why this priority**: The target machine has Python 3.14 installed as system Python. While krag can be pinned to an older version via `uv`, running on 3.13+ reduces friction and future-proofs the project. This may require dependency updates but no user-facing changes.

**Independent Test**: Can be tested by creating a virtual environment with Python 3.13, installing krag, and running the full test suite.

**Acceptance Scenarios**:

1. **Given** a Python 3.13+ environment, **When** all krag dependencies are installed, **Then** installation completes without errors
2. **Given** a Python 3.13+ environment with krag installed, **When** the full test suite runs, **Then** all tests pass
3. **Given** the `pyproject.toml` is updated, **When** krag is installed in a Python 3.11 or 3.12 environment, **Then** it continues to work (backward compatibility maintained)

---

### User Story 5 - Re-Index on New Machine (Priority: P5)

As a user who has migrated krag to new hardware, I want to re-index my corpus on the new machine rather than copy vector data from the old one, so that the index is optimized for the new storage layout and embedding device.

**Why this priority**: Re-indexing is an operational task users perform after migration is complete. It validates the full pipeline works end-to-end on the new machine.

**Independent Test**: Can be tested by pointing `directory_paths` at a corpus, running `krag index`, and verifying successful query results.

**Acceptance Scenarios**:

1. **Given** krag is configured with custom storage paths and a corpus directory, **When** the user runs `krag index`, **Then** the index is built in the configured `vector_store_path`
2. **Given** an existing index from a previous indexing run, **When** the user runs `krag index` again, **Then** incremental indexing detects and processes only changed files

---

### Edge Cases

- What happens when configured storage paths point to a different filesystem (e.g., NVME) than the OS root? (Permissions, space reporting, and atomic operations should work across filesystems)
- What happens when the `/krag` drive is unmounted or unavailable? (krag should report a clear error, not silently fall back to XDG defaults) - Note: should add a specific config item to declare that a storage path is a "mount" path and have krag verify that the location is in fact mounted.
- What happens when `config.toml` contains both a custom `vector_store_path` and the user has set `XDG_CACHE_HOME`? (Explicit config file settings take precedence over XDG environment variables)
- What happens when GPU drivers are installed but CUDA runtime is unavailable? (Graceful fallback with clear diagnostics)
- What happens when a dependency does not yet support Python 3.13? (Document the constraint; pin to 3.13 as minimum target, test 3.14 as stretch goal) - Note: one of the needed libraries does not currently have a wheel for 3.14 (llama-cpp-python)

## Requirements *(mandatory)*

### Functional Requirements

#### Storage Configuration

- **FR-001**: System MUST allow configuring the vector store path via `config.toml` (under a `[storage]` or existing `[vector_store]` section), with the current XDG-based path as the default when not specified
- **FR-002**: System MUST allow configuring the model cache path via `config.toml`, with the current XDG-based path (`~/.cache/krag/models`) as the default
- **FR-003**: System MUST allow configuring a corpus storage path via `config.toml` for local corpus caching, with an XDG-based default
- **FR-004**: System MUST validate all configured storage paths at startup and report clear errors for inaccessible or non-writable locations
- **FR-005**: System MUST create configured storage directories (and parent directories) if they do not exist, provided the user has write permission to the parent
- **FR-006**: Explicit storage paths in `config.toml` MUST take precedence over XDG environment variable overrides
- **FR-007**: System MUST support both absolute paths and `~`-expanded paths in storage configuration

#### Permissions & Access

- **FR-008**: Documentation MUST include instructions for creating a `krag` system group, adding users to it, and setting ownership/permissions on the shared storage directory
- **FR-009**: Documentation MUST include instructions for setting the setgid bit on storage directories so new files inherit group ownership

#### GPU Acceleration

- **FR-010**: System MUST support configuring the number of GPU layers to offload for LLM inference (via `llm_n_gpu_layers` setting), defaulting to 0 (CPU-only) for backward compatibility
- **FR-011**: System MUST detect GPU availability at startup and warn the user if GPU is configured but unavailable, falling back to CPU
- **FR-012**: The existing `embedding_device` configuration field MUST continue to work, supporting `"cpu"` and `"cuda"` values

#### Python Compatibility

- **FR-013**: System MUST run on Python 3.13 or later, if the required libraries support this
- **FR-014**: System SHOULD maintain backward compatibility with Python 3.11 and 3.12 if feasible, but this is optional if Python 3.13 requirements necessitate breaking older versions
- **FR-015**: All dependencies MUST be verified for Python 3.13 compatibility; any incompatible dependencies MUST be documented with workarounds or version pins

#### Configuration Display & Validation

- **FR-016**: The `krag config show` command MUST display all resolved storage paths (showing whether each path comes from config file, XDG default, or environment override)
- **FR-017**: The `krag config validate` command MUST check that all storage paths are accessible and writable

### Key Entities

- **Storage Path Configuration**: A set of named storage locations (vector store, model cache, corpus cache, logs) each with a configurable path and an XDG-based default. Stored in `config.toml` and resolved at startup.
- **Storage Group**: A UNIX group (e.g., `krag`) that controls access to shared storage directories. Members of this group have read/write access to all krag storage locations on shared media.

## Assumptions

- The target machine is running Arch Linux with NVIDIA GPU drivers already installed (or installable via `pacman`)
- The dedicated NVME drive is mounted at `/krag` and will remain at this mount point
- The user manages Python environments with `uv`
- `llama-cpp-python` will be rebuilt with CUDA support via `CMAKE_ARGS` — this is an installation-time concern, not a code change
- PyTorch CUDA support will be handled by installing the appropriate `torch` build — this is an installation-time concern
- The existing test suite (551 tests) is the acceptance bar for Python compatibility
- TOML is the primary configuration format; YAML support is legacy and not extended with new fields

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All configured storage paths are respected by krag — files are created in the specified locations, not the XDG defaults, when custom paths are set
- **SC-002**: krag starts and operates normally using paths on a dedicated drive (`/krag`) separate from the OS filesystem
- **SC-003**: A non-root user in the `krag` group can perform all krag operations (index, query, config) against `/krag` storage without permission errors
- **SC-004**: Embedding generation completes at least 5x faster with `embedding_device = "cuda"` compared to `"cpu"` on the same corpus
- **SC-005**: LLM inference with GPU offloading returns query responses at least 2x faster than CPU-only operation
- **SC-006**: The full test suite passes on Python 3.13+
- **SC-007**: The full test suite continues to pass on Python 3.11 and 3.12
- **SC-008**: `krag config show` accurately displays all resolved storage paths and their sources
- **SC-009**: A user can go from fresh clone to working krag installation (with GPU acceleration and custom storage) following documentation alone, within 30 minutes
