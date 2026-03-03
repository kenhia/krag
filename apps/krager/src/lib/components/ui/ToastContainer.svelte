<!--
  ToastContainer.svelte — Renders all active toast notifications
  
  Placed in +layout.svelte to be globally available.
  Reads from notifications state and auto-dismisses toasts.
-->
<script lang="ts">
	import Toast from "./Toast.svelte";
	import { notifications, dismissToast } from "$lib/state/notifications.svelte";
</script>

{#if notifications.toasts.length > 0}
	<div class="toast-container" aria-label="Notifications">
		{#each notifications.toasts as toast (toast.id)}
			<Toast
				id={toast.id}
				message={toast.message}
				type={toast.type}
				duration={toast.duration}
				onDismiss={dismissToast}
			/>
		{/each}
	</div>
{/if}

<style>
	.toast-container {
		position: fixed;
		top: var(--space-md, 16px);
		right: var(--space-md, 16px);
		z-index: 9999;
		display: flex;
		flex-direction: column;
		gap: var(--space-sm, 8px);
		pointer-events: none;
	}
</style>
