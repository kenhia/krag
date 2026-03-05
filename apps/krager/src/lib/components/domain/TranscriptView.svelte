<!--
  TranscriptView.svelte — Scrollable transcript of interaction entries
  
  Displays TranscriptEntry[] from transcript state. Each entry shows:
  timestamp, type badge, query text, answer (or loading spinner),
  SourceList for query/retrieve entries, error messages.
  Newest entries appear at the top. "Clear" button.
-->
<script lang="ts">
import { tick } from "svelte";
import SourceList from "$lib/components/domain/SourceList.svelte";
import Button from "$lib/components/ui/Button.svelte";
import CodeBlock from "$lib/components/ui/CodeBlock.svelte";
import Spinner from "$lib/components/ui/Spinner.svelte";
import {
	clearTranscript,
	isChunksExpanded,
	toggleChunksExpanded,
	transcript,
} from "$lib/state/transcript.svelte";
import type { QueryResponse, RetrieveResponse, SourceChunk } from "$lib/types";
import { formatDuration, formatTimestamp } from "$lib/utils/format";

let scrollContainer: HTMLElement | undefined = $state(undefined);

const typeBadgeConfig: Record<string, { label: string; cssClass: string }> = {
	query: { label: "Q", cssClass: "badge-query" },
	retrieve: { label: "R", cssClass: "badge-retrieve" },
	index: { label: "I", cssClass: "badge-index" },
	debug: { label: "D", cssClass: "badge-debug" },
};

/** Parsed segment of an answer: either plain text or a code fence. */
interface AnswerSegment {
	type: "text" | "code";
	content: string;
	lang?: string;
}

/**
 * Parse answer text into segments, splitting on markdown code fences.
 * Handles ```lang\n...\n``` patterns.
 */
function parseAnswerSegments(answer: string): AnswerSegment[] {
	const segments: AnswerSegment[] = [];
	const fenceRegex = /^```(\w*)\n([\s\S]*?)^```$/gm;
	let lastIndex = 0;

	for (const match of answer.matchAll(fenceRegex)) {
		const matchStart = match.index ?? 0;

		// Text before this fence
		if (matchStart > lastIndex) {
			const text = answer.slice(lastIndex, matchStart);
			if (text.trim()) {
				segments.push({ type: "text", content: text });
			}
		}

		segments.push({
			type: "code",
			content: match[2],
			lang: match[1] || "text",
		});

		lastIndex = matchStart + match[0].length;
	}

	// Remaining text after last fence
	if (lastIndex < answer.length) {
		const text = answer.slice(lastIndex);
		if (text.trim()) {
			segments.push({ type: "text", content: text });
		}
	}

	return segments;
}

/** Check if answer contains any code fences. */
function hasCodeFences(answer: string): boolean {
	return /^```\w*\n[\s\S]*?^```$/m.test(answer);
}

function getSources(response: unknown): SourceChunk[] {
	if (!response || typeof response !== "object") return [];
	const r = response as Record<string, unknown>;
	if (Array.isArray(r.sources)) return r.sources as SourceChunk[];
	return [];
}

function getAnswer(response: unknown): string | null {
	if (!response || typeof response !== "object") return null;
	const r = response as Record<string, unknown>;
	if (typeof r.answer === "string") return r.answer;
	return null;
}

function getQueryText(request: unknown): string {
	if (!request || typeof request !== "object") return "";
	const r = request as Record<string, unknown>;
	return typeof r.query === "string" ? r.query : "";
}

async function scrollToTop() {
	await tick();
	if (scrollContainer) {
		scrollContainer.scrollTop = 0;
	}
}

// Auto-scroll to top when entries change (newest first)
$effect(() => {
	const _len = transcript.entries.length;
	scrollToTop();
});

function handleClear() {
	clearTranscript();
}

/** Entries in reverse chronological order (newest first). */
const reversedEntries = $derived([...transcript.entries].reverse());
</script>

<div class="transcript-view">
	<div class="transcript-header">
		<h3>Transcript</h3>
		{#if transcript.entries.length > 0}
			<Button label="Clear" variant="secondary" onclick={handleClear} />
		{/if}
	</div>

	{#if transcript.entries.length === 0}
		<div class="transcript-empty">
			<p class="text-muted">No interactions yet. Submit a query to get started.</p>
		</div>
	{:else}
		<div class="transcript-scroll" bind:this={scrollContainer}>
			{#each reversedEntries as entry (entry.id)}
				{@const badgeInfo = typeBadgeConfig[entry.type] ?? { label: "?", cssClass: "badge-default" }}
				{@const answer = getAnswer(entry.response)}
				{@const sources = getSources(entry.response)}
				{@const queryText = getQueryText(entry.request)}
				<div class="entry" class:entry-error={!!entry.error}>
					<div class="entry-header">
						<span class="type-badge {badgeInfo.cssClass}">{badgeInfo.label}</span>
						<span class="entry-timestamp">{formatTimestamp(entry.timestamp)}</span>
						{#if entry.durationMs != null}
							<span class="entry-duration">{formatDuration(entry.durationMs)}</span>
						{/if}
						{#if entry.loading}
							<Spinner size="sm" />
						{/if}
					</div>

					{#if queryText}
						<div class="entry-query">
							<span class="query-label">Q:</span>
							<span class="query-text">{queryText}</span>
						</div>
					{/if}

					{#if entry.error}
						<div class="entry-error-msg">
							<span class="error-icon">✕</span>
							<span>{entry.error}</span>
						</div>
					{:else if entry.loading && !answer}
						<div class="entry-loading">
							<Spinner size="sm" />
							<span class="text-muted">Waiting for response...</span>
						</div>
					{:else if answer != null}
						<div class="entry-answer">
							{#if hasCodeFences(answer)}
								{#each parseAnswerSegments(answer) as segment}
									{#if segment.type === "code"}
										<CodeBlock code={segment.content} lang={segment.lang ?? "text"} />
									{:else}
										<pre class="answer-text">{segment.content}</pre>
									{/if}
								{/each}
							{:else}
								<pre class="answer-text">{answer}</pre>
							{/if}
						</div>
					{/if}

					{#if sources.length > 0}
						<div class="entry-sources">
							<button
								class="chunks-toggle"
								onclick={() => toggleChunksExpanded(entry.id)}
								aria-expanded={isChunksExpanded(entry.id)}
							>
								{isChunksExpanded(entry.id) ? "▾" : "▸"} {sources.length} source{sources.length === 1 ? "" : "s"}
							</button>
							{#if isChunksExpanded(entry.id)}
								<SourceList {sources} />
							{/if}
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.transcript-view {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
	}

	.transcript-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding-bottom: var(--space-sm, 8px);
		border-bottom: 1px solid var(--border, #45475a);
		flex-shrink: 0;
	}

	.transcript-header h3 {
		font-size: 1rem;
		font-weight: 600;
		margin: 0;
	}

	.transcript-empty {
		display: flex;
		align-items: center;
		justify-content: center;
		flex: 1;
		padding: var(--space-xl, 32px);
	}

	.transcript-scroll {
		flex: 1;
		overflow-y: auto;
		padding: var(--space-sm, 8px) 0;
		display: flex;
		flex-direction: column;
		gap: var(--space-md, 16px);
	}

	.entry {
		border: 1px solid var(--border, #45475a);
		border-radius: var(--radius-md, 8px);
		padding: var(--space-md, 16px);
		background-color: var(--surface, #313244);
		display: flex;
		flex-direction: column;
		gap: var(--space-sm, 8px);
	}

	.entry-error {
		border-color: var(--error, #f38ba8);
	}

	.entry-header {
		display: flex;
		align-items: center;
		gap: var(--space-sm, 8px);
	}

	.type-badge {
		font-size: 0.65rem;
		font-weight: 700;
		text-transform: uppercase;
		padding: 2px 6px;
		border-radius: var(--radius-sm, 4px);
		flex-shrink: 0;
	}

	.badge-query {
		background-color: var(--accent, #89b4fa);
		color: var(--bg, #1e1e2e);
	}

	.badge-retrieve {
		background-color: var(--success, #a6e3a1);
		color: var(--bg, #1e1e2e);
	}

	.badge-index {
		background-color: var(--warning, #f9e2af);
		color: var(--bg, #1e1e2e);
	}

	.badge-debug {
		background-color: var(--fg-muted, #a6adc8);
		color: var(--bg, #1e1e2e);
	}

	.badge-default {
		background-color: var(--surface-hover, #3b3d52);
		color: var(--fg, #cdd6f4);
	}

	.entry-timestamp {
		font-size: 0.75rem;
		font-family: var(--font-mono, monospace);
		color: var(--fg-muted, #a6adc8);
	}

	.entry-duration {
		font-size: 0.7rem;
		font-family: var(--font-mono, monospace);
		color: var(--fg-muted, #a6adc8);
		opacity: 0.8;
	}

	.entry-query {
		display: flex;
		gap: var(--space-sm, 8px);
		font-size: 0.875rem;
	}

	.query-label {
		font-weight: 700;
		color: var(--accent, #89b4fa);
		flex-shrink: 0;
	}

	.query-text {
		color: var(--fg, #cdd6f4);
	}

	.entry-error-msg {
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

	.entry-loading {
		display: flex;
		align-items: center;
		gap: var(--space-sm, 8px);
		padding: var(--space-sm, 8px) 0;
	}

	.entry-answer {
		padding: 0;
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

	.entry-sources {
		padding-top: var(--space-sm, 8px);
		border-top: 1px solid var(--border-subtle, #363849);
	}

	.chunks-toggle {
		background: none;
		border: none;
		color: var(--fg-muted, #a6adc8);
		cursor: pointer;
		font-size: 0.8rem;
		padding: var(--space-xs, 4px) 0;
		transition: color var(--transition-fast, 150ms ease);
	}

	.chunks-toggle:hover {
		color: var(--accent, #89b4fa);
	}

	.text-muted {
		color: var(--fg-muted, #a6adc8);
		font-size: 0.85rem;
	}
</style>
