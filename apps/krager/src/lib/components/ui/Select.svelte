<!--
  Select.svelte — Generic dropdown select component

  Props: options, value, onchange, placeholder, disabled, label
  Keyboard accessible: ArrowDown/ArrowUp to navigate, Enter to select, Escape to close.
-->
<script lang="ts">
interface SelectOption {
	value: string;
	label: string;
	description?: string;
}

interface Props {
	options: SelectOption[];
	value: string | null;
	onchange?: (value: string) => void;
	placeholder?: string;
	disabled?: boolean;
	label?: string;
}

let {
	options,
	value = null,
	onchange,
	placeholder = "Select...",
	disabled = false,
	label,
}: Props = $props();

let open = $state(false);
let highlightIndex = $state(-1);

const selectedLabel = $derived(options.find((o) => o.value === value)?.label ?? placeholder);

function toggle() {
	if (disabled) return;
	open = !open;
	if (open) {
		highlightIndex = options.findIndex((o) => o.value === value);
		if (highlightIndex === -1) highlightIndex = 0;
	}
}

function select(optionValue: string) {
	onchange?.(optionValue);
	open = false;
}

function handleKeyDown(e: KeyboardEvent) {
	if (disabled) return;

	switch (e.key) {
		case "Enter":
		case " ":
			e.preventDefault();
			if (!open) {
				open = true;
				highlightIndex = options.findIndex((o) => o.value === value);
				if (highlightIndex === -1) highlightIndex = 0;
			} else if (highlightIndex >= 0 && highlightIndex < options.length) {
				select(options[highlightIndex].value);
			}
			break;
		case "ArrowDown":
			e.preventDefault();
			if (!open) {
				open = true;
				highlightIndex = 0;
			} else {
				highlightIndex = Math.min(highlightIndex + 1, options.length - 1);
			}
			break;
		case "ArrowUp":
			e.preventDefault();
			if (open) {
				highlightIndex = Math.max(highlightIndex - 1, 0);
			}
			break;
		case "Escape":
			e.preventDefault();
			open = false;
			break;
	}
}
</script>

<div class="select-wrapper">
	{#if label}
		<span class="select-label">{label}</span>
	{/if}
	<div class="select-container">
		<!-- svelte-ignore a11y_role_has_required_aria_props -->
		<button
			type="button"
			class="select-trigger"
			class:select-open={open}
			class:select-disabled={disabled}
			role="combobox"
			aria-expanded={open}
			aria-disabled={disabled}
			aria-haspopup="listbox"
			onclick={toggle}
			onkeydown={handleKeyDown}
		>
			<span class="select-value" class:select-placeholder={value === null}>
				{selectedLabel}
			</span>
			<span class="select-chevron" class:select-chevron-up={open}>▾</span>
		</button>

		{#if open}
			<ul class="select-listbox" role="listbox">
				{#each options as option, i}
					<li
						role="option"
						class="select-option"
						class:select-option-highlighted={i === highlightIndex}
						class:select-option-selected={option.value === value}
						aria-selected={option.value === value}
						onclick={() => select(option.value)}
						onkeydown={() => {}}
						onmouseenter={() => (highlightIndex = i)}
					>
						<span class="option-label">{option.label}</span>
						{#if option.description}
							<span class="option-desc">{option.description}</span>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</div>
</div>

<style>
	.select-wrapper {
		display: flex;
		flex-direction: column;
		gap: var(--space-xs, 4px);
	}

	.select-label {
		font-size: 0.8rem;
		font-weight: 500;
		color: var(--fg-muted, #a6adc8);
	}

	.select-container {
		position: relative;
	}

	.select-trigger {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: var(--space-sm, 8px) var(--space-md, 16px);
		background-color: var(--surface, #313244);
		color: var(--fg, #cdd6f4);
		border: 1px solid var(--border, #45475a);
		border-radius: var(--radius-md, 8px);
		font-size: 0.875rem;
		font-family: inherit;
		cursor: pointer;
		transition:
			border-color var(--transition-fast, 150ms ease),
			background-color var(--transition-fast, 150ms ease);
	}

	.select-trigger:focus-visible {
		outline: 2px solid var(--accent, #89b4fa);
		outline-offset: 2px;
	}

	.select-open {
		border-color: var(--accent, #89b4fa);
	}

	.select-disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.select-placeholder {
		color: var(--fg-muted, #a6adc8);
		opacity: 0.6;
	}

	.select-chevron {
		font-size: 0.75rem;
		transition: transform var(--transition-fast, 150ms ease);
	}

	.select-chevron-up {
		transform: rotate(180deg);
	}

	.select-listbox {
		position: absolute;
		top: calc(100% + 4px);
		left: 0;
		right: 0;
		z-index: 50;
		list-style: none;
		margin: 0;
		padding: var(--space-xs, 4px);
		background-color: var(--surface, #313244);
		border: 1px solid var(--border, #45475a);
		border-radius: var(--radius-md, 8px);
		max-height: 200px;
		overflow-y: auto;
	}

	.select-option {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: var(--space-sm, 8px) var(--space-md, 16px);
		border-radius: var(--radius-sm, 4px);
		cursor: pointer;
		font-size: 0.875rem;
	}

	.select-option-highlighted {
		background-color: var(--surface-hover, #3b3d52);
	}

	.select-option-selected {
		color: var(--accent, #89b4fa);
	}

	.option-desc {
		font-size: 0.75rem;
		color: var(--fg-muted, #a6adc8);
	}
</style>
