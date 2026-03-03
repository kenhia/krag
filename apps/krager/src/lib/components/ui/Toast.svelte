<!--
  Toast.svelte — Animated toast notification component
  
  Accepts: message, type ('error'|'info'|'success'|'warning'), duration
  Auto-dismisses after duration. Accessible via role="alert".
-->
<script lang="ts">
	import { onMount } from "svelte";

	interface Props {
		id: string;
		message: string;
		type: "error" | "info" | "success" | "warning";
		duration?: number;
		onDismiss: (id: string) => void;
	}

	let { id, message, type, duration = 5000, onDismiss }: Props = $props();

	let visible = $state(false);

	onMount(() => {
		// Trigger enter animation
		requestAnimationFrame(() => {
			visible = true;
		});

		if (duration > 0) {
			const timer = setTimeout(() => dismiss(), duration);
			return () => clearTimeout(timer);
		}
	});

	function dismiss() {
		visible = false;
		// Wait for exit animation before removing
		setTimeout(() => onDismiss(id), 200);
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === "Escape") {
			dismiss();
		}
	}
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div
	class="toast toast-{type}"
	class:toast-visible={visible}
	role="alert"
	aria-live="assertive"
	aria-atomic="true"
	onkeydown={handleKeydown}
>
	<span class="toast-icon">
		{#if type === "error"}✕{:else if type === "success"}✓{:else if type === "warning"}⚠{:else}ℹ{/if}
	</span>
	<span class="toast-message">{message}</span>
	<button class="toast-close" onclick={dismiss} aria-label="Dismiss notification">×</button>
</div>

<style>
	.toast {
		display: flex;
		align-items: center;
		gap: var(--space-sm, 8px);
		padding: var(--space-sm, 8px) var(--space-md, 16px);
		border-radius: var(--radius-md, 8px);
		border: 1px solid var(--border, #45475a);
		background-color: var(--surface, #313244);
		color: var(--fg, #cdd6f4);
		font-size: 0.875rem;
		max-width: 400px;
		width: 100%;
		opacity: 0;
		transform: translateX(100%);
		transition:
			opacity 200ms ease,
			transform 200ms ease;
		pointer-events: auto;
	}

	.toast-visible {
		opacity: 1;
		transform: translateX(0);
	}

	.toast-error {
		border-color: var(--error, #f38ba8);
		background-color: var(--error-bg, rgba(243, 139, 168, 0.1));
	}

	.toast-success {
		border-color: var(--success, #a6e3a1);
		background-color: var(--success-bg, rgba(166, 227, 161, 0.1));
	}

	.toast-warning {
		border-color: var(--warning, #f9e2af);
		background-color: var(--warning-bg, rgba(249, 226, 175, 0.1));
	}

	.toast-info {
		border-color: var(--info, #89b4fa);
		background-color: var(--info-bg, rgba(137, 180, 250, 0.1));
	}

	.toast-icon {
		flex-shrink: 0;
		font-size: 1rem;
	}

	.toast-error .toast-icon {
		color: var(--error, #f38ba8);
	}
	.toast-success .toast-icon {
		color: var(--success, #a6e3a1);
	}
	.toast-warning .toast-icon {
		color: var(--warning, #f9e2af);
	}
	.toast-info .toast-icon {
		color: var(--info, #89b4fa);
	}

	.toast-message {
		flex: 1;
		line-height: 1.4;
	}

	.toast-close {
		flex-shrink: 0;
		background: none;
		border: none;
		color: var(--fg-muted, #a6adc8);
		cursor: pointer;
		font-size: 1.25rem;
		padding: 0 var(--space-xs, 4px);
		line-height: 1;
		border-radius: var(--radius-sm, 4px);
	}

	.toast-close:hover {
		color: var(--fg, #cdd6f4);
		background-color: var(--surface-hover, #3b3d52);
	}
</style>
