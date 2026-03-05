<!--
  SystemStatus.svelte — System status panel
  
  Displays ServiceStatus data: version, uptime, LLM slots, embedding models,
  collection stats, VRAM usage, and lexicon status.
  Fetches on mount and on manual refresh.
-->
<script lang="ts">
import { onMount } from "svelte";
import Button from "$lib/components/ui/Button.svelte";
import Spinner from "$lib/components/ui/Spinner.svelte";
import { getStatus, refreshLexicon } from "$lib/services/kragd-client";
import { addToast } from "$lib/state/notifications.svelte";
import type { ServiceStatus } from "$lib/types";
import { handleKragdError } from "$lib/utils/errors";
import { formatUptime } from "$lib/utils/format";

let status = $state<ServiceStatus | null>(null);
let loading = $state(false);
let error = $state<string | null>(null);

async function fetchStatus() {
	loading = true;
	error = null;
	try {
		status = await getStatus();
	} catch (e) {
		error = handleKragdError(e);
	} finally {
		loading = false;
	}
}

onMount(() => {
	fetchStatus();
});

const vramPercent = $derived(
	status?.vram ? Math.round((status.vram.used_mb / status.vram.total_mb) * 100) : 0,
);

let refreshingLexicon = $state(false);

async function handleRefreshLexicon() {
	refreshingLexicon = true;
	try {
		const result = await refreshLexicon();
		addToast(`Lexicon refreshed: ${result.entries.toLocaleString()} entries`, "success");
		// Re-fetch status to reflect updated lexicon counts
		await fetchStatus();
	} catch (e) {
		handleKragdError(e);
	} finally {
		refreshingLexicon = false;
	}
}
</script>

<div class="system-status">
	<div class="status-header">
		<h2>System Status</h2>
		<Button label="Refresh" variant="secondary" onclick={fetchStatus} loading={loading} />
	</div>

	{#if loading && !status}
		<div class="loading-container">
			<Spinner size="lg" />
			<p class="text-muted">Loading system status...</p>
		</div>
	{:else if error && !status}
		<div class="error-container">
			<p class="error-text">{error}</p>
			<Button label="Retry" variant="primary" onclick={fetchStatus} />
		</div>
	{:else if status}
		<div class="status-grid">
			<!-- Version & Uptime -->
			<section class="status-card">
				<h3>Server</h3>
				<dl class="info-list">
					<dt>Version</dt>
					<dd>{status.version}</dd>
					<dt>Uptime</dt>
					<dd>{formatUptime(status.uptime_seconds)}</dd>
				</dl>
			</section>

			<!-- LLM Slots -->
			<section class="status-card">
				<h3>LLM Slots</h3>
				{#each Object.entries(status.llm) as [slotName, slot]}
					<div class="llm-slot">
						<span class="slot-name">{slotName}</span>
						<span class="slot-status" class:slot-loaded={slot.loaded} class:slot-unloaded={!slot.loaded}>
							{slot.loaded ? "●" : "○"} {slot.loaded ? "Loaded" : "Not loaded"}
						</span>
						{#if slot.model}
							<span class="slot-model">{slot.model}</span>
						{/if}
					</div>
				{/each}
			</section>

			<!-- Embedding Models -->
			<section class="status-card">
				<h3>Embedding Models</h3>
				{#if status.embedding_models.length > 0}
					<ul class="model-list">
						{#each status.embedding_models as model}
							<li>{model}</li>
						{/each}
					</ul>
				{:else}
					<p class="text-muted">No embedding models loaded</p>
				{/if}
			</section>

			<!-- Collections -->
			<section class="status-card">
				<h3>Collections</h3>
				{#if Object.keys(status.collections).length > 0}
					<table class="stats-table">
						<thead>
							<tr>
								<th>Collection</th>
								<th>Vectors</th>
								<th>Status</th>
							</tr>
						</thead>
						<tbody>
							{#each Object.entries(status.collections) as [name, col]}
								<tr>
									<td>{name}</td>
									<td class="num">{col.vectors_count.toLocaleString()}</td>
									<td>
										<span class="collection-status" class:status-ok={col.status === "green"}>{col.status}</span>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{:else}
					<p class="text-muted">No collections</p>
				{/if}
			</section>

			<!-- VRAM -->
			{#if status.vram}
				<section class="status-card">
					<h3>GPU Memory</h3>
					<div class="vram-bar-container">
						<div class="vram-bar">
							<div
								class="vram-fill"
								class:vram-high={vramPercent > 85}
								class:vram-mid={vramPercent > 50 && vramPercent <= 85}
								style:width="{vramPercent}%"
							></div>
						</div>
						<span class="vram-label">
							{status.vram.used_mb.toLocaleString()} / {status.vram.total_mb.toLocaleString()} MB
							({vramPercent}%)
						</span>
					</div>
				</section>
			{/if}

			<!-- Lexicon -->
			<section class="status-card">
				<div class="card-header">
					<h3>Lexicon</h3>
					<Button label={refreshingLexicon ? "Refreshing..." : "Refresh"} variant="secondary" onclick={handleRefreshLexicon} loading={refreshingLexicon} />
				</div>
				<dl class="info-list">
					<dt>Status</dt>
					<dd>{status.lexicon_loaded ? "Loaded" : "Not loaded"}</dd>
					<dt>Entries</dt>
					<dd>{status.lexicon_entry_count.toLocaleString()}</dd>
				</dl>
			</section>
		</div>
	{/if}
</div>

<style>
	.system-status {
		display: flex;
		flex-direction: column;
		gap: var(--space-lg, 24px);
		height: 100%;
	}

	.status-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.status-header h2 {
		font-size: 1.25rem;
		font-weight: 600;
		margin: 0;
	}

	.loading-container,
	.error-container {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: var(--space-md, 16px);
		flex: 1;
	}

	.error-text {
		color: var(--error, #f38ba8);
	}

	.status-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
		gap: var(--space-md, 16px);
	}

	.status-card {
		background-color: var(--surface, #313244);
		border: 1px solid var(--border, #45475a);
		border-radius: var(--radius-md, 8px);
		padding: var(--space-md, 16px);
	}

	.status-card h3 {
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--fg-muted, #a6adc8);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin: 0 0 var(--space-sm, 8px);
	}

	.card-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: var(--space-sm, 8px);
	}

	.card-header h3 {
		margin-bottom: 0;
	}

	.info-list {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: var(--space-xs, 4px) var(--space-md, 16px);
		margin: 0;
	}

	.info-list dt {
		font-size: 0.8rem;
		color: var(--fg-muted, #a6adc8);
	}

	.info-list dd {
		font-size: 0.85rem;
		font-family: var(--font-mono, monospace);
		margin: 0;
	}

	/* LLM Slots */
	.llm-slot {
		display: flex;
		align-items: center;
		gap: var(--space-sm, 8px);
		padding: var(--space-xs, 4px) 0;
		font-size: 0.85rem;
	}

	.slot-name {
		font-weight: 600;
		min-width: 50px;
	}

	.slot-loaded {
		color: var(--success, #a6e3a1);
	}

	.slot-unloaded {
		color: var(--fg-muted, #a6adc8);
	}

	.slot-model {
		font-family: var(--font-mono, monospace);
		font-size: 0.75rem;
		color: var(--fg-muted, #a6adc8);
	}

	/* Model list */
	.model-list {
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.model-list li {
		font-size: 0.85rem;
		font-family: var(--font-mono, monospace);
		padding: var(--space-xs, 4px) 0;
		border-bottom: 1px solid var(--border, #45475a);
	}

	.model-list li:last-child {
		border-bottom: none;
	}

	/* Stats table */
	.stats-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.85rem;
	}

	.stats-table th {
		text-align: left;
		font-weight: 600;
		color: var(--fg-muted, #a6adc8);
		font-size: 0.75rem;
		text-transform: uppercase;
		padding: var(--space-xs, 4px) var(--space-sm, 8px);
		border-bottom: 1px solid var(--border, #45475a);
	}

	.stats-table td {
		padding: var(--space-xs, 4px) var(--space-sm, 8px);
		border-bottom: 1px solid var(--border, #45475a);
	}

	.stats-table .num {
		font-family: var(--font-mono, monospace);
		text-align: right;
	}

	.collection-status {
		font-size: 0.75rem;
		padding: 2px 6px;
		border-radius: var(--radius-sm, 4px);
		background-color: var(--surface-hover, #3b3d52);
	}

	.status-ok {
		color: var(--success, #a6e3a1);
	}

	/* VRAM bar */
	.vram-bar-container {
		display: flex;
		flex-direction: column;
		gap: var(--space-xs, 4px);
	}

	.vram-bar {
		width: 100%;
		height: 12px;
		background-color: var(--bg, #1e1e2e);
		border-radius: var(--radius-sm, 4px);
		overflow: hidden;
	}

	.vram-fill {
		height: 100%;
		background-color: var(--success, #a6e3a1);
		border-radius: var(--radius-sm, 4px);
		transition: width var(--transition-normal, 250ms ease);
	}

	.vram-mid {
		background-color: var(--warning, #f9e2af);
	}

	.vram-high {
		background-color: var(--error, #f38ba8);
	}

	.vram-label {
		font-size: 0.75rem;
		color: var(--fg-muted, #a6adc8);
		font-family: var(--font-mono, monospace);
	}

	.text-muted {
		color: var(--fg-muted, #a6adc8);
		font-size: 0.85rem;
	}
</style>
