<!--
  Slider.svelte — Range slider with value label

  Props: value, min, max, step, onchange, disabled, label
-->
<script lang="ts">
interface Props {
	value: number;
	min: number;
	max: number;
	step: number;
	onchange?: (value: number) => void;
	disabled?: boolean;
	label?: string;
}

let { value, min, max, step, onchange, disabled = false, label }: Props = $props();

function handleInput(e: Event) {
	const target = e.target as HTMLInputElement;
	const newValue = Number.parseFloat(target.value);
	onchange?.(newValue);
}
</script>

<div class="slider-wrapper">
	{#if label}
		<div class="slider-header">
			<span class="slider-label">{label}</span>
			<span class="slider-value">{value}</span>
		</div>
	{:else}
		<span class="slider-value slider-value-standalone">{value}</span>
	{/if}
	<input
		type="range"
		class="slider-input"
		{value}
		{min}
		{max}
		{step}
		{disabled}
		oninput={handleInput}
	/>
</div>

<style>
	.slider-wrapper {
		display: flex;
		flex-direction: column;
		gap: var(--space-xs, 4px);
	}

	.slider-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.slider-label {
		font-size: 0.8rem;
		font-weight: 500;
		color: var(--fg-muted, #a6adc8);
	}

	.slider-value {
		font-size: 0.8rem;
		font-family: var(--font-mono, monospace);
		color: var(--fg, #cdd6f4);
	}

	.slider-value-standalone {
		text-align: right;
	}

	.slider-input {
		-webkit-appearance: none;
		appearance: none;
		width: 100%;
		height: 6px;
		background-color: var(--surface-hover, #3b3d52);
		border-radius: 3px;
		outline: none;
		cursor: pointer;
	}

	.slider-input:focus-visible {
		outline: 2px solid var(--accent, #89b4fa);
		outline-offset: 4px;
	}

	.slider-input::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		width: 16px;
		height: 16px;
		border-radius: 50%;
		background-color: var(--accent, #89b4fa);
		cursor: pointer;
		transition: background-color var(--transition-fast, 150ms ease);
	}

	.slider-input::-webkit-slider-thumb:hover {
		background-color: var(--accent-hover, #74a8f7);
	}

	.slider-input::-moz-range-thumb {
		width: 16px;
		height: 16px;
		border: none;
		border-radius: 50%;
		background-color: var(--accent, #89b4fa);
		cursor: pointer;
	}

	.slider-input:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
</style>
