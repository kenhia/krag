<!--
  Toggle.svelte — Boolean switch component

  Props: checked, onchange, disabled, label
  Keyboard accessible: Space/Enter to toggle.
-->
<script lang="ts">
interface Props {
	checked: boolean;
	onchange?: (value: boolean) => void;
	disabled?: boolean;
	label?: string;
}

let { checked = false, onchange, disabled = false, label }: Props = $props();

function toggle() {
	if (disabled) return;
	onchange?.(!checked);
}

function handleKeyDown(e: KeyboardEvent) {
	if (disabled) return;
	if (e.key === " " || e.key === "Enter") {
		e.preventDefault();
		toggle();
	}
}
</script>

<div class="toggle-wrapper">
	<!-- svelte-ignore a11y_role_has_required_aria_props -->
	<button
		type="button"
		class="toggle-track"
		class:toggle-on={checked}
		class:toggle-disabled={disabled}
		role="switch"
		aria-checked={checked}
		aria-disabled={disabled}
		aria-label={label ?? "Toggle"}
		onclick={toggle}
		onkeydown={handleKeyDown}
	>
		<span class="toggle-thumb" class:toggle-thumb-on={checked}></span>
	</button>
	{#if label}
		<span class="toggle-label" class:toggle-label-disabled={disabled}>{label}</span>
	{/if}
</div>

<style>
	.toggle-wrapper {
		display: flex;
		align-items: center;
		gap: var(--space-sm, 8px);
	}

	.toggle-track {
		position: relative;
		width: 36px;
		height: 20px;
		background-color: var(--surface-hover, #3b3d52);
		border: 1px solid var(--border, #45475a);
		border-radius: 10px;
		cursor: pointer;
		transition: background-color var(--transition-fast, 150ms ease);
		padding: 0;
		flex-shrink: 0;
	}

	.toggle-track:focus-visible {
		outline: 2px solid var(--accent, #89b4fa);
		outline-offset: 2px;
	}

	.toggle-on {
		background-color: var(--accent, #89b4fa);
		border-color: var(--accent, #89b4fa);
	}

	.toggle-disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.toggle-thumb {
		position: absolute;
		top: 2px;
		left: 2px;
		width: 14px;
		height: 14px;
		background-color: var(--fg, #cdd6f4);
		border-radius: 50%;
		transition: transform var(--transition-fast, 150ms ease);
	}

	.toggle-thumb-on {
		transform: translateX(16px);
	}

	.toggle-label {
		font-size: 0.875rem;
		color: var(--fg, #cdd6f4);
		user-select: none;
	}

	.toggle-label-disabled {
		opacity: 0.5;
	}
</style>
