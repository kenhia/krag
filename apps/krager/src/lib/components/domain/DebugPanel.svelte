<!--
  DebugPanel.svelte — Debug tools for power users
  
  Two-tab interface:
  - Debug Query: Full query with metadata (POST /debug/query)
  - Qdrant Search: Raw vector search (POST /debug/qdrant)
  
  Results rendered via DebugMetadataView + SourceList.
  Wires results to transcript with type: 'debug'.
-->
<script lang="ts">
import DebugMetadataView from "$lib/components/domain/DebugMetadataView.svelte";
import SourceList from "$lib/components/domain/SourceList.svelte";
import Button from "$lib/components/ui/Button.svelte";
import Spinner from "$lib/components/ui/Spinner.svelte";
import { postDebugQdrant, postDebugQuery } from "$lib/services/kragd-client";
import { connection } from "$lib/state/connection.svelte";
import { addEntry, updateEntry } from "$lib/state/transcript.svelte";
import type {
	DebugMetadata,
	DebugQueryRequest,
	DebugQueryResponse,
	QdrantFilters,
	QdrantSearchRequest,
	QdrantSearchResponse,
	SourceChunk,
	TranscriptEntry,
} from "$lib/types";
import { handleKragdError, requireConnection } from "$lib/utils/errors";

type DebugTab = "query" | "qdrant";
let activeTab = $state<DebugTab>("query");

// Debug Query state
let dqQuery = $state("");
let dqTopK = $state("");
let dqPreset = $state("");
let dqMode = $state("");
let dqLoading = $state(false);
let dqResult = $state<DebugQueryResponse | null>(null);

// Qdrant Search state
let qsQuery = $state("");
let qsVectorSpace = $state("");
let qsTopK = $state("10");
let qsScoreThreshold = $state("");
let qsFileType = $state("");
let qsPathContains = $state("");
let qsLoading = $state(false);
let qsResult = $state<QdrantSearchResponse | null>(null);

async function handleDebugQuery() {
	if (!requireConnection(connection.status)) return;
	if (!dqQuery.trim()) return;

	dqLoading = true;
	dqResult = null;

	const req: DebugQueryRequest = { query: dqQuery.trim() };
	if (dqTopK.trim()) req.top_k = Number.parseInt(dqTopK, 10);
	if (dqPreset.trim()) req.preset = dqPreset.trim();
	if (dqMode.trim()) req.mode = dqMode.trim();

	const entryId = crypto.randomUUID();
	addEntry({
		id: entryId,
		timestamp: new Date(),
		type: "debug",
		request: req,
		response: null,
		durationMs: null,
		error: null,
		loading: true,
	});
	const startTime = Date.now();

	try {
		const result = await postDebugQuery(req);
		dqResult = result;
		updateEntry(entryId, {
			response: result,
			durationMs: Date.now() - startTime,
			loading: false,
		});
	} catch (e) {
		const msg = handleKragdError(e);
		updateEntry(entryId, {
			error: msg,
			durationMs: Date.now() - startTime,
			loading: false,
		});
	} finally {
		dqLoading = false;
	}
}

async function handleQdrantSearch() {
	if (!requireConnection(connection.status)) return;
	if (!qsQuery.trim()) return;

	qsLoading = true;
	qsResult = null;

	const req: QdrantSearchRequest = { query: qsQuery.trim() };
	if (qsVectorSpace.trim()) req.vector_space = qsVectorSpace.trim();
	if (qsTopK.trim()) req.top_k = Number.parseInt(qsTopK, 10);
	if (qsScoreThreshold.trim()) req.score_threshold = Number.parseFloat(qsScoreThreshold);
	if (qsFileType.trim() || qsPathContains.trim()) {
		const filters: QdrantFilters = {};
		if (qsFileType.trim()) filters.file_type = qsFileType.trim();
		if (qsPathContains.trim()) filters.file_path_contains = qsPathContains.trim();
		req.filters = filters;
	}

	const entryId = crypto.randomUUID();
	addEntry({
		id: entryId,
		timestamp: new Date(),
		type: "debug",
		request: req,
		response: null,
		durationMs: null,
		error: null,
		loading: true,
	});
	const startTime = Date.now();

	try {
		const result = await postDebugQdrant(req);
		qsResult = result;
		updateEntry(entryId, {
			response: result,
			durationMs: Date.now() - startTime,
			loading: false,
		});
	} catch (e) {
		const msg = handleKragdError(e);
		updateEntry(entryId, {
			error: msg,
			durationMs: Date.now() - startTime,
			loading: false,
		});
	} finally {
		qsLoading = false;
	}
}

function handleQueryKeydown(e: KeyboardEvent) {
	if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
		e.preventDefault();
		handleDebugQuery();
	}
}

function handleQdrantKeydown(e: KeyboardEvent) {
	if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
		e.preventDefault();
		handleQdrantSearch();
	}
}

// Convert QdrantSearchResult[] to SourceChunk[] for SourceList rendering
function qdrantResultsToChunks(result: QdrantSearchResponse): SourceChunk[] {
	return result.results.map((r, i) => ({
		chunk_id: r.chunk_id,
		file_path: r.file_path,
		score: r.score,
		rank: i + 1,
		chunk_content: r.chunk_content,
		file_type: r.file_type,
		start_line: r.start_line ?? null,
		end_line: r.end_line ?? null,
	}));
}
</script>

<div class="debug-panel">
	<div class="debug-header">
		<h2>Debug Tools</h2>
	</div>

	<!-- Tab bar -->
	<div class="tab-bar" role="tablist">
		<button
			class="tab"
			class:active={activeTab === "query"}
			onclick={() => (activeTab = "query")}
			role="tab"
			aria-selected={activeTab === "query"}
		>
			Debug Query
		</button>
		<button
			class="tab"
			class:active={activeTab === "qdrant"}
			onclick={() => (activeTab = "qdrant")}
			role="tab"
			aria-selected={activeTab === "qdrant"}
		>
			Qdrant Search
		</button>
	</div>

	<div class="tab-content">
		<!-- Debug Query Tab -->
		{#if activeTab === "query"}
			<div class="form-area">
				<textarea
					class="query-input"
					placeholder="Enter debug query..."
					bind:value={dqQuery}
					onkeydown={handleQueryKeydown}
					rows="3"
				></textarea>
				<div class="form-fields">
					<label class="field">
						<span class="field-label">Top K</span>
						<input type="number" class="field-input" bind:value={dqTopK} placeholder="10" min="1" max="100" />
					</label>
					<label class="field">
						<span class="field-label">Preset</span>
						<input type="text" class="field-input" bind:value={dqPreset} placeholder="default" />
					</label>
					<label class="field">
						<span class="field-label">Mode</span>
						<input type="text" class="field-input" bind:value={dqMode} placeholder="(default)" />
					</label>
				</div>
				<div class="form-actions">
					<Button
						label={dqLoading ? "Querying..." : "Send Debug Query"}
						variant="primary"
						onclick={handleDebugQuery}
						disabled={!dqQuery.trim() || dqLoading}
						loading={dqLoading}
					/>
				</div>
			</div>

			{#if dqLoading}
				<div class="loading-area">
					<Spinner size="lg" />
					<span class="text-muted">Running debug query...</span>
				</div>
			{:else if dqResult}
				<div class="results-area">
					{#if dqResult.debug}
						<DebugMetadataView metadata={dqResult.debug} />
					{/if}
					{#if dqResult.answer}
						<div class="answer-section">
							<h4>Answer</h4>
							<pre class="answer-text">{dqResult.answer}</pre>
						</div>
					{/if}
					{#if dqResult.sources.length > 0}
						<div class="sources-section">
							<h4>Sources ({dqResult.sources.length})</h4>
							<SourceList sources={dqResult.sources} />
						</div>
					{/if}
				</div>
			{/if}

		<!-- Qdrant Search Tab -->
		{:else if activeTab === "qdrant"}
			<div class="form-area">
				<textarea
					class="query-input"
					placeholder="Enter vector search query..."
					bind:value={qsQuery}
					onkeydown={handleQdrantKeydown}
					rows="3"
				></textarea>
				<div class="form-fields">
					<label class="field">
						<span class="field-label">Vector Space</span>
						<input type="text" class="field-input" bind:value={qsVectorSpace} placeholder="(all spaces)" />
					</label>
					<label class="field">
						<span class="field-label">Top K</span>
						<input type="number" class="field-input" bind:value={qsTopK} placeholder="10" min="1" max="1000" />
					</label>
					<label class="field">
						<span class="field-label">Score Threshold</span>
						<input type="number" class="field-input" bind:value={qsScoreThreshold} placeholder="0.0" min="0" max="1" step="0.05" />
					</label>
					<label class="field">
						<span class="field-label">File Type</span>
						<input type="text" class="field-input" bind:value={qsFileType} placeholder="python, typescript..." />
					</label>
					<label class="field">
						<span class="field-label">Path Contains</span>
						<input type="text" class="field-input" bind:value={qsPathContains} placeholder="src/" />
					</label>
				</div>
				<div class="form-actions">
					<Button
						label={qsLoading ? "Searching..." : "Search Qdrant"}
						variant="primary"
						onclick={handleQdrantSearch}
						disabled={!qsQuery.trim() || qsLoading}
						loading={qsLoading}
					/>
				</div>
			</div>

			{#if qsLoading}
				<div class="loading-area">
					<Spinner size="lg" />
					<span class="text-muted">Searching vectors...</span>
				</div>
			{:else if qsResult}
				<div class="results-area">
					<div class="results-summary">
						<span class="mono">{qsResult.total_results} result{qsResult.total_results !== 1 ? "s" : ""}</span>
						{#if qsResult.vector_space}
							<span class="text-muted">in <span class="mono">{qsResult.vector_space}</span></span>
						{/if}
					</div>
					{#if qsResult.results.length > 0}
						<SourceList sources={qdrantResultsToChunks(qsResult)} />
					{:else}
						<p class="text-muted">No results found.</p>
					{/if}
				</div>
			{/if}
		{/if}
	</div>
</div>

<style>
	.debug-panel {
		display: flex;
		flex-direction: column;
		height: 100%;
		gap: var(--space-md, 16px);
		overflow: hidden;
	}

	.debug-header h2 {
		font-size: 1.25rem;
		font-weight: 600;
		margin: 0;
	}

	.tab-bar {
		display: flex;
		gap: var(--space-xs, 4px);
		border-bottom: 1px solid var(--border, #45475a);
		flex-shrink: 0;
	}

	.tab {
		background: none;
		border: none;
		padding: var(--space-sm, 8px) var(--space-md, 16px);
		font-size: 0.85rem;
		font-weight: 500;
		color: var(--fg-muted, #a6adc8);
		cursor: pointer;
		border-bottom: 2px solid transparent;
		transition: color var(--transition-fast, 150ms ease), border-color var(--transition-fast, 150ms ease);
	}

	.tab:hover {
		color: var(--fg, #cdd6f4);
	}

	.tab.active {
		color: var(--accent, #89b4fa);
		border-bottom-color: var(--accent, #89b4fa);
	}

	.tab-content {
		flex: 1;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: var(--space-lg, 24px);
	}

	.form-area {
		display: flex;
		flex-direction: column;
		gap: var(--space-sm, 8px);
	}

	.query-input {
		width: 100%;
		padding: var(--space-sm, 8px) var(--space-md, 16px);
		background-color: var(--surface, #313244);
		color: var(--fg, #cdd6f4);
		border: 1px solid var(--border, #45475a);
		border-radius: var(--radius-md, 8px);
		font-family: var(--font-mono, monospace);
		font-size: 0.85rem;
		resize: vertical;
		line-height: 1.5;
	}

	.query-input::placeholder {
		color: var(--fg-muted, #a6adc8);
	}

	.query-input:focus {
		outline: none;
		border-color: var(--accent, #89b4fa);
	}

	.form-fields {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-sm, 8px);
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 2px;
		flex: 1;
		min-width: 120px;
	}

	.field-label {
		font-size: 0.7rem;
		font-weight: 600;
		color: var(--fg-muted, #a6adc8);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.field-input {
		padding: var(--space-xs, 4px) var(--space-sm, 8px);
		background-color: var(--surface, #313244);
		color: var(--fg, #cdd6f4);
		border: 1px solid var(--border, #45475a);
		border-radius: var(--radius-sm, 4px);
		font-size: 0.8rem;
		font-family: var(--font-mono, monospace);
	}

	.field-input::placeholder {
		color: var(--fg-muted, #a6adc8);
		opacity: 0.6;
	}

	.field-input:focus {
		outline: none;
		border-color: var(--accent, #89b4fa);
	}

	.form-actions {
		display: flex;
		justify-content: flex-end;
	}

	.loading-area {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: var(--space-md, 16px);
		padding: var(--space-xl, 32px);
	}

	.results-area {
		display: flex;
		flex-direction: column;
		gap: var(--space-md, 16px);
	}

	.results-summary {
		display: flex;
		align-items: center;
		gap: var(--space-sm, 8px);
		font-size: 0.85rem;
	}

	.answer-section,
	.sources-section {
		display: flex;
		flex-direction: column;
		gap: var(--space-sm, 8px);
	}

	.answer-section h4,
	.sources-section h4 {
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--fg-muted, #a6adc8);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin: 0;
	}

	.answer-text {
		margin: 0;
		padding: var(--space-sm, 8px) var(--space-md, 16px);
		font-family: inherit;
		font-size: 0.875rem;
		line-height: 1.6;
		white-space: pre-wrap;
		word-wrap: break-word;
		background-color: var(--bg, #1e1e2e);
		border-radius: var(--radius-sm, 4px);
		border: 1px solid var(--border-subtle, #363849);
	}

	.mono {
		font-family: var(--font-mono, monospace);
	}

	.text-muted {
		color: var(--fg-muted, #a6adc8);
		font-size: 0.85rem;
	}
</style>
