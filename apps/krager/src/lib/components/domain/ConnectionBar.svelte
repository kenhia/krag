<!--
  ConnectionBar.svelte — Connection management header bar
  
  Host/port inputs + Connect/Disconnect button + status badge.
  Includes health polling $effect that runs while connected.
-->
<script lang="ts">
	import { onMount } from "svelte";
	import Button from "$lib/components/ui/Button.svelte";
	import Input from "$lib/components/ui/Input.svelte";
	import Spinner from "$lib/components/ui/Spinner.svelte";
	import {
		connection,
		setConnectionTarget,
		setConnected,
		setDisconnected,
		setConnectionError,
	} from "$lib/state/connection.svelte";
	import { getHealth, getModes } from "$lib/services/kragd-client";
	import { setBaseUrl } from "$lib/services/kragd-client";
	import { addToast } from "$lib/state/notifications.svelte";
	import { handleKragdError } from "$lib/utils/errors";
	import { setModes, setModesLoading, setModesError, clearModes } from "$lib/state/modes.svelte";

	let hostInput = $state(connection.host);
	let portInput = $state(String(connection.port));
	let connecting = $state(false);

	const POLL_INTERVAL = 5000;
	let pollTimer: ReturnType<typeof setInterval> | null = null;

	/** Status badge display config */
	const statusConfig = {
		connected: { color: "var(--success, #a6e3a1)", label: "Connected" },
		disconnected: { color: "var(--error, #f38ba8)", label: "Disconnected" },
		error: { color: "var(--warning, #f9e2af)", label: "Error" },
	} as const;

	async function checkHealth(): Promise<boolean> {
		try {
			const health = await getHealth(connection.host, connection.port);
			setConnected(health.version);
			setBaseUrl(`http://${connection.host}:${connection.port}`);
			return true;
		} catch (e) {
			const detail = e instanceof Error ? e.message : String(e);
			if (connection.status === "connected") {
				setDisconnected();
				addToast("Lost connection to kragd", "warning");
			} else {
				setConnectionError(detail || "Cannot reach kragd");
			}
			return false;
		}
	}

	function startPolling() {
		stopPolling();
		pollTimer = setInterval(async () => {
			await checkHealth();
		}, POLL_INTERVAL);
	}

	function stopPolling() {
		if (pollTimer !== null) {
			clearInterval(pollTimer);
			pollTimer = null;
		}
	}

	async function handleConnect() {
		const port = Number.parseInt(portInput, 10);
		if (Number.isNaN(port) || port < 1 || port > 65535) {
			addToast("Invalid port number", "error");
			return;
		}

		connecting = true;
		setConnectionTarget(hostInput, port);

		const ok = await checkHealth();
		connecting = false;

		if (ok) {
			addToast(`Connected to kragd v${connection.version}`, "success");
			startPolling();
			fetchModes();
		}
	}

	function handleDisconnect() {
		stopPolling();
		setDisconnected();
		clearModes();
		addToast("Disconnected from kragd", "info");
	}

	async function fetchModes() {
		setModesLoading();
		try {
			const res = await getModes();
			setModes(res.modes);
		} catch (e) {
			const msg = handleKragdError(e);
			setModesError(msg);
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === "Enter" && connection.status !== "connected") {
			handleConnect();
		}
	}

	// Cleanup on component destroy
	onMount(() => {
		return () => stopPolling();
	});

	// Restart polling when connection status changes to 'connected' externally
	$effect(() => {
		if (connection.status === "connected" && pollTimer === null && !connecting) {
			startPolling();
		} else if (connection.status !== "connected") {
			stopPolling();
		}
	});

	const isConnected = $derived(connection.status === "connected");
	const statusStyle = $derived(statusConfig[connection.status]);
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions a11y_no_static_element_interactions -->
<header class="connection-bar" onkeydown={handleKeydown}>
	<span class="app-title">krager</span>

	<div class="connection-controls">
		<div class="input-group">
			<Input
				value={hostInput}
				placeholder="hostname"
				disabled={isConnected || connecting}
				oninput={(e) => { hostInput = (e.target as HTMLInputElement).value; }}
			/>
		</div>
		<span class="port-separator">:</span>
		<div class="input-group port-input">
			<Input
				value={portInput}
				placeholder="port"
				disabled={isConnected || connecting}
				oninput={(e) => { portInput = (e.target as HTMLInputElement).value; }}
			/>
		</div>

		{#if isConnected}
			<Button label="Disconnect" variant="secondary" onclick={handleDisconnect} />
		{:else}
			<Button label="Connect" variant="primary" onclick={handleConnect} loading={connecting} />
		{/if}
	</div>

	<div class="status-badge" aria-live="polite">
		{#if connecting}
			<Spinner size="sm" />
			<span class="status-label">Connecting...</span>
		{:else}
			<span class="status-dot" style:background-color={statusStyle.color}></span>
			<span class="status-label">{statusStyle.label}</span>
			{#if connection.version && isConnected}
				<span class="version-tag">v{connection.version}</span>
			{/if}
		{/if}
	</div>

	{#if connection.errorMsg && connection.status === "error"}
		<span class="error-msg" title={connection.errorMsg}>{connection.errorMsg}</span>
	{/if}
</header>

<style>
	.connection-bar {
		display: flex;
		align-items: center;
		gap: var(--space-md, 16px);
		padding: var(--space-sm, 8px) var(--space-md, 16px);
		background-color: var(--bg-elevated, #1a1b26);
		border-bottom: 1px solid var(--border, #45475a);
		flex-shrink: 0;
	}

	.app-title {
		font-weight: 700;
		font-size: 1rem;
		color: var(--accent, #89b4fa);
		letter-spacing: 0.02em;
		flex-shrink: 0;
	}

	.connection-controls {
		display: flex;
		align-items: center;
		gap: var(--space-sm, 8px);
		flex: 1;
		max-width: 500px;
	}

	.input-group {
		flex: 1;
		min-width: 120px;
	}

	.port-input {
		max-width: 80px;
		flex: 0 0 80px;
	}

	.port-separator {
		color: var(--fg-muted, #a6adc8);
		font-weight: 600;
		flex-shrink: 0;
	}

	.status-badge {
		display: flex;
		align-items: center;
		gap: var(--space-sm, 8px);
		flex-shrink: 0;
		margin-left: auto;
	}

	.status-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.status-label {
		font-size: 0.8rem;
		color: var(--fg-muted, #a6adc8);
	}

	.version-tag {
		font-size: 0.7rem;
		color: var(--fg-muted, #a6adc8);
		opacity: 0.7;
		font-family: var(--font-mono, monospace);
	}

	.error-msg {
		font-size: 0.75rem;
		color: var(--error, #f38ba8);
		flex: 0 1 auto;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 350px;
	}
</style>
