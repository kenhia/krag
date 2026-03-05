<!--
  QueryAnswer.svelte — Display a query/retrieve answer with sources and critic warning.

  Renders:
  - Answer text
  - Source references (file_path + score), no chunk_content
  - Low-confidence warning when critic enabled and any score < cut_off
-->
<script lang="ts">
import { queryState } from "$lib/state/query.svelte";
import type { DebugMetadata, SourceChunk, TranscriptEntry } from "$lib/types";

interface Props {
	entry: TranscriptEntry;
	criticEnabled?: boolean;
	criticCutOff?: number;
	showSources?: boolean;
}

let { entry, criticEnabled = false, criticCutOff = 3, showSources = true }: Props = $props();

let sourcesExpanded = $state(false);

// Safely extract typed fields from the `unknown` response
const response = $derived(
	entry.response as {
		answer?: string;
		sources?: SourceChunk[];
		debug?: DebugMetadata | null;
	} | null,
);
const answer = $derived(response?.answer ?? "");
const sources = $derived(response?.sources ?? []);
const debug = $derived(response?.debug ?? null);

const hasLowConfidence = $derived(() => {
	if (!criticEnabled || !debug?.critic_scores?.length) return false;
	return debug.critic_scores.some((s: number) => s < criticCutOff);
});
</script>

{#if entry.loading}
	<div class="answer-loading">
		<span class="loading-dot">…</span>
	</div>
{:else if entry.error}
	<div class="answer-error">{entry.error}</div>
{:else if response}
	<div class="query-answer">
		{#if hasLowConfidence()}
			<div class="low-confidence-warning">
				⚠ Low confidence — some critic scores are below the cut-off threshold.
			</div>
		{/if}

		{#if answer}
			<div class="answer-text">{answer}</div>
		{/if}

		{#if showSources && sources.length > 0}
			<div class="answer-sources">
				<button
					class="sources-toggle"
					onclick={() => (sourcesExpanded = !sourcesExpanded)}
					aria-expanded={sourcesExpanded}
				>
					{sourcesExpanded ? "▾" : "▸"} {sources.length} source{sources.length === 1 ? "" : "s"}
				</button>
				{#if sourcesExpanded}
					<ul class="sources-list">
						{#each sources as source}
							<li class="source-item">
								<span class="source-path">{source.file_path}</span>
								<span class="source-score">{source.score}</span>
							</li>
						{/each}
					</ul>
				{/if}
			</div>
		{/if}
	</div>
{/if}

<style>
	.query-answer {
		display: flex;
		flex-direction: column;
		gap: var(--space-sm, 8px);
	}

	.answer-text {
		line-height: 1.6;
		white-space: pre-wrap;
		word-wrap: break-word;
	}

	.low-confidence-warning {
		padding: var(--space-xs, 4px) var(--space-sm, 8px);
		background-color: var(--warning-bg, rgba(249, 226, 175, 0.1));
		border: 1px solid var(--warning, #f9e2af);
		border-radius: var(--radius-sm, 4px);
		color: var(--warning, #f9e2af);
		font-size: 0.8rem;
	}

	.answer-error {
		color: var(--error, #f38ba8);
		font-size: 0.85rem;
	}

	.answer-loading {
		color: var(--fg-muted, #a6adc8);
		font-size: 0.85rem;
	}

	.answer-sources {
		margin-top: var(--space-xs, 4px);
	}

	.sources-toggle {
		display: inline-flex;
		align-items: center;
		gap: var(--space-xs, 4px);
		background: none;
		border: none;
		padding: 2px var(--space-xs, 4px);
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--fg-muted, #a6adc8);
		cursor: pointer;
		border-radius: var(--radius-sm, 4px);
		transition: background-color var(--transition-fast, 150ms ease);
	}

	.sources-toggle:hover {
		background-color: var(--surface-hover, rgba(69, 71, 90, 0.5));
		color: var(--fg, #cdd6f4);
	}

	.sources-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.source-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 2px var(--space-xs, 4px);
		font-size: 0.8rem;
		border-radius: var(--radius-sm, 4px);
	}

	.source-item:hover {
		background-color: var(--surface-hover, rgba(69, 71, 90, 0.5));
	}

	.source-path {
		color: var(--accent, #89b4fa);
		font-family: var(--font-mono, monospace);
		font-size: 0.75rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.source-score {
		color: var(--fg-muted, #a6adc8);
		font-size: 0.75rem;
		flex-shrink: 0;
		margin-left: var(--space-sm, 8px);
	}

	.loading-dot {
		animation: pulse 1.5s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 0.4; }
		50% { opacity: 1; }
	}
</style>
