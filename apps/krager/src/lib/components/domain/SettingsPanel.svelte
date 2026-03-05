<!--
  SettingsPanel.svelte — Centralized settings page.

  4 sections: Connection, Query, Critic, Display.
  All changes apply immediately (no save button).
-->
<script lang="ts">
import Input from "$lib/components/ui/Input.svelte";
import Select from "$lib/components/ui/Select.svelte";
import Slider from "$lib/components/ui/Slider.svelte";
import Toggle from "$lib/components/ui/Toggle.svelte";
import { connection, saveConnectionToConfig } from "$lib/state/connection.svelte";
import {
	queryState,
	setCriticCutOff,
	setCriticEnabled,
	setIncludeDebug,
	setPreset,
	setShowSources,
	setTopK,
} from "$lib/state/query.svelte";
import { setOpacity, setTheme, settingsState } from "$lib/state/settings.svelte";
import type { PresetName } from "$lib/types";
import { PRESET_OPTIONS } from "$lib/types";

const THEME_OPTIONS = [
	{ value: "light", label: "Light" },
	{ value: "dark", label: "Dark" },
];

function handleHostChange(value: string) {
	connection.host = value;
	saveConnectionToConfig();
}

function handlePortChange(value: string) {
	const p = parseInt(value, 10);
	if (!isNaN(p) && p >= 1 && p <= 65535) {
		connection.port = p;
		saveConnectionToConfig();
	}
}
</script>

<div class="settings-panel">
	<h2 class="settings-title">Settings</h2>

	<!-- Connection -->
	<section class="settings-section">
		<h3 class="section-heading">Connection</h3>
		<div class="setting-row">
			<Input
				value={connection.host}
				label="Host"
				placeholder="localhost"
				oninput={(e) => handleHostChange((e.currentTarget as HTMLInputElement).value)}
			/>
		</div>
		<div class="setting-row">
			<Input
				value={String(connection.port)}
				label="Port"
				placeholder="8742"
				type="number"
				oninput={(e) => handlePortChange((e.currentTarget as HTMLInputElement).value)}
			/>
		</div>
	</section>

	<!-- Query -->
	<section class="settings-section">
		<h3 class="section-heading">Query</h3>
		<div class="setting-row">
			<Slider
				value={queryState.top_k ?? 10}
				min={1}
				max={100}
				step={1}
				label="Top K"
				onchange={(v) => setTopK(v)}
			/>
		</div>
		<div class="setting-row">
			<Select
				options={PRESET_OPTIONS}
				value={queryState.preset}
				placeholder="Server default"
				label="Preset"
				onchange={(v) => setPreset(v as PresetName)}
			/>
		</div>
		<div class="setting-row toggles">
			<Toggle
				checked={queryState.include_debug}
				onchange={(v) => setIncludeDebug(v)}
				label="Debug"
			/>
			<Toggle
				checked={queryState.show_sources}
				onchange={(v) => setShowSources(v)}
				label="Sources"
			/>
		</div>
	</section>

	<!-- Critic -->
	<section class="settings-section">
		<h3 class="section-heading">Critic</h3>
		<div class="setting-row">
			<Toggle
				checked={queryState.critic_enabled}
				onchange={(v) => setCriticEnabled(v)}
				label="Critic"
			/>
		</div>
		{#if queryState.critic_enabled}
			<div class="setting-row">
				<Slider
					value={queryState.critic_cut_off}
					min={0}
					max={5}
					step={1}
					label="Cut-off"
					onchange={(v) => setCriticCutOff(v)}
				/>
			</div>
		{/if}
	</section>

	<!-- Display -->
	<section class="settings-section">
		<h3 class="section-heading">Display</h3>
		<div class="setting-row">
			<Slider
				value={settingsState.opacity}
				min={0.3}
				max={1}
				step={0.05}
				label="Opacity"
				onchange={(v) => setOpacity(v)}
			/>
		</div>
		<div class="setting-row">
			<Select
				options={THEME_OPTIONS}
				value={settingsState.theme}
				placeholder="Follow OS"
				label="Theme"
				onchange={(v) => setTheme(v as "light" | "dark" | null)}
			/>
		</div>
	</section>
</div>

<style>
	.settings-panel {
		display: flex;
		flex-direction: column;
		gap: var(--space-lg, 24px);
		max-width: 480px;
		overflow-y: auto;
	}

	.settings-title {
		font-size: 1.25rem;
		font-weight: 600;
		margin: 0;
	}

	.settings-section {
		display: flex;
		flex-direction: column;
		gap: var(--space-sm, 8px);
		padding: var(--space-md, 16px);
		background-color: var(--surface, #313244);
		border: 1px solid var(--border, #45475a);
		border-radius: var(--radius-md, 8px);
	}

	.section-heading {
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--fg-muted, #a6adc8);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin: 0 0 var(--space-xs, 4px);
	}

	.setting-row {
		display: flex;
		flex-direction: column;
		gap: var(--space-xs, 4px);
	}

	.toggles {
		flex-direction: row;
		flex-wrap: wrap;
		gap: var(--space-md, 16px);
	}
</style>
