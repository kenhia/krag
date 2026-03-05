<!--
  Spinner.svelte — CSS-only loading indicator
  
  Props: size ('sm' | 'md' | 'lg')
-->
<script lang="ts">
interface Props {
	size?: "sm" | "md" | "lg";
}

let { size = "md" }: Props = $props();
</script>

<span class="spinner spinner-{size}" role="status" aria-label="Loading">
	<span class="sr-only">Loading...</span>
</span>

<style>
	.spinner {
		display: inline-block;
		border: 2px solid var(--border, #45475a);
		border-top-color: var(--accent, #89b4fa);
		border-radius: 50%;
		animation: spin 600ms linear infinite;
	}

	.spinner-sm {
		width: 16px;
		height: 16px;
		border-width: 2px;
	}

	.spinner-md {
		width: 24px;
		height: 24px;
		border-width: 2.5px;
	}

	.spinner-lg {
		width: 36px;
		height: 36px;
		border-width: 3px;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		white-space: nowrap;
		border-width: 0;
	}
</style>
