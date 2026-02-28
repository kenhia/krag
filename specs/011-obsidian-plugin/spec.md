# Feature Specification: Obsidian Vault Plugin

**Feature Branch**: `011-obsidian-plugin`
**Created**: 2026-02-27
**Status**: Draft
**Input**: User description: "Obsidian Plugin — A krag plugin for indexing Obsidian vault content with path-based ownership, mixed-content routing, and virtual obsidian:// path prefixes"

## Overview

A krag file-type plugin purpose-built for Obsidian vault content. Unlike the generic markdown plugin which claims all `.md` files by extension, this plugin claims files by vault path, splits mixed content (prose vs fenced code blocks) into separate collections, and stores results under virtual `obsidian://` path prefixes for clean attribution. Exercises the plugin override routing, multi-collection indexing, custom retrieval modes, and domain lexicon features end-to-end.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Index an Obsidian Vault (Priority: P1)

As a krag user with an Obsidian vault on disk, I want to index my vault so that my notes become searchable through krag's query interface.

**Why this priority**: Without indexing there is nothing to query — this is the foundational capability.

**Independent Test**: Configure one vault path in `config.toml`, run `krag index`, and verify that notes from the vault appear in the index with `obsidian://` path prefixes.

**Acceptance Scenarios**:

1. **Given** a configured vault path `[plugins.obsidian.vaults] gratch = "~/obsidian/gratch"`, **When** the user runs `krag index -d ~/obsidian/gratch`, **Then** all `.md` files under that path are processed by the Obsidian plugin (not the generic markdown plugin), and stored with paths like `obsidian://gratch/todo/mynote.md`.
2. **Given** vault indexing completes, **When** the user queries `krag retrieve "meeting notes"`, **Then** results include chunks from the vault with the virtual path prefix in the `file_path` field.
3. **Given** no vault paths are configured, **When** the user installs the Obsidian plugin and indexes `.md` files outside a vault, **Then** the generic markdown plugin handles those files (Obsidian plugin does not claim them).

---

### User Story 2 — Mixed-Content Routing (Priority: P1)

As a krag user, I want fenced code blocks in my Obsidian notes to be indexed into the `code` collection while surrounding prose goes to `docs`, so that code-aware queries find inline code snippets.

**Why this priority**: This is the core differentiator from the generic markdown plugin and exercises the plugin collection routing override (Level 1 in CollectionRouter) which currently has no real consumers.

**Independent Test**: Index a note containing both prose and a fenced Python block, then verify via `krag retrieve` and `debug/qdrant` that the code chunk appears in the `code` collection and the prose chunk appears in the `docs` collection.

**Acceptance Scenarios**:

1. **Given** a vault note contains a fenced code block (` ```python ... ``` `), **When** it is indexed, **Then** the code block text is routed to the `code` collection and the remaining prose is routed to the `docs` collection.
2. **Given** a vault note contains only prose (no fenced code blocks), **When** it is indexed, **Then** all content goes to the `docs` collection.
3. **Given** a vault note contains multiple fenced code blocks with different language identifiers, **When** it is indexed, **Then** each code block becomes a separate chunk in the `code` collection, with the language identifier preserved in metadata.

---

### User Story 3 — Path-Based Plugin Ownership (Priority: P1)

As a krag user with both vault notes and non-vault markdown files, I want the Obsidian plugin to handle only vault-path files while the generic markdown plugin handles everything else.

**Why this priority**: Without path-based ownership, the Obsidian plugin would either conflict with or replace the markdown plugin for all `.md` files. This requires extending krag's plugin architecture.

**Independent Test**: Index a directory containing both vault and non-vault markdown files, verify via index status and metadata that each file was handled by the correct plugin.

**Acceptance Scenarios**:

1. **Given** vault path `~/obsidian/gratch` is configured and `~/docs/readme.md` exists outside the vault, **When** both directories are indexed, **Then** `~/obsidian/gratch/note.md` is handled by the Obsidian plugin and `~/docs/readme.md` is handled by the generic markdown plugin.
2. **Given** the Obsidian plugin is installed but no vault paths are configured, **When** `.md` files are indexed, **Then** the generic markdown plugin handles all of them.
3. **Given** two vaults are configured (`gratch` and `work`), **When** files from both are indexed, **Then** each gets the correct virtual path prefix (`obsidian://gratch/...` and `obsidian://work/...`).

---

### User Story 4 — Virtual Path Display (Priority: P2)

As a krag user querying vault content, I want results to show clean `obsidian://vault-name/path` references instead of raw filesystem paths, so I can identify which vault and note a result came from.

**Why this priority**: Improves discoverability and UX but not strictly required for functional indexing/retrieval.

**Independent Test**: Query indexed vault content and verify the `file_path` field in results uses the `obsidian://` prefix with the vault name.

**Acceptance Scenarios**:

1. **Given** a file at `~/obsidian/gratch/projects/todo.md` is indexed with vault name `gratch`, **When** it appears in query results, **Then** `file_path` is `obsidian://gratch/projects/todo.md`.
2. **Given** a file is indexed with virtual path, **When** displayed via `krag query` CLI, **Then** the `obsidian://` prefix is shown clearly.

---

### User Story 5 — Custom Obsidian Retrieval Mode (Priority: P2)

As a krag user, I want an `obsidian` retrieval mode that targets the `docs` and `code` collections with vault-appropriate weights, so I get well-ranked results from vault content.

**Why this priority**: Enhances query quality for vault content but users can already query via the `default` mode.

**Independent Test**: Query with `--mode obsidian` and verify results are drawn from `docs` and `code` collections with the defined weights.

**Acceptance Scenarios**:

1. **Given** vault content is indexed, **When** the user queries with `--mode obsidian`, **Then** results are drawn from `docs` (weight 1.0) and `code` (weight 0.7) collections, excluding `tests` and `text`.
2. **Given** the `obsidian` mode is installed, **When** the user runs `krag query "my notes" --mode obsidian`, **Then** the critic is enabled with threshold 3 to filter low-relevance vault fragments.

---

### User Story 6 — Obsidian-Specific Lexicon (Priority: P3)

As a krag user querying vault content, I want Obsidian-specific terminology (backlinks, daily notes, canvas, etc.) recognized in the domain lexicon so that queries using vault jargon get better retrieval.

**Why this priority**: Nice-to-have polish that improves query quality for Obsidian-savvy users but is not essential.

**Independent Test**: Verify lexicon entries exist for Obsidian terms after plugin initialization by checking the lexicon refresh endpoint.

**Acceptance Scenarios**:

1. **Given** the Obsidian plugin is enabled, **When** the domain lexicon is refreshed, **Then** Obsidian-specific terms (backlink, daily note, canvas, dataview, template, frontmatter, wikilink) are available.

---

### Edge Cases

- What happens when a vault path does not exist on disk? The plugin logs a warning during initialization and skips that vault — no error raised.
- What happens when a fenced code block has no language identifier? It is treated as prose and routed to `docs`.
- What happens when the same file is under two overlapping vault paths? The first matching vault (in configuration order) wins.
- What happens when a vault file is zero-byte or binary? Handled gracefully — empty text returned, binary files skipped.
- What happens when the Obsidian plugin and markdown plugin are both installed? Path-based handlers take priority over extension-based handlers for files under a vault path; files outside vaults are handled by the markdown plugin.

## Requirements *(mandatory)*

### Functional Requirements

#### Plugin Core

- **FR-001**: System MUST provide a new `krag-plugin-obsidian` Python package implementing `FileTypeHandler`.
- **FR-002**: Plugin MUST claim `.md` files only when they reside under a configured vault path.
- **FR-003**: Plugin MUST NOT claim `.md` files outside configured vault paths — those remain handled by the generic markdown plugin.
- **FR-004**: Plugin MUST support multiple vault configurations, each with a human-readable name and local path.
- **FR-005**: Plugin MUST register via the `krag.plugins` entry point group.

#### Plugin Architecture Extension

- **FR-006**: The `PluginRegistry.get_handler_for_file()` method MUST support path-based handler resolution in addition to extension-based resolution.
- **FR-007**: The `FileTypeHandler` interface MUST be extended with a `claims_file(file_path: Path) -> bool` method that defaults to `False` for backward compatibility.
- **FR-008**: The resolution order in `get_handler_for_file()` MUST be: path-claiming plugins (via `claims_file`) → extension-based plugins → no handler.

#### Content Splitting & Routing

- **FR-009**: Plugin MUST split note content into prose segments and fenced code blocks.
- **FR-010**: Fenced code blocks with a language identifier MUST be routed to the `code` collection.
- **FR-011**: Fenced code blocks without a language identifier MUST be routed to the `docs` collection (treated as prose).
- **FR-012**: Prose segments (everything outside fenced code blocks) MUST be routed to the `docs` collection.
- **FR-013**: Each code block MUST preserve its language identifier in chunk metadata (`language` field).
- **FR-014**: Plugin MUST annotate each chunk's payload with `target_collection` metadata to direct chunks to the correct collection. The indexer routes per-chunk when this field is present.

#### Virtual Paths

- **FR-015**: Plugin MUST replace the vault root path with `obsidian://vault-name/` in all stored `file_path` metadata.
- **FR-016**: Virtual paths MUST be deterministic — the same file always produces the same virtual path.
- **FR-017**: Multiple vaults MUST produce distinct prefixes (e.g., `obsidian://gratch/...`, `obsidian://work/...`).

#### Configuration

- **FR-018**: Plugin MUST be configurable via `[plugins.obsidian]` section in `config.toml`.
- **FR-019**: Vault mappings MUST be specified under `[plugins.obsidian.vaults]` as `name = "path"` pairs.
- **FR-020**: Plugin MUST validate that configured vault paths exist on disk during initialization and warn (not error) for missing paths.
- **FR-021**: Plugin MUST provide a Pydantic `config_schema()` for validation of the vault configuration.

#### Frontmatter

- **FR-022**: Plugin MUST parse YAML frontmatter (between `---` delimiters) and strip it from indexed text while preserving frontmatter fields as chunk metadata.

#### Retrieval Mode

- **FR-023**: System MUST include a built-in `obsidian` retrieval mode TOML targeting `docs` (weight 1.0) and `code` (weight 0.7).
- **FR-024**: The `obsidian` mode MUST enable the context critic with threshold 3.
- **FR-025**: The `obsidian` mode MUST use the `balanced` prompt preset.

#### Lexicon

- **FR-026**: Plugin MUST contribute Obsidian-specific terms to the domain lexicon on initialization.
- **FR-027**: Terms MUST include at minimum: backlink, daily note, canvas, dataview, template, frontmatter, wikilink, MOC (map of content), tag, vault.

### Key Entities

- **Vault**: A named mapping from a human-readable identifier to a local filesystem path containing Obsidian notes. Each vault has a unique name used in virtual path prefixes.
- **Note**: A markdown file within a vault. May contain mixed content (prose + fenced code blocks).
- **Content Segment**: A contiguous section of a note that is either prose or a fenced code block. Each segment is routed to a specific collection independently.
- **Virtual Path**: A synthetic `obsidian://vault-name/relative-path` replacing the filesystem path for display and retrieval attribution.

## Assumptions

- Obsidian vaults are local directories containing `.md` files — no Obsidian Sync or remote vault support needed.
- The existing `krag-plugin-markdown` plugin will continue to handle all `.md` files not under a vault path.
- Fenced code block detection uses standard CommonMark syntax (triple backtick with optional language identifier).
- The plugin does not need to understand Obsidian-specific link syntax (`[[wikilinks]]`, `![[embeds]]`) for indexing — these are treated as prose text. Wikilink resolution could be a future enhancement.
- The plugin does not parse or index Obsidian canvas (`.canvas`) files — only `.md` files in vaults.
- Performance is acceptable for vaults up to 10,000 notes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can index an Obsidian vault and query its content within 5 minutes of initial configuration.
- **SC-002**: Mixed-content notes correctly split code and prose into separate collections in 100% of indexed files.
- **SC-003**: Virtual path prefixes appear correctly in 100% of query results for vault-sourced content.
- **SC-004**: No regressions — existing markdown plugin continues to handle non-vault `.md` files identically.
- **SC-005**: Path-based plugin resolution adds less than 10ms overhead per file during indexing.
- **SC-006**: The `obsidian` retrieval mode returns relevant vault results for domain-specific queries (manual verification by vault owner).
- **SC-007**: Plugin handles vaults of up to 10,000 notes without errors or timeouts.
