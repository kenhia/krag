import { describe, it, expect, vi, beforeEach } from "vitest";
import { handleKragdError, requireConnection } from "./errors";
import { KragdError } from "$lib/types";

// Mock notifications state
const { mockAddToast } = vi.hoisted(() => ({
	mockAddToast: vi.fn(),
}));
vi.mock("$lib/state/notifications.svelte", () => ({
	addToast: mockAddToast,
}));

describe("errors utilities", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	describe("handleKragdError", () => {
		it("handles network error (status 0)", () => {
			const err = new KragdError(0, "Cannot reach kragd at localhost:11435");
			const msg = handleKragdError(err);

			expect(msg).toContain("Cannot reach kragd");
			expect(mockAddToast).toHaveBeenCalledWith(
				expect.stringContaining("Cannot reach kragd"),
				"warning",
			);
		});

		it("handles validation error (status 422)", () => {
			const err = new KragdError(422, "Validation error: query: too short");
			const msg = handleKragdError(err);

			expect(msg).toContain("Invalid request");
			expect(mockAddToast).toHaveBeenCalledWith(expect.stringContaining("Invalid request"), "error");
		});

		it("handles conflict error (status 409)", () => {
			const err = new KragdError(409, "Job already running");
			const msg = handleKragdError(err);

			expect(msg).toContain("Conflict");
			expect(mockAddToast).toHaveBeenCalledWith(expect.stringContaining("Conflict"), "error");
		});

		it("handles not ready error (status 503)", () => {
			const err = new KragdError(503, "LLM not loaded");
			const msg = handleKragdError(err);

			expect(msg).toContain("not ready");
			expect(mockAddToast).toHaveBeenCalledWith(expect.stringContaining("not ready"), "warning");
		});

		it("handles server error (status 500)", () => {
			const err = new KragdError(500, "Internal error");
			const msg = handleKragdError(err);

			expect(msg).toContain("Internal server error");
			expect(mockAddToast).toHaveBeenCalledWith(
				expect.stringContaining("Internal server error"),
				"error",
			);
		});

		it("handles unknown HTTP status", () => {
			const err = new KragdError(418, "I'm a teapot");
			const msg = handleKragdError(err);

			expect(msg).toBe("I'm a teapot");
			expect(mockAddToast).toHaveBeenCalledWith("I'm a teapot", "error");
		});

		it("handles generic Error", () => {
			const err = new Error("Something went wrong");
			const msg = handleKragdError(err);

			expect(msg).toBe("Something went wrong");
			expect(mockAddToast).toHaveBeenCalledWith("Something went wrong", "error");
		});

		it("handles non-Error unknown value", () => {
			const msg = handleKragdError("random string");

			expect(msg).toBe("An unexpected error occurred");
			expect(mockAddToast).toHaveBeenCalledWith("An unexpected error occurred", "error");
		});

		it("handles null", () => {
			const msg = handleKragdError(null);
			expect(msg).toBe("An unexpected error occurred");
		});

		it("returns the error message string", () => {
			const err = new KragdError(500, "Server error");
			const result = handleKragdError(err);
			expect(typeof result).toBe("string");
			expect(result.length).toBeGreaterThan(0);
		});
	});

	describe("requireConnection", () => {
		it("returns true when connected", () => {
			expect(requireConnection("connected")).toBe(true);
			expect(mockAddToast).not.toHaveBeenCalled();
		});

		it("returns false when disconnected and shows toast", () => {
			expect(requireConnection("disconnected")).toBe(false);
			expect(mockAddToast).toHaveBeenCalledWith("Not connected to kragd", "warning");
		});

		it("returns false when error status", () => {
			expect(requireConnection("error")).toBe(false);
			expect(mockAddToast).toHaveBeenCalled();
		});
	});
});
