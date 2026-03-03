import { describe, it, expect, beforeEach } from "vitest";
import {
	modesState,
	setSelected,
	clearModes,
	setModes,
	setModesLoading,
	setModesError,
} from "./modes.svelte";
import type { ModeInfo } from "$lib/types";

const sampleModes: ModeInfo[] = [
	{ name: "default", description: "Default mode", collections: ["main"], llm_slot: "text", preset: "standard" },
	{ name: "code", description: "Code mode", collections: ["code"], llm_slot: "code", preset: "code" },
];

describe("modes.svelte", () => {
	beforeEach(() => {
		clearModes();
	});

	it("starts with empty state", () => {
		expect(modesState.available).toHaveLength(0);
		expect(modesState.selected).toBeNull();
		expect(modesState.loading).toBe(false);
		expect(modesState.error).toBeNull();
	});

	describe("setModes", () => {
		it("populates available modes", () => {
			setModes(sampleModes);
			expect(modesState.available).toHaveLength(2);
			expect(modesState.available[0].name).toBe("default");
			expect(modesState.available[1].name).toBe("code");
		});

		it("clears loading and error", () => {
			setModesLoading();
			setModes(sampleModes);
			expect(modesState.loading).toBe(false);
			expect(modesState.error).toBeNull();
		});

		it("replaces existing modes", () => {
			setModes(sampleModes);
			setModes([{ name: "docs", description: "Docs mode", collections: ["docs"], llm_slot: "text", preset: "docs" }]);
			expect(modesState.available).toHaveLength(1);
			expect(modesState.available[0].name).toBe("docs");
		});
	});

	describe("setSelected", () => {
		it("sets selected mode name", () => {
			setSelected("code");
			expect(modesState.selected).toBe("code");
		});

		it("can set to null (default mode)", () => {
			setSelected("code");
			setSelected(null);
			expect(modesState.selected).toBeNull();
		});
	});

	describe("clearModes", () => {
		it("resets all state", () => {
			setModes(sampleModes);
			setSelected("code");
			clearModes();
			expect(modesState.available).toHaveLength(0);
			expect(modesState.selected).toBeNull();
			expect(modesState.loading).toBe(false);
			expect(modesState.error).toBeNull();
		});
	});

	describe("setModesLoading", () => {
		it("sets loading state", () => {
			setModesLoading();
			expect(modesState.loading).toBe(true);
			expect(modesState.error).toBeNull();
		});
	});

	describe("setModesError", () => {
		it("sets error and clears loading", () => {
			setModesLoading();
			setModesError("Failed to fetch modes");
			expect(modesState.loading).toBe(false);
			expect(modesState.error).toBe("Failed to fetch modes");
		});
	});
});
