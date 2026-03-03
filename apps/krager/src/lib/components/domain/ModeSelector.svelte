<!--
  ModeSelector.svelte — Mode selection dropdown with optional detail panel

  Displays available retrieval modes from modesState.
  Selecting a mode fetches its detail (description, collections, llm_slot, top_k, critic).
  "(default mode)" maps to null selection.
-->
<script lang="ts">
	import {
		modesState,
		setSelected,
	} from "$lib/state/modes.svelte";
	import { getModeDetail } from "$lib/services/kragd-client";
	import { handleKragdError } from "$lib/utils/errors";
	import type { ModeDetailResponse } from "$lib/types";
	import Spinner from "$lib/components/ui/Spinner.svelte";

	let detail = $state<ModeDetailResponse | null>(null);
	let detailLoading = $state(false);
	let detailError = $state<string | null>(null);

	async function handleChange(event: Event) {
		const value = (event.target as HTMLSelectElement).value;
		const selected = value === "" ? null : value;
		setSelected(selected);
		detail = null;
		detailError = null;

		if (selected) {
			detailLoading = true;
			try {
				detail = await getModeDetail(selected);
			} catch (e) {
				detailError = handleKragdError(e);
			} finally {
				detailLoading = false;
			}
		}
	}

	const selectValue = $derived(modesState.selected ?? "");
</script>

<div class="mode-selector">
	<div class="mode-select-row">
		<label class="mode-label" for="mode-select">Mode</label>
		{#if modesState.loading}
			<Spinner size="sm" />
		{:else}
			<select
				id="mode-select"
				class="mode-select"
				value={selectValue}
				onchange={handleChange}
				disabled={modesState.available.length === 0}
			>
				<option value="">(default mode)</option>
				{#each modesState.available as mode (mode.name)}
					<option value={mode.name}>{mode.name}</option>
				{/each}
			</select>
		{/if}
		{#if modesState.error}
			<span class="mode-error">{modesState.error}</span>
		{/if}
	</div>

	{#if detailLoading}
		<div class="mode-detail loading">
			<Spinner size="sm" />
			<span class="text-muted">Loading mode detail...</span>
		</div>
	{:else if detailError}
		<div class="mode-detail error">
			<span class="mode-error">{detailError}</span>
		</div>
	{:else if detail}
		<div class="mode-detail">
			<p class="detail-desc">{detail.description}</p>
			<dl class="detail-list">
				<dt>Collections</dt>
				<dd>{Object.keys(detail.collections).join(", ") || "—"}</dd>
				<dt>LLM Slot</dt>
				<dd>{detail.llm_slot}</dd>
				<dt>Top K</dt>
				<dd>{detail.top_k}</dd>
				<dt>Critic</dt>
				<dd>{detail.critic_enabled ? `Enabled (≥${detail.critic_threshold})` : "Disabled"}</dd>
			</dl>
		</div>
	{/if}
</div>

<style>
	.mode-selector {
		display: flex;
		flex-direction: column;
		gap: var(--space-sm, 8px);
	}

	.mode-select-row {
		display: flex;
		align-items: center;
		gap: var(--space-sm, 8px);
	}

	.mode-label {
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--fg-muted, #a6adc8);
		flex-shrink: 0;
	}

	.mode-select {
		flex: 1;
		max-width: 200px;
		padding: var(--space-xs, 4px) var(--space-sm, 8px);
		background-color: var(--surface, #313244);
		color: var(--fg, #cdd6f4);
		border: 1px solid var(--border, #45475a);
		border-radius: var(--radius-sm, 4px);
		font-size: 0.8rem;
		cursor: pointer;
	}

	.mode-select:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.mode-select:focus {
		outline: none;
		border-color: var(--accent, #89b4fa);
	}

	.mode-error {
		font-size: 0.75rem;
		color: var(--error, #f38ba8);
	}

	.mode-detail {
		padding: var(--space-sm, 8px) var(--space-md, 16px);
		background-color: var(--surface, #313244);
		border: 1px solid var(--border, #45475a);
		border-radius: var(--radius-sm, 4px);
		font-size: 0.8rem;
	}

	.mode-detail.loading,
	.mode-detail.error {
		display: flex;
		align-items: center;
		gap: var(--space-sm, 8px);
	}

	.detail-desc {
		margin: 0 0 var(--space-sm, 8px);
		color: var(--fg, #cdd6f4);
	}

	.detail-list {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: var(--space-xs, 4px) var(--space-md, 16px);
		margin: 0;
	}

	.detail-list dt {
		font-size: 0.75rem;
		color: var(--fg-muted, #a6adc8);
	}

	.detail-list dd {
		font-size: 0.8rem;
		font-family: var(--font-mono, monospace);
		margin: 0;
	}

	.text-muted {
		color: var(--fg-muted, #a6adc8);
		font-size: 0.8rem;
	}
</style>
