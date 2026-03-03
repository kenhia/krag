<script lang="ts">
	import "../app.css";
	import ToastContainer from "$lib/components/ui/ToastContainer.svelte";
	import { appTheme, initTheme } from "$lib/state/theme.svelte";
	import { onMount } from "svelte";

	let { children } = $props();

	onMount(() => {
		let cleanup: (() => void) | undefined;

		initTheme().then((fn) => {
			cleanup = fn;
		});

		return () => {
			cleanup?.();
		};
	});

	// Reactively set data-theme on document root
	$effect(() => {
		if (typeof document !== "undefined") {
			document.documentElement.setAttribute("data-theme", appTheme.current);
		}
	});
</script>

{@render children()}
<ToastContainer />
