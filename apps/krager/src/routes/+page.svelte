<!--
  +page.svelte — Main multi-panel layout
  
  Multi-panel layout: ConnectionBar header, sidebar nav, content area.
  Panels are wired to domain components as they are built.
-->
<script lang="ts">
import { onMount } from "svelte";
import ConnectionBar from "$lib/components/domain/ConnectionBar.svelte";
import DebugPanel from "$lib/components/domain/DebugPanel.svelte";
import IndexPanel from "$lib/components/domain/IndexPanel.svelte";
import ModeSelector from "$lib/components/domain/ModeSelector.svelte";
import QueryAnswer from "$lib/components/domain/QueryAnswer.svelte";
import QueryPanel from "$lib/components/domain/QueryPanel.svelte";
import SettingsPanel from "$lib/components/domain/SettingsPanel.svelte";
import SystemStatus from "$lib/components/domain/SystemStatus.svelte";
import TranscriptView from "$lib/components/domain/TranscriptView.svelte";
import { destroyConfigStore, initConfigStore } from "$lib/services/config-store";
import { connection, initConnectionFromConfig } from "$lib/state/connection.svelte";
import { modesState } from "$lib/state/modes.svelte";
import { initQueryFromConfig, queryState } from "$lib/state/query.svelte";
import { initSettingsFromConfig, settingsState } from "$lib/state/settings.svelte";
import { transcript } from "$lib/state/transcript.svelte";

let activePanel = $state<string>("query");

const panels = [
	{ id: "query", label: "Query", icon: "💬" },
	{ id: "transcript", label: "Transcript", icon: "📝" },
	{ id: "index", label: "Index", icon: "📑" },
	{ id: "system", label: "System", icon: "⚙" },
	{ id: "settings", label: "Settings", icon: "🔧" },
	{ id: "debug", label: "Debug", icon: "🔍" },
] as const;

const isConnected = $derived(connection.status === "connected");

onMount(() => {
	initConfigStore().then(() => {
		initConnectionFromConfig();
		initQueryFromConfig();
		initSettingsFromConfig();
	});

	return () => {
		destroyConfigStore();
	};
});

// Apply window opacity reactively
$effect(() => {
	if (typeof document !== "undefined") {
		document.documentElement.style.opacity = String(settingsState.opacity);
	}
});
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
					{#if transcript.entries.length > 0}
						{@const latestEntry = transcript.entries[transcript.entries.length - 1]}
						<div class="query-answer-scroll">
							<QueryAnswer
								entry={latestEntry}
								criticEnabled={queryState.critic_enabled}
								criticCutOff={queryState.critic_cut_off}
								showSources={queryState.show_sources}
							/>
						</div>
					{/if}
				</div>
			{:else if activePanel === "transcript"}
				<TranscriptView />
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
			{:else if activePanel === "settings"}
				<SettingsPanel />
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

	.query-answer-scroll {
		flex: 1;
		overflow-y: auto;
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
