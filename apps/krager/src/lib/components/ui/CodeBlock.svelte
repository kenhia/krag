<!--
  CodeBlock.svelte — Syntax-highlighted code block
  
  Uses Shiki via highlight() utility. Reacts to code, lang, and theme changes.
  Shows raw code in <pre> during first render while highlighting loads.
-->
<script lang="ts">
	import { highlight } from "$lib/utils/highlight";
	import { appTheme } from "$lib/state/theme.svelte";

	interface Props {
		code: string;
		lang: string;
	}

	const { code, lang }: Props = $props();

	let html = $state("");

	// Re-highlight when code, lang, or theme changes
	$effect(() => {
		const currentCode = code;
		const currentLang = lang;
		const currentTheme = appTheme.current;

		highlight(currentCode, currentLang, currentTheme).then((result) => {
			html = result;
		});
	});
</script>

{#if html}
	<div class="code-block" data-lang={lang}>
		{#if lang && lang !== "text"}
			<span class="lang-tag">{lang}</span>
		{/if}
		{@html html}
	</div>
{:else}
	<pre class="code-block-fallback"><code>{code}</code></pre>
{/if}

<style>
	.code-block {
		position: relative;
		border-radius: var(--radius-md, 8px);
		overflow: hidden;
		font-size: 0.85rem;
		line-height: 1.6;
	}

	.code-block :global(pre) {
		margin: 0;
		padding: var(--space-md, 16px);
		overflow-x: auto;
		border-radius: var(--radius-md, 8px);
	}

	.code-block :global(code) {
		font-family: var(--font-mono, monospace);
		font-size: 0.85rem;
	}

	.lang-tag {
		position: absolute;
		top: var(--space-xs, 4px);
		right: var(--space-sm, 8px);
		font-size: 0.65rem;
		font-weight: 600;
		text-transform: uppercase;
		color: var(--fg-muted, #a6adc8);
		opacity: 0.7;
		z-index: 1;
		pointer-events: none;
	}

	.code-block-fallback {
		margin: 0;
		padding: var(--space-md, 16px);
		font-family: var(--font-mono, monospace);
		font-size: 0.85rem;
		line-height: 1.6;
		overflow-x: auto;
		background-color: var(--surface, #313244);
		border-radius: var(--radius-md, 8px);
		border: 1px solid var(--border-subtle, #363849);
	}

	.code-block-fallback code {
		font-family: inherit;
	}
</style>
