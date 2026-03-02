<!--
  Input.svelte — Reusable text input component
  
  Props: value (bindable), placeholder, disabled, type, label, oninput
-->
<script lang="ts">
	interface Props {
		value: string;
		placeholder?: string;
		disabled?: boolean;
		type?: string;
		label?: string;
		oninput?: (event: Event) => void;
	}

	let { value = $bindable(""), placeholder = "", disabled = false, type = "text", label, oninput }: Props = $props();

	const inputId = `input-${Math.random().toString(36).slice(2, 9)}`;
</script>

{#if label}
	<label class="input-label" for={inputId}>{label}</label>
{/if}
<input
	id={inputId}
	class="input"
	{type}
	bind:value
	{placeholder}
	{disabled}
	{oninput}
/>

<style>
	.input-label {
		display: block;
		font-size: 0.8rem;
		font-weight: 500;
		color: var(--fg-muted, #a6adc8);
		margin-bottom: var(--space-xs, 4px);
	}

	.input {
		display: block;
		width: 100%;
		padding: var(--space-sm, 8px) var(--space-md, 16px);
		background-color: var(--surface, #313244);
		color: var(--fg, #cdd6f4);
		border: 1px solid var(--border, #45475a);
		border-radius: var(--radius-md, 8px);
		font-size: 0.875rem;
		font-family: inherit;
		transition:
			border-color var(--transition-fast, 150ms ease),
			background-color var(--transition-fast, 150ms ease);
	}

	.input::placeholder {
		color: var(--fg-muted, #a6adc8);
		opacity: 0.6;
	}

	.input:focus {
		outline: none;
		border-color: var(--accent, #89b4fa);
		background-color: var(--bg, #1e1e2e);
	}

	.input:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
</style>
