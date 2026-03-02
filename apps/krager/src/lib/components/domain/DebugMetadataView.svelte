<!--
  DebugMetadataView.svelte — Renders DebugMetadata from a debug query response
  
  Shows: LLM used + model, route + auto-routed badge, preset, mode,
  retrieval/generation timings, embedding models, vector spaces,
  candidate counts, similarity threshold, per-space result counts,
  lexicon terms, critic scores, chunks pre/post critic.
-->
<script lang="ts">
	import type { DebugMetadata } from "$lib/types";

	interface Props {
		metadata: DebugMetadata;
	}

	const { metadata }: Props = $props();

	const avgCriticScore = $derived(
		metadata.critic_scores.length > 0
			? (metadata.critic_scores.reduce((a, b) => a + b, 0) / metadata.critic_scores.length).toFixed(3)
			: "—",
	);

	const criticScoreRange = $derived(
		metadata.critic_scores.length > 0
			? `${Math.min(...metadata.critic_scores).toFixed(3)} – ${Math.max(...metadata.critic_scores).toFixed(3)}`
			: "—",
	);
</script>

<div class="debug-metadata">
	<!-- LLM & Route -->
	<section class="meta-section">
		<h4>LLM & Routing</h4>
		<dl class="meta-grid">
			<dt>LLM Slot</dt>
			<dd>{metadata.llm_used}</dd>
			<dt>Model</dt>
			<dd class="mono">{metadata.llm_model}</dd>
			<dt>Route</dt>
			<dd>
				{metadata.route}
				{#if metadata.auto_routed}
					<span class="badge badge-auto">auto</span>
				{/if}
			</dd>
			{#if metadata.route_reason}
				<dt>Route Reason</dt>
				<dd>{metadata.route_reason}</dd>
			{/if}
			<dt>Preset</dt>
			<dd>{metadata.preset}</dd>
			{#if metadata.mode}
				<dt>Mode</dt>
				<dd>{metadata.mode}</dd>
			{/if}
		</dl>
	</section>

	<!-- Timings -->
	<section class="meta-section">
		<h4>Timings</h4>
		<dl class="meta-grid">
			<dt>Retrieval</dt>
			<dd class="mono">{metadata.retrieval_time_ms.toLocaleString()} ms</dd>
			<dt>Generation</dt>
			<dd class="mono">{metadata.generation_time_ms.toLocaleString()} ms</dd>
			<dt>Total</dt>
			<dd class="mono">{(metadata.retrieval_time_ms + metadata.generation_time_ms).toLocaleString()} ms</dd>
		</dl>
	</section>

	<!-- Embeddings & Vector Spaces -->
	<section class="meta-section">
		<h4>Embeddings & Vectors</h4>
		<dl class="meta-grid">
			<dt>Embedding Models</dt>
			<dd class="mono">{metadata.embedding_models_used.join(", ") || "—"}</dd>
			<dt>Vector Spaces</dt>
			<dd class="mono">{metadata.vector_spaces_searched.join(", ") || "—"}</dd>
			{#if metadata.collections_searched}
				<dt>Collections</dt>
				<dd class="mono">{metadata.collections_searched.join(", ")}</dd>
			{/if}
			<dt>Similarity Threshold</dt>
			<dd class="mono">{metadata.similarity_threshold.toFixed(3)}</dd>
		</dl>
	</section>

	<!-- Candidate Counts -->
	<section class="meta-section">
		<h4>Candidates</h4>
		<dl class="meta-grid">
			<dt>Before Dedup</dt>
			<dd class="mono">{metadata.total_candidates_before_dedup}</dd>
			<dt>After Dedup</dt>
			<dd class="mono">{metadata.total_candidates_after_dedup}</dd>
			<dt>Lexicon Terms</dt>
			<dd class="mono">{metadata.lexicon_terms_injected}</dd>
		</dl>
	</section>

	<!-- Per-space Result Counts -->
	{#if Object.keys(metadata.per_space_result_counts).length > 0}
		<section class="meta-section">
			<h4>Results per Space</h4>
			<table class="meta-table">
				<thead>
					<tr>
						<th>Space</th>
						<th>Count</th>
					</tr>
				</thead>
				<tbody>
					{#each Object.entries(metadata.per_space_result_counts) as [space, count]}
						<tr>
							<td class="mono">{space}</td>
							<td class="mono num">{count}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</section>
	{/if}

	<!-- Critic Scores -->
	<section class="meta-section">
		<h4>Critic</h4>
		<dl class="meta-grid">
			<dt>Chunks Pre-Critic</dt>
			<dd class="mono">{metadata.chunks_pre_critic}</dd>
			<dt>Chunks Post-Critic</dt>
			<dd class="mono">{metadata.chunks_post_critic}</dd>
			<dt>Scores ({metadata.critic_scores.length})</dt>
			<dd class="mono">{avgCriticScore} avg</dd>
			<dt>Score Range</dt>
			<dd class="mono">{criticScoreRange}</dd>
		</dl>
		{#if metadata.critic_scores.length > 0}
			<div class="score-distribution">
				{#each metadata.critic_scores as score, i}
					<span
						class="score-chip"
						class:score-high={score >= 0.7}
						class:score-mid={score >= 0.4 && score < 0.7}
						class:score-low={score < 0.4}
						title="Chunk {i + 1}: {score.toFixed(3)}"
					>
						{score.toFixed(2)}
					</span>
				{/each}
			</div>
		{/if}
	</section>
</div>

<style>
	.debug-metadata {
		display: flex;
		flex-direction: column;
		gap: var(--space-md, 16px);
	}

	.meta-section {
		background-color: var(--surface, #313244);
		border: 1px solid var(--border, #45475a);
		border-radius: var(--radius-md, 8px);
		padding: var(--space-md, 16px);
	}

	.meta-section h4 {
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--fg-muted, #a6adc8);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin: 0 0 var(--space-sm, 8px);
	}

	.meta-grid {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: var(--space-xs, 4px) var(--space-md, 16px);
		margin: 0;
	}

	.meta-grid dt {
		font-size: 0.8rem;
		color: var(--fg-muted, #a6adc8);
	}

	.meta-grid dd {
		font-size: 0.85rem;
		margin: 0;
	}

	.mono {
		font-family: var(--font-mono, monospace);
		font-size: 0.8rem;
	}

	.badge {
		display: inline-block;
		font-size: 0.65rem;
		font-weight: 700;
		text-transform: uppercase;
		padding: 1px 5px;
		border-radius: var(--radius-sm, 4px);
		vertical-align: middle;
		margin-left: var(--space-xs, 4px);
	}

	.badge-auto {
		background-color: var(--accent, #89b4fa);
		color: var(--bg, #1e1e2e);
	}

	.meta-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.85rem;
	}

	.meta-table th {
		text-align: left;
		font-weight: 600;
		color: var(--fg-muted, #a6adc8);
		font-size: 0.75rem;
		text-transform: uppercase;
		padding: var(--space-xs, 4px) var(--space-sm, 8px);
		border-bottom: 1px solid var(--border, #45475a);
	}

	.meta-table td {
		padding: var(--space-xs, 4px) var(--space-sm, 8px);
		border-bottom: 1px solid var(--border, #45475a);
	}

	.num {
		text-align: right;
	}

	.score-distribution {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-xs, 4px);
		margin-top: var(--space-sm, 8px);
	}

	.score-chip {
		font-family: var(--font-mono, monospace);
		font-size: 0.7rem;
		padding: 2px 6px;
		border-radius: var(--radius-sm, 4px);
	}

	.score-high {
		background-color: var(--success-bg, rgba(166, 227, 161, 0.1));
		color: var(--success, #a6e3a1);
	}

	.score-mid {
		background-color: var(--warning-bg, rgba(249, 226, 175, 0.1));
		color: var(--warning, #f9e2af);
	}

	.score-low {
		background-color: var(--error-bg, rgba(243, 139, 168, 0.1));
		color: var(--error, #f38ba8);
	}
</style>
