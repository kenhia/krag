<!--
  SourceList.svelte — Renders an array of source chunks
  
  Displays file path (copyable), score badge, rank, language tag,
  and chunk content in <pre>. Empty state when no sources.
-->
<script lang="ts">
import { addToast } from "$lib/state/notifications.svelte";
import type { SourceChunk } from "$lib/types";

interface Props {
	sources: SourceChunk[];
}

let { sources }: Props = $props();

async function copyPath(path: string) {
	try {
		await navigator.clipboard.writeText(path);
		addToast("Path copied", "info", 2000);
	} catch {
		addToast("Failed to copy path", "error");
	}
}

function scoreColor(score: number): string {
	if (score >= 0.8) return "var(--success, #a6e3a1)";
	if (score >= 0.5) return "var(--warning, #f9e2af)";
	return "var(--fg-muted, #a6adc8)";
}

function lineRange(chunk: SourceChunk): string {
	if (chunk.start_line != null && chunk.end_line != null) {
		return `L${chunk.start_line}–${chunk.end_line}`;
	}
	if (chunk.start_line != null) {
		return `L${chunk.start_line}`;
	}
	return "";
}
</script>

{#if sources.length === 0}
	<div class="source-empty">
		<p class="text-muted">No sources</p>
	</div>
{:else}
	<div class="source-list">
		{#each sources as chunk, i (chunk.chunk_id)}
			<div class="source-item">
				<div class="source-header">
					<span class="source-rank">#{chunk.rank}</span>
					<button
						class="source-path"
						onclick={() => copyPath(chunk.file_path)}
						title="Click to copy path"
					>
						{chunk.file_path}
					</button>
					{#if lineRange(chunk)}
						<span class="source-lines">{lineRange(chunk)}</span>
					{/if}
					{#if chunk.language}
						<span class="source-lang">{chunk.language}</span>
					{/if}
					{#if chunk.collection}
						<span class="source-collection">{chunk.collection}</span>
					{/if}
					<span class="source-score" style:color={scoreColor(chunk.score)}>
						{chunk.score.toFixed(3)}
					</span>
				</div>
				<pre class="source-content">{chunk.chunk_content}</pre>
			</div>
		{/each}
	</div>
{/if}

<style>
	.source-empty {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: var(--space-lg, 24px);
	}

	.source-list {
		display: flex;
		flex-direction: column;
		gap: var(--space-sm, 8px);
	}

	.source-item {
		border: 1px solid var(--border, #45475a);
		border-radius: var(--radius-md, 8px);
		overflow: hidden;
	}

	.source-header {
		display: flex;
		align-items: center;
		gap: var(--space-sm, 8px);
		padding: var(--space-sm, 8px) var(--space-md, 16px);
		background-color: var(--bg-elevated, #252537);
		border-bottom: 1px solid var(--border, #45475a);
		flex-wrap: wrap;
	}

	.source-rank {
		font-size: 0.7rem;
		font-weight: 700;
		color: var(--accent, #89b4fa);
		flex-shrink: 0;
		min-width: 24px;
	}

	.source-path {
		font-family: var(--font-mono, monospace);
		font-size: 0.8rem;
		color: var(--accent, #89b4fa);
		background: none;
		border: none;
		cursor: pointer;
		padding: 0;
		text-align: left;
		word-break: break-all;
	}

	.source-path:hover {
		text-decoration: underline;
		color: var(--accent-hover, #74a8f7);
	}

	.source-lines {
		font-size: 0.7rem;
		font-family: var(--font-mono, monospace);
		color: var(--fg-muted, #a6adc8);
		flex-shrink: 0;
	}

	.source-lang {
		font-size: 0.65rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		padding: 1px 6px;
		border-radius: var(--radius-sm, 4px);
		background-color: var(--surface, #313244);
		color: var(--fg-muted, #a6adc8);
		flex-shrink: 0;
	}

	.source-collection {
		font-size: 0.65rem;
		padding: 1px 6px;
		border-radius: var(--radius-sm, 4px);
		background-color: var(--surface, #313244);
		color: var(--fg-muted, #a6adc8);
		flex-shrink: 0;
	}

	.source-score {
		font-family: var(--font-mono, monospace);
		font-size: 0.75rem;
		font-weight: 600;
		flex-shrink: 0;
		margin-left: auto;
	}

	.source-content {
		margin: 0;
		padding: var(--space-sm, 8px) var(--space-md, 16px);
		font-size: 0.8rem;
		line-height: 1.5;
		max-height: 200px;
		overflow-y: auto;
		background-color: var(--surface, #313244);
		border: none;
		border-radius: 0;
	}

	.text-muted {
		color: var(--fg-muted, #a6adc8);
		font-size: 0.85rem;
	}
</style>
