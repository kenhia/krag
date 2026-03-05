<!--
  QueryPanel.svelte — Query input panel with SSE streaming
  
  Textarea for query text, Send button, optional mode selector slot,
  "Retrieve Only" toggle. Uses SSE streaming as primary transport,
  falls back to POST /query on SSE failure.
-->
<script lang="ts">
import type { Snippet } from "svelte";
import Button from "$lib/components/ui/Button.svelte";
import Select from "$lib/components/ui/Select.svelte";
import Slider from "$lib/components/ui/Slider.svelte";
import Spinner from "$lib/components/ui/Spinner.svelte";
import Toggle from "$lib/components/ui/Toggle.svelte";
import { postQuery, postRetrieve } from "$lib/services/kragd-client";
import { streamQuerySSE } from "$lib/services/streaming";
import { connection, getConnectionBaseUrl } from "$lib/state/connection.svelte";
import { addToast } from "$lib/state/notifications.svelte";
import {
	queryState,
	setCriticCutOff,
	setCriticEnabled,
	setIncludeDebug,
	setPreset,
	setRetrieveOnly,
	setShowSources,
	setTopK,
} from "$lib/state/query.svelte";
import { addEntry, transcript, updateEntry } from "$lib/state/transcript.svelte";
import type {
	PresetName,
	QueryRequest,
	QueryStreamEvent,
	RetrieveRequest,
	SourceChunk,
} from "$lib/types";
import { PRESET_OPTIONS } from "$lib/types";
import { handleKragdError, requireConnection } from "$lib/utils/errors";

interface Props {
	/** Selected mode from ModeSelector (null = default) */
	selectedMode?: string | null;
	/** Slot for mode selector component */
	modeSelector?: Snippet;
}

let { selectedMode = null, modeSelector }: Props = $props();

let queryText = $state("");
let loading = $state(false);
let queryAbort: AbortController | null = null;

const QUERY_TIMEOUT_MS = 60_000;

const isConnected = $derived(connection.status === "connected");
const canSend = $derived(isConnected && !loading && queryText.trim().length > 0);

function generateId(): string {
	return `entry-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

async function handleSend() {
	const text = queryText.trim();
	if (!text || loading) return;
	if (!requireConnection(connection.status)) return;

	loading = true;
	queryAbort = new AbortController();
	const timeoutId = setTimeout(() => {
		queryAbort?.abort();
		addToast("Query timed out after 60 seconds", "warning");
	}, QUERY_TIMEOUT_MS);
	const entryId = generateId();
	const startTime = Date.now();

	if (queryState.retrieve_only) {
		await handleRetrieve(text, entryId, startTime);
	} else {
		await handleQuery(text, entryId, startTime);
	}

	clearTimeout(timeoutId);
	queryAbort = null;
	loading = false;
}

async function handleQuery(text: string, entryId: string, startTime: number) {
	const req: QueryRequest = { query: text };
	if (selectedMode) req.mode = selectedMode;
	if (queryState.top_k !== null) req.top_k = queryState.top_k;
	if (queryState.preset !== null) req.preset = queryState.preset;
	if (queryState.include_debug) req.include_debug = true;

	// Add loading entry
	addEntry({
		id: entryId,
		timestamp: new Date(),
		type: "query",
		request: req,
		response: null,
		durationMs: null,
		error: null,
		loading: true,
	});

	// Try SSE streaming first
	let sseSuccess = false;
	try {
		await streamQuery(entryId, req, startTime);
		sseSuccess = true;
	} catch {
		// SSE failed — fall back to POST /query
	}

	if (!sseSuccess) {
		await fallbackQuery(entryId, req, startTime);
	}

	queryText = "";
}

async function streamQuery(entryId: string, req: QueryRequest, startTime: number): Promise<void> {
	const baseUrl = getConnectionBaseUrl();
	let accumulatedAnswer = "";
	let sources: SourceChunk[] = [];
	let streamError: string | null = null;

	await streamQuerySSE(
		baseUrl,
		req,
		(event: QueryStreamEvent) => {
			switch (event.type) {
				case "query:sources":
					sources = event.data.sources;
					updateEntry(entryId, {
						response: { answer: accumulatedAnswer, sources },
					});
					break;
				case "query:token":
					accumulatedAnswer += event.data.token;
					updateEntry(entryId, {
						response: { answer: accumulatedAnswer, sources },
					});
					break;
				case "query:done":
					updateEntry(entryId, {
						response: { answer: event.data.answer, sources: event.data.sources },
						loading: false,
						durationMs: Date.now() - startTime,
					});
					break;
				case "query:error":
					streamError = event.data.error;
					updateEntry(entryId, {
						error: event.data.error,
						loading: false,
						durationMs: Date.now() - startTime,
					});
					break;
			}
		},
		{ signal: queryAbort?.signal },
	);

	if (streamError) {
		addToast(`Query error: ${streamError}`, "error");
	}
}

async function fallbackQuery(entryId: string, req: QueryRequest, startTime: number) {
	try {
		const result = await postQuery(req);
		updateEntry(entryId, {
			response: result,
			loading: false,
			durationMs: Date.now() - startTime,
		});
	} catch (err) {
		const msg = handleKragdError(err);
		updateEntry(entryId, {
			error: msg,
			loading: false,
			durationMs: Date.now() - startTime,
		});
	}
}

async function handleRetrieve(text: string, entryId: string, startTime: number) {
	const req: RetrieveRequest = { query: text };
	if (selectedMode) req.mode = selectedMode;
	if (queryState.top_k !== null) req.top_k = queryState.top_k;

	addEntry({
		id: entryId,
		timestamp: new Date(),
		type: "retrieve",
		request: req,
		response: null,
		durationMs: null,
		error: null,
		loading: true,
	});

	try {
		const result = await postRetrieve(req);
		updateEntry(entryId, {
			response: result,
			loading: false,
			durationMs: Date.now() - startTime,
		});
	} catch (err) {
		const msg = handleKragdError(err);
		updateEntry(entryId, {
			error: msg,
			loading: false,
			durationMs: Date.now() - startTime,
		});
	}

	queryText = "";
}

function handleKeydown(event: KeyboardEvent) {
	// Ctrl/Cmd+Enter to send
	if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && canSend) {
		event.preventDefault();
		handleSend();
	}
}
</script>

<div class="query-panel">
	{#if modeSelector}
		<div class="mode-slot">
			{@render modeSelector()}
		</div>
	{/if}

	<div class="query-input-area">
		<textarea
			class="query-textarea"
			bind:value={queryText}
			placeholder={isConnected ? "Ask a question..." : "Connect to kragd first"}
			disabled={!isConnected}
			rows={3}
			onkeydown={handleKeydown}
		></textarea>

		<!-- Query Controls -->
		<div class="query-controls">
			<div class="control-row">
				<Slider
					value={queryState.top_k ?? 10}
					min={1}
					max={100}
					step={1}
					label="Top K"
					onchange={(v) => setTopK(v)}
				/>
			</div>
			<div class="control-row">
				<Select
					options={PRESET_OPTIONS}
					value={queryState.preset}
					placeholder="Server default"
					label="Preset"
					onchange={(v) => setPreset(v as PresetName)}
				/>
			</div>
			<div class="control-toggles">
				<Toggle
					checked={queryState.include_debug}
					onchange={(v) => setIncludeDebug(v)}
					label="Debug"
				/>
				<Toggle
					checked={queryState.show_sources}
					onchange={(v) => setShowSources(v)}
					label="Sources"
				/>
				<Toggle
					checked={queryState.retrieve_only}
					onchange={(v) => setRetrieveOnly(v)}
					label="Retrieve Only"
				/>
				<Toggle
					checked={queryState.critic_enabled}
					onchange={(v) => setCriticEnabled(v)}
					label="Critic"
				/>
			</div>
			{#if queryState.critic_enabled}
				<div class="control-row">
					<Slider
						value={queryState.critic_cut_off}
						min={0}
						max={1}
						step={0.05}
						label="Critic Cut-off"
						onchange={(v) => setCriticCutOff(v)}
					/>
				</div>
			{/if}
		</div>

		<div class="query-actions">
			<div class="send-area">
				{#if loading}
					<Spinner size="sm" />
				{/if}
				<Button
					label={queryState.retrieve_only ? "Retrieve" : "Send"}
					variant="primary"
					disabled={!canSend}
					{loading}
					onclick={handleSend}
				/>
			</div>
		</div>

		{#if !isConnected}
			<p class="connection-hint text-muted">Connect to kragd to start querying.</p>
		{/if}
	</div>
</div>

<style>
	.query-panel {
		display: flex;
		flex-direction: column;
		gap: var(--space-md, 16px);
		flex-shrink: 0;
	}

	.mode-slot {
		flex-shrink: 0;
	}

	.query-input-area {
		display: flex;
		flex-direction: column;
		gap: var(--space-sm, 8px);
	}

	.query-textarea {
		width: 100%;
		min-height: 80px;
		max-height: 200px;
		resize: vertical;
		padding: var(--space-sm, 8px) var(--space-md, 16px);
		background-color: var(--surface, #313244);
		color: var(--fg, #cdd6f4);
		border: 1px solid var(--border, #45475a);
		border-radius: var(--radius-md, 8px);
		font-family: inherit;
		font-size: 0.875rem;
		line-height: 1.5;
		transition: border-color var(--transition-fast, 150ms ease);
	}

	.query-textarea::placeholder {
		color: var(--fg-muted, #a6adc8);
		opacity: 0.6;
	}

	.query-textarea:focus {
		outline: none;
		border-color: var(--accent, #89b4fa);
	}

	.query-textarea:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.query-actions {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: var(--space-md, 16px);
	}

	.query-controls {
		display: flex;
		flex-direction: column;
		gap: var(--space-sm, 8px);
		padding: var(--space-sm, 8px);
		background-color: var(--surface, #313244);
		border: 1px solid var(--border, #45475a);
		border-radius: var(--radius-md, 8px);
	}

	.control-row {
		flex: 1;
	}

	.control-toggles {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-md, 16px);
	}

	.send-area {
		display: flex;
		align-items: center;
		gap: var(--space-sm, 8px);
	}

	.connection-hint {
		font-size: 0.8rem;
	}

	.text-muted {
		color: var(--fg-muted, #a6adc8);
	}
</style>
