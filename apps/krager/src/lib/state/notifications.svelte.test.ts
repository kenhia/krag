import { beforeEach, describe, expect, it } from "vitest";
import { addToast, clearToasts, dismissToast, notifications } from "./notifications.svelte";

describe("notifications.svelte", () => {
	beforeEach(() => {
		clearToasts();
	});

	it("starts with empty toasts array", () => {
		expect(notifications.toasts).toHaveLength(0);
	});

	describe("addToast", () => {
		it("adds a toast with default duration", () => {
			const id = addToast("Test message", "info");
			expect(notifications.toasts).toHaveLength(1);
			expect(notifications.toasts[0].id).toBe(id);
			expect(notifications.toasts[0].message).toBe("Test message");
			expect(notifications.toasts[0].type).toBe("info");
			expect(notifications.toasts[0].duration).toBe(5000);
		});

		it("adds a toast with custom duration", () => {
			addToast("Error!", "error", 10000);
			expect(notifications.toasts[0].duration).toBe(10000);
		});

		it("accumulates multiple toasts", () => {
			addToast("First", "info");
			addToast("Second", "warning");
			addToast("Third", "success");
			expect(notifications.toasts).toHaveLength(3);
		});

		it("generates unique IDs", () => {
			const id1 = addToast("A", "info");
			const id2 = addToast("B", "info");
			expect(id1).not.toBe(id2);
		});
	});

	describe("dismissToast", () => {
		it("removes a toast by ID", () => {
			const id = addToast("Remove me", "info");
			expect(notifications.toasts).toHaveLength(1);
			dismissToast(id);
			expect(notifications.toasts).toHaveLength(0);
		});

		it("does nothing if ID not found", () => {
			addToast("Keep me", "info");
			dismissToast("nonexistent");
			expect(notifications.toasts).toHaveLength(1);
		});

		it("removes only the specified toast", () => {
			const id1 = addToast("First", "info");
			addToast("Second", "warning");
			dismissToast(id1);
			expect(notifications.toasts).toHaveLength(1);
			expect(notifications.toasts[0].message).toBe("Second");
		});
	});

	describe("clearToasts", () => {
		it("removes all toasts", () => {
			addToast("A", "info");
			addToast("B", "error");
			clearToasts();
			expect(notifications.toasts).toHaveLength(0);
		});
	});
});
