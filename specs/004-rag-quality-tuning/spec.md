# Feature Specification: RAG Quality Tuning & Hallucination Reduction

**Feature Branch**: `004-rag-quality-tuning`  
**Created**: 2026-02-16  
**Status**: Draft  
**Input**: User description: "Improve RAG answer quality and reduce hallucinations by tuning retrieval, chunking, prompting, model configuration, and adding evaluation diagnostics"

## Clarifications

### Session 2026-02-16

- Q: What should the default minimum similarity score threshold be (0.0–1.0 scale)? → A: 0.3 — filters clear noise while allowing moderate semantic matches through; users can tune upward.
- Q: What format should evaluation reports use? → A: JSON to stdout (structured, machine-readable, pipe/redirect friendly) with a human-readable summary table printed to stderr.
- Q: How should prompt template customization be expressed in configuration? → A: Named presets (e.g., strict, balanced, verbose) with an optional system prompt string override in config. Preset selection is also exposed as a CLI flag for quick switching without editing the config file.
- Q: What types of expected behavior checks should the evaluation harness support? → A: Three check types: (1) substring contains/excludes match on the answer text, (2) source file citation check (answer references a specific file), (3) "I don't know" / insufficient context detection.

## Problem Statement & Motivation

krag's end-to-end RAG pipeline is functional — indexing, embedding, retrieval, and LLM synthesis all work. However, the quality of answers is inconsistent:

1. **Poor context selection**: Retrieved chunks frequently contain irrelevant or low-signal content, diluting the useful context available to the LLM.
2. **Hallucination**: The LLM sometimes fabricates details or ignores the provided context, producing answers that are not grounded in the user's documents.
3. **No quality feedback loop**: There is no systematic way to measure answer quality, compare configurations, or iterate on retrieval/prompting/model settings.

These issues reduce user trust and make krag unreliable for its core purpose: answering questions accurately from a personal knowledge base.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Grounded, Accurate Answers (Priority: P1)

As a krag user, when I ask a question about content I have indexed, I want the answer to be based on the relevant documents in my knowledge base rather than fabricated by the model, so I can trust the response.

**Why this priority**: This is the core value proposition of krag. If answers are not grounded in the user's own documents, the tool is not useful regardless of any other capability.

**Independent Test**: Index a known set of documents, ask factual questions that can be answered from those documents, and verify that answers reference the correct information without fabrication. Ask questions whose answers are NOT in the documents and verify the system acknowledges insufficient context.

**Acceptance Scenarios**:

1. **Given** a set of indexed documents containing specific facts, **When** I ask a question answerable from those documents, **Then** the answer is accurate and based on the retrieved context.
2. **Given** a set of indexed documents that do NOT contain information about a topic, **When** I ask about that topic, **Then** the system clearly states it does not have enough context to answer.
3. **Given** a query with partially relevant context, **When** I ask the question, **Then** the answer uses only the relevant portions and does not fill gaps with fabricated details.

---

### User Story 2 - Relevant Context Retrieval (Priority: P1)

As a krag user, when I ask a question, I want the retrieved context chunks to be highly relevant to my question so the LLM has the best material to work with.

**Why this priority**: Retrieval quality is the upstream bottleneck — even a perfect LLM cannot produce good answers from irrelevant context. Tied with P1 because it directly enables Story 1.

**Independent Test**: Run queries against a known document set, inspect the retrieved chunks, and verify that the most relevant chunks appear in the top results with minimal noise.

**Acceptance Scenarios**:

1. **Given** an indexed knowledge base with documents on distinct topics, **When** I query about a specific topic, **Then** the top retrieved chunks are from the relevant document(s).
2. **Given** a large indexed corpus, **When** I query with a specific term or concept, **Then** chunks containing that term or closely related content rank highest.
3. **Given** overlapping documents on similar topics, **When** I query about a nuanced aspect, **Then** the most specifically relevant chunks are prioritized over broadly related ones.

---

### User Story 3 - Tunable Configuration (Priority: P2)

As a krag user, I want to adjust key retrieval and model settings through my configuration file so I can optimize answer quality for my specific documents and use case without changing code.

**Why this priority**: Different document sets and models perform differently — users need levers to tune behavior. This also enables the evaluation workflow (Story 4).

**Independent Test**: Modify chunking, retrieval, and LLM settings in the config file and verify the changes take effect on subsequent queries.

**Acceptance Scenarios**:

1. **Given** a krag configuration file, **When** I change the chunk size and overlap values, **Then** re-indexing produces chunks of the new size with the specified overlap.
2. **Given** a krag configuration file, **When** I change LLM temperature and max_tokens, **Then** subsequent queries use those settings for generation.
3. **Given** a krag configuration file, **When** I set a similarity score threshold, **Then** only chunks meeting or exceeding that threshold are included in the context.

---

### User Story 4 - Quality Evaluation Workflow (Priority: P2)

As a krag developer or power user, I want a simple way to run a set of test queries against a configuration and see how well the system performs, so I can measure the impact of tuning changes.

**Why this priority**: Without measurement, tuning is guesswork. This story enables a data-driven improvement loop — still high priority but depends on the quality improvements from Stories 1-3 to be meaningful.

**Independent Test**: Create a small set of evaluation queries with expected behaviors, run the evaluation, and review a summary report showing retrieval and answer quality signals.

**Acceptance Scenarios**:

1. **Given** a TOML/YAML file with test queries and expected behaviors, **When** I run the evaluation command, **Then** I see a summary of pass/fail results for each query.
2. **Given** two different krag configurations, **When** I run the evaluation suite against each, **Then** I can compare the summary reports to see which configuration scores better.
3. **Given** an evaluation run, **When** I review the output, **Then** I can see for each query: the retrieved chunks, the prompt sent to the LLM, and the generated answer.

---

### User Story 5 - Diagnostic Logging (Priority: P3)

As a krag developer, I want to see what context was retrieved and what prompt was sent to the LLM for any given query, so I can diagnose quality issues and iterate on improvements.

**Why this priority**: Essential for debugging and tuning but is a developer-facing tool rather than a direct user-facing quality improvement.

**Independent Test**: Run a query with verbose/debug logging enabled and verify the logs contain retrieved chunks, similarity scores, the full constructed prompt, and the raw LLM response.

**Acceptance Scenarios**:

1. **Given** debug logging is enabled, **When** I run a query, **Then** the log output includes each retrieved chunk with its similarity score and source file.
2. **Given** debug logging is enabled, **When** I run a query, **Then** the log output includes the complete prompt sent to the LLM.
3. **Given** a query that produces a poor-quality answer, **When** I review the debug log, **Then** I can identify whether the issue was poor retrieval, poor prompting, or poor generation.

---

### Edge Cases

- What happens when no chunks meet the similarity score threshold? The system returns an "insufficient context" response rather than forcing low-quality context into the prompt.
- What happens when the context window is too small for the retrieved chunks plus the prompt? The system prioritizes the highest-scoring chunks and gracefully truncates rather than failing.
- What happens when all retrieved chunks are from the same source file? The answer should still be accurate; source diversity is a quality signal but not a hard requirement.
- What happens when the user's query is extremely short (one word) or extremely long? Retrieval should still function reasonably; short queries may retrieve broader context, long queries should not exceed embedding model limits.
- What happens when evaluation queries reference documents that are no longer indexed? The evaluation report notes the missing context rather than silently failing.

## Requirements *(mandatory)*

### Functional Requirements

**Prompting & Generation**

- **FR-001**: System MUST use structured prompt templates that explicitly instruct the LLM to answer based solely on the provided context.
- **FR-002**: System MUST instruct the LLM to state "I don't know" or equivalent when the provided context is insufficient to answer the question.
- **FR-003**: System MUST include source attribution information in prompts so the LLM can reference which document(s) support its answer.
- **FR-004**: System MUST provide named prompt presets (e.g., "strict", "balanced", "verbose") selectable via configuration file or CLI flag. Users MAY also override the system prompt instruction string directly in the configuration file for full customization.

**Retrieval & Chunking**

- **FR-005**: System MUST support a configurable minimum similarity score threshold; chunks below this threshold are excluded from context.
- **FR-006**: System MUST allow configuration of chunk size and overlap values that take effect on re-indexing.
- **FR-007**: System MUST support configurable top-k retrieval through the existing configuration system.
- **FR-008**: System MUST log the similarity score for each retrieved chunk when debug logging is enabled.

**Model Configuration**

- **FR-009**: System MUST expose LLM temperature, top_p, max_tokens, and repeat_penalty as configurable parameters with documented defaults.
- **FR-010**: System MUST set conservative defaults for LLM parameters aimed at factual, grounded answers (low temperature, moderate top_p, reasonable repeat_penalty).

**Evaluation & Diagnostics**

- **FR-011**: System MUST provide a way to run a suite of test queries from a definition file and produce a summary of results.
- **FR-012**: System MUST log the complete prompt sent to the LLM when debug-level logging is enabled.
- **FR-013**: System MUST log all retrieved chunks with their scores and source metadata when debug-level logging is enabled.
- **FR-014**: Evaluation output MUST include, for each test query: the retrieved chunks, the final prompt, the generated answer, and pass/fail status against expected behaviors.
- **FR-015**: Evaluation MUST output structured JSON results to stdout and a human-readable summary table to stderr, enabling both scripted comparison and quick visual review.
- **FR-016**: Evaluation harness MUST support three behavior check types per test query: (1) answer substring contains/excludes match, (2) source file citation verification (answer references a specific source file), and (3) "I don't know" / insufficient context detection.

### Key Entities

- **Prompt Template**: A named preset (e.g., "strict", "balanced", "verbose") defining the system prompt, context formatting, instructions, and answer constraints used when building the LLM prompt. Selectable via config file or CLI flag. Users may also supply a custom system prompt string override in the config file. The default preset is optimized for grounded, factual answers.
- **Similarity Threshold**: A minimum cosine similarity score (0.0–1.0) that a retrieved chunk must meet to be included in the context. Configured globally with a default of 0.3.
- **Evaluation Query**: A test case definition containing a query string and one or more expected behavior checks. Supported check types: (1) substring contains/excludes — verify the answer includes or does not include specific text, (2) source citation — verify the answer references a specific source file, (3) insufficient context — verify the answer signals "I don't know" when appropriate. Stored in a TOML/YAML file.
- **Evaluation Report**: The output of running an evaluation suite — structured JSON to stdout containing a per-query breakdown of retrieved context, prompt, answer, and pass/fail against expected behaviors, plus an aggregate summary. A human-readable summary table is printed to stderr for quick visual review.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a curated set of 10+ evaluation queries, at least 80% of answers are grounded in the retrieved context (no fabricated claims).
- **SC-002**: On queries where the answer is not present in the indexed documents, the system responds with an "insufficient context" message at least 90% of the time.
- **SC-003**: On a curated set of evaluation queries, the top-3 retrieved chunks contain the most relevant content for at least 70% of queries (as judged by manual review).
- **SC-004**: A developer can run the complete evaluation workflow — configure, execute evaluation suite, compare reports — in under 5 minutes.
- **SC-005**: All key tuning parameters (chunk size, overlap, top-k, similarity threshold, temperature, top_p, max_tokens, repeat_penalty) are adjustable via configuration without code changes.
- **SC-006**: Debug logging provides sufficient information to diagnose whether a poor answer was caused by retrieval, prompting, or generation, for any given query.

## Assumptions

- The existing llama-cpp-python backend and Qdrant vector store are adequate for achieving quality goals; no infrastructure replacement is needed.
- The default embedding model (BAAI/bge-base-en-v1.5) provides strong retrieval quality for both natural language and code content. Model swap is supported but the current default is tuned for krag's use case.
- The user's document corpus is primarily text-based (code, markdown, text files) as currently supported.
- A curated evaluation set of 10–20 queries is sufficient for the pragmatic quality loop targeted by this evolution; large-scale benchmarking is out of scope.
- LLM parameter defaults (e.g., temperature 0.2, top_p 0.9, repeat_penalty 1.1) are reasonable starting points for factual grounding; exact values will be validated during implementation.
- The similarity score threshold default of 0.2 is appropriate for the BAAI/bge-base-en-v1.5 embedding model; may need adjustment if the embedding model changes.
- The existing TOML-based configuration system can accommodate the new parameters without structural changes.
- Prompt template customization via configuration file strings is sufficient; a full prompt-template-file system is out of scope for this evolution.

## Scope Boundaries

**In scope**:

- Prompt template refinement and configuration
- Retrieval parameter tuning (similarity threshold, top-k)
- Chunking parameter tuning (size, overlap) via existing config
- LLM parameter exposure and conservative defaults
- Lightweight evaluation harness with CLI entry point
- Debug logging of retrieval, prompt, and generation pipeline
- Documentation of tuning workflow

**Out of scope**:

- New user-facing CLI commands beyond a simple evaluation runner
- New frontends or UX redesigns
- Hybrid retrieval or re-ranking (deferred to a future evolution unless trivially achievable)
- Replacing the embedding model, LLM, or vector store
- Multi-hop reasoning or query decomposition
- Large-scale benchmarking infrastructure
- Automated prompt optimization or hyperparameter search
