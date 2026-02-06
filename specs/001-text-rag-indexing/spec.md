# Feature Specification: Text-Based RAG Indexing & Retrieval System

**Feature Branch**: `001-text-rag-indexing`  
**Created**: 2026-02-03  
**Status**: Draft  
**Input**: User description: "Personal Multimodal RAG System - Phase 1: Text content indexing and retrieval with local LLM synthesis"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Query Personal Knowledge Base (Priority: P1)

As a user, I want to ask questions about information in my personal files and receive synthesized answers from my local system, so I can quickly find relevant information across all my documents without manually searching through folders.

**Why this priority**: This is the core value proposition - enabling information retrieval from personal data. Without this, the system provides no user value.

**Independent Test**: Can be fully tested by indexing a small set of test documents, submitting a query, and verifying that relevant content is retrieved and synthesized into a coherent answer.

**Acceptance Scenarios**:

1. **Given** a set of indexed personal documents, **When** I submit a natural language query, **Then** the system returns a synthesized answer based on the most relevant content chunks
2. **Given** my query matches content in multiple files, **When** I submit the query, **Then** the system retrieves and synthesizes information from all relevant sources
3. **Given** my query has no relevant matches, **When** I submit the query, **Then** the system clearly indicates no relevant information was found
4. **Given** the system has indexed my files, **When** I query for specific technical information (e.g., code examples, configuration details), **Then** the system returns accurate, contextually relevant information

---

### User Story 2 - Index Local and Network Storage (Priority: P2)

As a user, I want to index text content from both my PC and NAS storage locations, so that all my personal files are searchable through the system regardless of where they're stored.

**Why this priority**: Essential for comprehensive coverage of personal data, but the query functionality (P1) can be demonstrated with a single directory first.

**Independent Test**: Can be tested independently by configuring multiple storage paths, running indexing, and verifying that files from all locations are discoverable in metadata storage.

**Acceptance Scenarios**:

1. **Given** configured directory paths on PC and NAS, **When** I initiate indexing, **Then** the system recursively discovers all text-based files in those locations
2. **Given** a large directory tree, **When** indexing runs, **Then** the system provides progress updates showing files processed
3. **Given** indexing has completed, **When** I review indexed files, **Then** metadata includes file paths, modification times, and file types for all discovered content
4. **Given** some directories contain build artifacts or dependencies (node_modules, venv), **When** indexing runs, **Then** these directories are automatically excluded unless explicitly included

---

### User Story 3 - Incremental Re-Indexing (Priority: P3)

As a user, I want the system to detect and re-index only new or modified files, so that I can keep my knowledge base current without waiting for full re-indexing of all files.

**Why this priority**: Improves user experience for ongoing use, but full indexing (P2) provides initial value. This is an optimization.

**Independent Test**: Can be tested by indexing a corpus, modifying specific files, running incremental update, and verifying only changed files are re-processed.

**Acceptance Scenarios**:

1. **Given** a previously indexed corpus, **When** I add new files and trigger incremental indexing, **Then** only the new files are processed
2. **Given** indexed files with tracked modification times, **When** I modify specific files and trigger incremental indexing, **Then** only the modified files are re-indexed
3. **Given** I delete indexed files from storage, **When** incremental indexing runs, **Then** the system removes those files from the index
4. **Given** a large corpus with few changes, **When** incremental indexing runs, **Then** processing completes significantly faster than full re-indexing

---

### User Story 4 - Configure Indexing Behavior (Priority: P4)

As a user, I want to configure which directories to include/exclude, which file types to index, and chunking parameters, so that I can tailor the system to my specific needs and avoid indexing irrelevant content.

**Why this priority**: Enhances flexibility and control, but reasonable defaults allow the system to work without extensive configuration.

**Independent Test**: Can be tested by modifying configuration settings, running indexing, and verifying that only specified directories and file types are processed according to the rules.

**Acceptance Scenarios**:

1. **Given** configuration file with directory paths, **When** I add or remove paths, **Then** subsequent indexing reflects the updated scope
2. **Given** configuration with file type filters, **When** I specify extensions to include, **Then** only those file types are indexed
3. **Given** default exclusion patterns, **When** I review configuration, **Then** common non-content directories are pre-excluded (node_modules, .git, build, cache)
4. **Given** chunking parameters in configuration, **When** I adjust chunk size and overlap, **Then** subsequent indexing uses the new parameters

---

### Edge Cases

- **Empty Query**: What happens when a user submits an empty or whitespace-only query?
- **No Indexed Content**: How does the system respond when queried before any content has been indexed?
- **Extremely Large Files**: How are files exceeding reasonable size limits handled during text extraction and chunking?
- **Binary Files Misidentified as Text**: What happens if the system attempts to extract text from binary files incorrectly identified as text?
- **Storage Unavailable**: How does the system handle cases where NAS or network storage becomes unavailable during indexing or querying?
- **Corrupt or Unreadable Files**: How are files that cannot be read or parsed handled without crashing the indexing process?
- **Very Long Document Chunks**: What happens if intelligent chunking produces chunks that exceed embedding model token limits?
- **Concurrent Indexing Requests**: How does the system behave if indexing is triggered while another indexing operation is already running?
- **Configuration Errors**: What happens if the configuration file contains invalid paths, unsupported file types, or malformed parameters?

## Requirements *(mandatory)*

### Functional Requirements

**File Discovery & Metadata**

- **FR-001**: System MUST recursively scan configured directories to discover all files within scope
- **FR-002**: System MUST maintain metadata for each discovered file including file path, size, modification timestamp, and file type
- **FR-003**: System MUST support configurable directory inclusion and exclusion patterns
- **FR-004**: System MUST automatically exclude common non-content directories (node_modules, .git, build, __pycache__, .venv, dist, target)
- **FR-005**: System MUST handle both local filesystem paths and network-mounted storage paths

**Text Extraction & Processing**

- **FR-006**: System MUST extract text content from supported file formats (plain text, markdown, source code, JSON, YAML, XML, CSV)
- **FR-007**: System MUST intelligently chunk extracted text into segments suitable for embedding (chunks respect semantic boundaries: paragraph breaks for prose, function/class boundaries for code)
- **FR-008**: System MUST support configurable chunk size and overlap parameters
- **FR-009**: System MUST preserve meaningful context boundaries when chunking by using semantic-aware splitting that avoids breaking mid-sentence for text or mid-function for code
- **FR-010**: System MUST handle files that exceed configured max_file_size_mb by logging a warning and skipping the file (files are never truncated to avoid data loss)

**Embedding Generation**

- **FR-011**: System MUST generate vector embeddings for all text chunks using a local embedding model
- **FR-012**: System MUST support configuration of which local embedding model to use (models must be sentence-transformers compatible and output consistent vector dimensions; changing models requires full re-indexing)
- **FR-013**: System MUST batch embedding generation to optimize throughput
- **FR-014**: System MUST store embeddings alongside chunk metadata

**Vector Storage**

- **FR-015**: System MUST persist embeddings and metadata in a vector store that supports similarity search
- **FR-016**: System MUST define an abstract VectorStore interface to enable future backend alternatives (Phase 1 implements Qdrant embedded mode only)
- **FR-017**: System MUST maintain associations between embeddings, source chunks, and original files

**Query & Retrieval**

- **FR-018**: System MUST accept natural language queries from users
- **FR-019**: System MUST generate query embeddings using the same model used for document embeddings
- **FR-020**: System MUST perform similarity search to retrieve top-k most relevant chunks
- **FR-021**: System MUST support configurable k value for retrieval
- **FR-022**: System MUST return chunk content along with source file metadata

**LLM Synthesis**

- **FR-023**: System MUST pass retrieved chunks and user query to a local LLM for answer synthesis
- **FR-024**: System MUST support configuration of which local LLM to use
- **FR-025**: System MUST handle cases where no relevant chunks are found by informing the user
- **FR-026**: System MUST display synthesized answers to the user (streaming support is planned for future phases)

**Incremental Indexing**

- **FR-027**: System MUST track file modification timestamps to detect changes
- **FR-028**: System MUST support incremental re-indexing that processes only new or modified files
- **FR-029**: System MUST remove embeddings for files that have been deleted from storage
- **FR-030**: System MUST update embeddings for files that have been modified since last indexing
- **FR-031**: System MUST persist FileMetadata state between CLI invocations to enable incremental indexing across separate runs

**Configuration**

- **FR-031**: System MUST support a configuration file for all tunable parameters
- **FR-032**: Configuration MUST include directory paths, file type filters, embedding model selection, vector store backend, chunking parameters, and LLM selection
- **FR-033**: System MUST validate configuration on startup and report clear errors for invalid settings

**Logging & Diagnostics**

- **FR-038**: System MUST log operational events (indexing progress, errors, configuration) to rotating log files by default
- **FR-039**: System MUST support a `--show-logs` flag to display INFO-level application logs on console in addition to file logging
- **FR-040**: System MUST suppress third-party library logs (httpx, sentence-transformers, qdrant, llama-cpp) at INFO level to reduce console noise
- **FR-041**: System MUST always display ERROR and CRITICAL level messages on console regardless of `--show-logs` setting
- **FR-042**: System MUST implement log rotation to prevent unbounded log file growth (max 10MB per file, keep 5 backup files)

**Observability**

- **FR-034**: System MUST log progress during indexing operations (files processed, chunks generated, embeddings created)
- **FR-035**: System MUST log errors encountered during file processing without terminating the entire indexing process
- **FR-036**: System MUST provide visibility into query processing (query embedding, retrieval, synthesis)
- **FR-037**: System MUST track and report indexing performance metrics (files per second, embeddings per second)

### Key Entities

- **FileMetadata**: Represents a discovered file with attributes: file path, size, modification timestamp, file type, indexing status, last indexed timestamp
- **TextChunk**: Represents a segment of extracted text with attributes: chunk content, chunk index within file, start/end character positions, parent file reference
- **EmbeddingRecord**: Represents a vector embedding with attributes: embedding vector, associated text chunk reference, dimension size
- **QueryResult**: Represents a retrieved chunk with attributes: chunk content, similarity score, source file metadata, chunk position
- **IndexingJob**: Represents an indexing operation with attributes: job ID, start time, end time, status, files processed count, errors encountered
- **Configuration**: Represents system settings with attributes: directory paths, exclusion patterns, file type filters, embedding model name, vector store type, chunking parameters, LLM model name

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can successfully index a corpus of 10,000 text files in under 30 minutes on modern hardware
- **SC-002**: Users receive query responses (retrieval + synthesis) in under 10 seconds for 95% of queries
- **SC-003**: Incremental re-indexing of a corpus with 1% file changes completes in under 5% of the time required for full re-indexing
- **SC-004**: System successfully retrieves relevant content for queries with measurable accuracy (top-5 results include at least one relevant chunk for 80% of test queries)
- **SC-005**: Users can configure and start using the system with minimal setup (under 10 minutes from installation to first query)
- **SC-006**: System maintains stable memory usage during indexing and querying operations (no memory leaks over extended operation)
- **SC-007**: Indexing process gracefully handles and logs errors for up to 5% of problematic files without halting the entire operation

## Assumptions

- **A-001**: User has sufficient local storage for vector embeddings (estimated 1-2GB per 10,000 documents)
- **A-002**: User has local LLM and embedding models already available or is willing to download them
- **A-003**: User's hardware can run local embedding models and LLMs with acceptable performance (assumes modern CPU or GPU)
- **A-004**: Network-mounted storage (NAS) is accessible via standard filesystem mounting (SMB, NFS)
- **A-005**: Text content is primarily in English (embedding models may have reduced performance for other languages)
- **A-006**: User's personal corpus consists primarily of text-based files (Phase 1 scope)
- **A-007**: Reasonable defaults exist for chunking parameters (e.g., 512 tokens with 50 token overlap)
- **A-008**: Vector similarity search provides sufficient relevance ranking without advanced reranking

## Out of Scope (Phase 1)

- Image indexing and multimodal retrieval
- 3D model indexing
- Audio or video content processing
- Real-time incremental indexing (file watching)
- Multi-user support or authentication
- Cloud-based LLM or embedding services
- Advanced query features (filtering by date, file type, source)
- Web-based user interface (CLI/API only for Phase 1)
- Distributed indexing across multiple machines
