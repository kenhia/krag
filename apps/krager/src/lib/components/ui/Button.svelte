<!--
  Button.svelte — Reusable button component
  
  Props: label, variant ('primary'|'secondary'|'danger'), disabled, loading, onclick
  Keyboard accessible via native <button>.
-->
<script lang="ts">
interface Props {
	label: string;
	variant?: "primary" | "secondary" | "danger";
	disabled?: boolean;
	loading?: boolean;
	onclick?: (event: MouseEvent) => void;
}

let { label, variant = "primary", disabled = false, loading = false, onclick }: Props = $props();
</script>

<button
	class="btn btn-{variant}"
	disabled={disabled || loading}
	{onclick}
>
	{#if loading}
		<span class="btn-spinner" aria-hidden="true"></span>
	{/if}
	<span class="btn-label" class:btn-label-hidden={loading}>{label}</span>
</button>

<style>
	.btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: var(--space-sm, 8px);
		padding: var(--space-sm, 8px) var(--space-md, 16px);
		border: 1px solid transparent;
		border-radius: var(--radius-md, 8px);
		font-size: 0.875rem;
		font-weight: 500;
		font-family: inherit;
		cursor: pointer;
		transition:
			background-color var(--transition-fast, 150ms ease),
			border-color var(--transition-fast, 150ms ease),
			opacity var(--transition-fast, 150ms ease);
		position: relative;
		min-height: 36px;
	}

	.btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn:focus-visible {
		outline: 2px solid var(--accent, #89b4fa);
		outline-offset: 2px;
	}

	/* Primary */
	.btn-primary {
		background-color: var(--accent, #89b4fa);
		color: var(--bg, #1e1e2e);
		border-color: var(--accent, #89b4fa);
	}

	.btn-primary:hover:not(:disabled) {
		background-color: var(--accent-hover, #74a8f7);
	}

	/* Secondary */
	.btn-secondary {
		background-color: var(--surface, #313244);
		color: var(--fg, #cdd6f4);
		border-color: var(--border, #45475a);
	}

	.btn-secondary:hover:not(:disabled) {
		background-color: var(--surface-hover, #3b3d52);
	}

	/* Danger */
	.btn-danger {
		background-color: var(--error, #f38ba8);
		color: var(--bg, #1e1e2e);
		border-color: var(--error, #f38ba8);
	}

	.btn-danger:hover:not(:disabled) {
		background-color: var(--error-hover, #e67a97);
	}

	/* Loading spinner */
	.btn-spinner {
		width: 16px;
		height: 16px;
		border: 2px solid currentColor;
		border-top-color: transparent;
		border-radius: 50%;
		animation: spin 600ms linear infinite;
	}

	.btn-label-hidden {
		opacity: 0.4;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
