<!--
  IndexPanel.svelte — Index management panel

  Full/incremental radio, Start Indexing button, status badge,
  progress counters grid, error list. SSE streaming as primary
  transport, polling fallback. Adds transcript entry on completion.
-->
<script lang="ts">
	import { onMount } from "svelte";
	import Button from "$lib/components/ui/Button.svelte";
	import Spinner from "$lib/components/ui/Spinner.svelte";
	import {
		indexJob,
		resetJob,
		applyStatus,
	} from "$lib/state/indexJob.svelte";
	import { connection, getConnectionBaseUrl } from "$lib/state/connection.svelte";
	import { addEntry, updateEntry } from "$lib/state/transcript.svelte";
	import { addToast } from "$lib/state/notifications.svelte";
	import { triggerIndex, getIndexStatus } from "$lib/services/kragd-client";
	import { streamIndexSSE } from "$lib/services/streaming";
	import { handleKragdError, requireConnection } from "$lib/utils/errors";
	import type { IndexMode, IndexStreamEvent, IndexResponse } from "$lib/types";
	import { formatDuration } from "$lib/utils/format";

	let indexMode = $state<IndexMode>("incremental");
	let starting = $state(false);
	let transcriptEntryId = $state<string | null>(null);
	let sseAbort: AbortController | null = null;
	let pollTimer: ReturnType<typeof setInterval> | null = null;

	const POLL_INTERVAL = 2000;

	const isConnected = $derived(connection.status === "connected");
	const canStart = $derived(isConnected && !indexJob.running && !starting);

	const statusLabel = $derived.by(() => {
		if (starting) return "Starting…";
		if (indexJob.running) return "Running";
		if (indexJob.status === "completed") return "Completed";
		if (indexJob.status === "failed") return "Failed";
		return "Idle";
	});

	const statusClass = $derived.by(() => {
		if (indexJob.running || starting) return "status-running";
		if (indexJob.status === "completed") return "status-completed";
		if (indexJob.status === "failed") return "status-failed";
		return "status-idle";
	});

	function generateId(): string {
		return `entry-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
	}

	async function handleStart() {
		if (!canStart) return;
		if (!requireConnection(connection.status)) return;

		starting = true;
		resetJob();

		const entryId = generateId();
		transcriptEntryId = entryId;
		const startTime = Date.now();

		// Add loading transcript entry
		addEntry({
			id: entryId,
			timestamp: new Date(),
			type: "index",
			request: { mode: indexMode },
			response: null,
			durationMs: null,
			error: null,
			loading: true,
		});

		try {
			const res = await triggerIndex({ mode: indexMode });
			indexJob.running = true;
			applyStatus(res);
			starting = false;

			// Try SSE streaming first, fall back to polling
			const sseOk = await trySSEStream(entryId, startTime);
			if (!sseOk) {
				startPolling(entryId, startTime);
			}
		} catch (err) {
			starting = false;
			const msg = handleKragdError(err);
			indexJob.error = msg;
			updateEntry(entryId, {
				error: msg,
				loading: false,
				durationMs: Date.now() - startTime,
			});
		}
	}

	// ─── SSE Streaming ──────────────────────────────────────────

	async function trySSEStream(entryId: string, startTime: number): Promise<boolean> {
		sseAbort = new AbortController();
		try {
			await streamIndexSSE(
				getConnectionBaseUrl(),
				(event: IndexStreamEvent) => handleSSEEvent(event, entryId, startTime),
				{ signal: sseAbort.signal },
			);
			return true;
		} catch {
			return false;
		}
	}

	function handleSSEEvent(event: IndexStreamEvent, entryId: string, startTime: number) {
		switch (event.type) {
			case "index:progress": {
				const d = event.data;
				indexJob.filesScanned = d.total;
				indexJob.filesProcessed = d.current;
				indexJob.status = "running";
				break;
			}
			case "index:complete": {
				const d = event.data;
				indexJob.status = "completed";
				indexJob.running = false;
				indexJob.filesProcessed = d.files_processed;
				indexJob.durationSeconds = d.duration_seconds;
				finalizeEntry(entryId, startTime, null);
				cleanupSSE();
				addToast("Indexing completed", "success");
				break;
			}
			case "index:error": {
				const d = event.data;
				indexJob.status = "failed";
				indexJob.running = false;
				indexJob.error = d.error;
				finalizeEntry(entryId, startTime, d.error);
				cleanupSSE();
				addToast(`Indexing failed: ${d.error}`, "error");
				break;
			}
			case "index:idle": {
				// No active job — stop listening
				cleanupSSE();
				break;
			}
		}
	}

	function cleanupSSE() {
		if (sseAbort) {
			sseAbort.abort();
			sseAbort = null;
		}
	}

	// ─── Polling Fallback ───────────────────────────────────────

	function startPolling(entryId: string, startTime: number) {
		stopPolling();
		pollTimer = setInterval(async () => {
			await pollStatus(entryId, startTime);
		}, POLL_INTERVAL);
	}

	function stopPolling() {
		if (pollTimer !== null) {
			clearInterval(pollTimer);
			pollTimer = null;
		}
	}

	async function pollStatus(entryId: string, startTime: number) {
		try {
			const statuses = await getIndexStatus();
			if (statuses.length > 0) {
				const latest = statuses[0];
				applyStatus(latest);

				if (latest.status === "completed" || latest.status === "failed") {
					stopPolling();
					const errMsg = latest.status === "failed" ? "Indexing failed" : null;
					finalizeEntry(entryId, startTime, errMsg);
					addToast(
						latest.status === "completed" ? "Indexing completed" : "Indexing failed",
						latest.status === "completed" ? "success" : "error",
					);
				}
			}
		} catch {
			// Polling error — keep trying
		}
	}

	// ─── Transcript ─────────────────────────────────────────────

	function finalizeEntry(entryId: string, startTime: number, errorMsg: string | null) {
		const response: Record<string, unknown> = {
			status: indexJob.status,
			mode: indexJob.mode,
			files_scanned: indexJob.filesScanned,
			files_processed: indexJob.filesProcessed,
			files_errored: indexJob.filesErrored,
			chunks_created: indexJob.chunksCreated,
			vectors_stored: indexJob.vectorsStored,
			duration_seconds: indexJob.durationSeconds,
		};

		updateEntry(entryId, {
			response,
			error: errorMsg,
			loading: false,
			durationMs: Date.now() - startTime,
		});
	}

	// Cleanup on component destroy
	onMount(() => {
		return () => {
			stopPolling();
			cleanupSSE();
		};
	});
</script>

<div class="index-panel">
	<div class="index-header">
		<h2>Indexing</h2>
		<span class="status-badge {statusClass}">
			{#if indexJob.running || starting}
				<Spinner size="sm" />
			{/if}
			{statusLabel}
		</span>
	</div>

	<!-- Controls -->
	<div class="index-controls">
		<fieldset class="mode-fieldset" disabled={!canStart}>
			<legend class="sr-only">Index Mode</legend>
			<label class="radio-label">
				<input type="radio" bind:group={indexMode} value="incremental" />
				<span>Incremental</span>
			</label>
			<label class="radio-label">
				<input type="radio" bind:group={indexMode} value="full" />
				<span>Full</span>
			</label>
		</fieldset>

		<Button
			label={starting ? "Starting…" : "Start Indexing"}
			variant="primary"
			disabled={!canStart}
			loading={starting}
			onclick={handleStart}
		/>
	</div>

	<!-- Progress -->
	{#if indexJob.running || indexJob.status}
		<div class="progress-grid">
			<div class="stat">
				<span class="stat-label">Scanned</span>
				<span class="stat-value">{indexJob.filesScanned}</span>
			</div>
			<div class="stat">
				<span class="stat-label">Processed</span>
				<span class="stat-value">{indexJob.filesProcessed}</span>
			</div>
			<div class="stat">
				<span class="stat-label">Skipped</span>
				<span class="stat-value">{indexJob.filesSkippedUnchanged + indexJob.filesSkippedOther}</span>
			</div>
			<div class="stat">
				<span class="stat-label">Errors</span>
				<span class="stat-value" class:error-count={indexJob.filesErrored > 0}>
					{indexJob.filesErrored}
				</span>
			</div>
			<div class="stat">
				<span class="stat-label">Chunks</span>
				<span class="stat-value">{indexJob.chunksCreated}</span>
			</div>
			<div class="stat">
				<span class="stat-label">Vectors</span>
				<span class="stat-value">{indexJob.vectorsStored}</span>
			</div>
			{#if indexJob.durationSeconds != null}
				<div class="stat">
					<span class="stat-label">Duration</span>
					<span class="stat-value">{formatDuration(indexJob.durationSeconds * 1000)}</span>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Errors list -->
	{#if indexJob.errors.length > 0}
		<div class="error-section">
			<h3>Errors ({indexJob.errors.length})</h3>
			<ul class="error-list">
				{#each indexJob.errors as err}
					<li class="error-item">
						<span class="error-path">{err.file_path}</span>
						<span class="error-type">{err.error_type}</span>
						<span class="error-msg">{err.error_message}</span>
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	<!-- General error message -->
	{#if indexJob.error && !indexJob.running}
		<div class="general-error">
			<span class="error-icon">✕</span>
			<span>{indexJob.error}</span>
		</div>
	{/if}

	{#if !isConnected}
		<p class="text-muted">Connect to kragd to manage indexing.</p>
	{/if}
</div>

<style>
	.index-panel {
		display: flex;
		flex-direction: column;
		gap: var(--space-lg, 24px);
		height: 100%;
	}

	.index-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.index-header h2 {
		font-size: 1.25rem;
		font-weight: 600;
		margin: 0;
	}

	.status-badge {
		display: flex;
		align-items: center;
		gap: var(--space-sm, 8px);
		font-size: 0.8rem;
		font-weight: 600;
		padding: var(--space-xs, 4px) var(--space-sm, 8px);
		border-radius: var(--radius-sm, 4px);
	}

	.status-idle {
		color: var(--fg-muted, #a6adc8);
	}

	.status-running {
		color: var(--accent, #89b4fa);
	}

	.status-completed {
		color: var(--success, #a6e3a1);
	}

	.status-failed {
		color: var(--error, #f38ba8);
	}

	.index-controls {
		display: flex;
		align-items: center;
		gap: var(--space-lg, 24px);
	}

	.mode-fieldset {
		display: flex;
		align-items: center;
		gap: var(--space-md, 16px);
		border: none;
		padding: 0;
		margin: 0;
	}

	.radio-label {
		display: flex;
		align-items: center;
		gap: var(--space-xs, 4px);
		font-size: 0.85rem;
		cursor: pointer;
		color: var(--fg, #cdd6f4);
	}

	.radio-label input[type="radio"] {
		accent-color: var(--accent, #89b4fa);
		cursor: pointer;
	}

	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		white-space: nowrap;
		border: 0;
	}

	.progress-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
		gap: var(--space-sm, 8px);
	}

	.stat {
		display: flex;
		flex-direction: column;
		padding: var(--space-sm, 8px) var(--space-md, 16px);
		background-color: var(--surface, #313244);
		border: 1px solid var(--border, #45475a);
		border-radius: var(--radius-sm, 4px);
	}

	.stat-label {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--fg-muted, #a6adc8);
	}

	.stat-value {
		font-size: 1.1rem;
		font-weight: 600;
		font-family: var(--font-mono, monospace);
	}

	.error-count {
		color: var(--error, #f38ba8);
	}

	.error-section {
		display: flex;
		flex-direction: column;
		gap: var(--space-sm, 8px);
	}

	.error-section h3 {
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--error, #f38ba8);
		margin: 0;
	}

	.error-list {
		list-style: none;
		padding: 0;
		margin: 0;
		max-height: 200px;
		overflow-y: auto;
	}

	.error-item {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-sm, 8px);
		padding: var(--space-xs, 4px) var(--space-sm, 8px);
		border-bottom: 1px solid var(--border, #45475a);
		font-size: 0.8rem;
	}

	.error-path {
		font-family: var(--font-mono, monospace);
		color: var(--accent, #89b4fa);
		word-break: break-all;
	}

	.error-type {
		font-size: 0.7rem;
		text-transform: uppercase;
		color: var(--fg-muted, #a6adc8);
		padding: 1px 4px;
		background-color: var(--surface-hover, #3b3d52);
		border-radius: var(--radius-sm, 4px);
	}

	.error-msg {
		color: var(--error, #f38ba8);
	}

	.general-error {
		display: flex;
		align-items: flex-start;
		gap: var(--space-sm, 8px);
		color: var(--error, #f38ba8);
		font-size: 0.85rem;
		padding: var(--space-sm, 8px);
		background-color: var(--error-bg, rgba(243, 139, 168, 0.1));
		border-radius: var(--radius-sm, 4px);
	}

	.error-icon {
		font-weight: 700;
		flex-shrink: 0;
	}

	.text-muted {
		color: var(--fg-muted, #a6adc8);
		font-size: 0.85rem;
	}
</style>
