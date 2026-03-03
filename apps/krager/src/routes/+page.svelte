<!--
  +page.svelte — Main multi-panel layout
  
  Multi-panel layout: ConnectionBar header, sidebar nav, content area.
  Panels are wired to domain components as they are built.
-->
<script lang="ts">
	import ConnectionBar from "$lib/components/domain/ConnectionBar.svelte";
	import SystemStatus from "$lib/components/domain/SystemStatus.svelte";
	import QueryPanel from "$lib/components/domain/QueryPanel.svelte";
	import TranscriptView from "$lib/components/domain/TranscriptView.svelte";
	import ModeSelector from "$lib/components/domain/ModeSelector.svelte";
	import IndexPanel from "$lib/components/domain/IndexPanel.svelte";
	import DebugPanel from "$lib/components/domain/DebugPanel.svelte";
	import { connection } from "$lib/state/connection.svelte";
	import { modesState } from "$lib/state/modes.svelte";

	let activePanel = $state<string>("query");

	const panels = [
		{ id: "query", label: "Query", icon: "💬" },
		{ id: "index", label: "Index", icon: "📑" },
		{ id: "system", label: "System", icon: "⚙" },
		{ id: "debug", label: "Debug", icon: "🔍" },
	] as const;

	const isConnected = $derived(connection.status === "connected");
</script>

<div class="app-layout">
	<ConnectionBar />

	<div class="main-area">
		<!-- Sidebar navigation -->
		<nav class="sidebar" aria-label="Main navigation">
			{#each panels as panel}
				<button
					class="nav-item"
					class:active={activePanel === panel.id}
					onclick={() => (activePanel = panel.id)}
					aria-current={activePanel === panel.id ? "page" : undefined}
				>
					<span class="nav-icon">{panel.icon}</span>
					<span class="nav-label">{panel.label}</span>
				</button>
			{/each}
		</nav>

		<!-- Main content area -->
		<main class="content">
			{#if activePanel === "query"}
				<div class="query-layout">
					<QueryPanel selectedMode={modesState.selected}>
						{#snippet modeSelector()}
							<ModeSelector />
						{/snippet}
					</QueryPanel>
					<TranscriptView />
				</div>
			{:else if activePanel === "index"}
				<IndexPanel />
			{:else if activePanel === "system"}
				{#if isConnected}
					<SystemStatus />
				{:else}
					<div class="panel-placeholder">
						<h2>System Status</h2>
						<p class="text-muted">Connect to kragd to view system status.</p>
					</div>
				{/if}
			{:else if activePanel === "debug"}
				{#if isConnected}
					<DebugPanel />
				{:else}
					<div class="panel-placeholder">
						<h2>Debug Tools</h2>
						<p class="text-muted">Connect to kragd to use debug tools.</p>
					</div>
				{/if}
			{/if}
		</main>
	</div>
</div>

<style>
	.app-layout {
		display: flex;
		flex-direction: column;
		height: 100vh;
		overflow: hidden;
	}

	.main-area {
		display: flex;
		flex: 1;
		overflow: hidden;
	}

	.sidebar {
		flex-shrink: 0;
		width: 60px;
		background-color: var(--bg-elevated);
		border-right: 1px solid var(--border);
		display: flex;
		flex-direction: column;
		padding: var(--space-sm) 0;
		gap: var(--space-xs);
	}

	.nav-item {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2px;
		padding: var(--space-sm) var(--space-xs);
		border: none;
		background: none;
		color: var(--fg-muted);
		cursor: pointer;
		border-radius: var(--radius-sm);
		margin: 0 var(--space-xs);
		font-size: 0.65rem;
		transition: background-color var(--transition-fast), color var(--transition-fast);
	}

	.nav-item:hover {
		background-color: var(--surface-hover);
		color: var(--fg);
	}

	.nav-item.active {
		background-color: var(--surface);
		color: var(--accent);
	}

	.nav-icon {
		font-size: 1.25rem;
		line-height: 1;
	}

	.nav-label {
		line-height: 1;
	}

	.content {
		flex: 1;
		overflow: hidden;
		padding: var(--space-lg);
		display: flex;
		flex-direction: column;
	}

	.query-layout {
		display: flex;
		flex-direction: column;
		height: 100%;
		gap: var(--space-md);
		min-height: 0;
	}

	.panel-placeholder {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		height: 100%;
		gap: var(--space-sm);
	}

	.panel-placeholder h2 {
		font-size: 1.25rem;
		font-weight: 600;
	}
</style>
