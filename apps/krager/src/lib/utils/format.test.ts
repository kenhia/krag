import { describe, expect, it } from "vitest";
import { formatDuration, formatFileSize, formatTimestamp, formatUptime } from "./format";

describe("format utilities", () => {
	describe("formatDuration", () => {
		it("formats zero", () => {
			expect(formatDuration(0)).toBe("0ms");
		});

		it("formats negative as 0ms", () => {
			expect(formatDuration(-100)).toBe("0ms");
		});

		it("formats milliseconds", () => {
			expect(formatDuration(150)).toBe("150ms");
			expect(formatDuration(999)).toBe("999ms");
		});

		it("formats seconds", () => {
			expect(formatDuration(1000)).toBe("1.0s");
			expect(formatDuration(2500)).toBe("2.5s");
			expect(formatDuration(59999)).toBe("60.0s");
		});

		it("formats minutes and seconds", () => {
			expect(formatDuration(60000)).toBe("1m");
			expect(formatDuration(90000)).toBe("1m 30s");
		});

		it("formats hours and minutes", () => {
			expect(formatDuration(3600000)).toBe("1h");
			expect(formatDuration(8100000)).toBe("2h 15m");
		});

		it("formats very large values", () => {
			expect(formatDuration(86400000)).toBe("24h");
		});
	});

	describe("formatTimestamp", () => {
		it("formats a valid date", () => {
			const d = new Date("2026-03-01T14:30:05.000Z");
			const result = formatTimestamp(d);
			// Result depends on locale, just check it's not the fallback
			expect(result).not.toBe("—");
			expect(result.length).toBeGreaterThan(0);
		});

		it("returns dash for null", () => {
			expect(formatTimestamp(null)).toBe("—");
		});

		it("returns dash for undefined", () => {
			expect(formatTimestamp(undefined)).toBe("—");
		});

		it("returns dash for invalid date", () => {
			expect(formatTimestamp(new Date("not a date"))).toBe("—");
		});
	});

	describe("formatFileSize", () => {
		it("formats zero bytes", () => {
			expect(formatFileSize(0)).toBe("0 B");
		});

		it("formats negative as 0 B", () => {
			expect(formatFileSize(-1)).toBe("0 B");
		});

		it("formats bytes", () => {
			expect(formatFileSize(100)).toBe("100 B");
			expect(formatFileSize(1023)).toBe("1023 B");
		});

		it("formats kilobytes", () => {
			expect(formatFileSize(1024)).toBe("1.0 KB");
			expect(formatFileSize(1536)).toBe("1.5 KB");
		});

		it("formats megabytes", () => {
			expect(formatFileSize(1024 * 1024)).toBe("1.0 MB");
			expect(formatFileSize(2.3 * 1024 * 1024)).toBe("2.3 MB");
		});

		it("formats gigabytes", () => {
			expect(formatFileSize(1024 * 1024 * 1024)).toBe("1.0 GB");
		});

		it("formats very large values", () => {
			expect(formatFileSize(1024 * 1024 * 1024 * 1024)).toBe("1.0 TB");
		});
	});

	describe("formatUptime", () => {
		it("formats zero", () => {
			expect(formatUptime(0)).toBe("0s");
		});

		it("formats negative as 0s", () => {
			expect(formatUptime(-10)).toBe("0s");
		});

		it("formats seconds", () => {
			expect(formatUptime(45)).toBe("45s");
		});

		it("formats minutes and seconds", () => {
			expect(formatUptime(330)).toBe("5m 30s");
			expect(formatUptime(60)).toBe("1m");
		});

		it("formats hours and minutes", () => {
			expect(formatUptime(8100)).toBe("2h 15m");
			expect(formatUptime(3600)).toBe("1h");
		});

		it("formats days and hours", () => {
			expect(formatUptime(86400)).toBe("1d");
			expect(formatUptime(129600)).toBe("1d 12h");
		});

		it("formats very large values", () => {
			expect(formatUptime(604800)).toBe("7d");
		});
	});

	// ─── Edge-case tests (T076) ────────────────────────────────

	describe("edge cases", () => {
		it("formatDuration handles NaN gracefully", () => {
			expect(formatDuration(Number.NaN)).toBe("0ms");
		});

		it("formatDuration handles Infinity", () => {
			// Infinity / 1000 = Infinity → should not crash
			const result = formatDuration(Number.POSITIVE_INFINITY);
			expect(typeof result).toBe("string");
		});

		it("formatDuration handles sub-millisecond", () => {
			expect(formatDuration(0.5)).toBe("1ms");
		});

		it("formatDuration handles boundary at 1000ms", () => {
			expect(formatDuration(999)).toBe("999ms");
			expect(formatDuration(1000)).toBe("1.0s");
		});

		it("formatDuration handles exact 60s boundary", () => {
			expect(formatDuration(60000)).toBe("1m");
		});

		it("formatDuration handles exact 1h boundary", () => {
			expect(formatDuration(3600000)).toBe("1h");
		});

		it("formatFileSize handles fractional bytes", () => {
			expect(formatFileSize(0.5)).toBe("0.5 B");
		});

		it("formatFileSize handles very large TB values", () => {
			const petabyte = 1024 ** 5;
			const result = formatFileSize(petabyte);
			expect(result).toContain("TB");
		});

		it("formatUptime handles fractional seconds", () => {
			expect(formatUptime(0.5)).toBe("1s");
		});

		it("formatUptime handles NaN gracefully", () => {
			expect(formatUptime(Number.NaN)).toBe("0s");
		});

		it("formatTimestamp handles Date at epoch", () => {
			const d = new Date(0);
			const result = formatTimestamp(d);
			expect(result).not.toBe("—");
		});

		it("formatTimestamp handles non-Date object", () => {
			// @ts-expect-error — intentionally testing bad input
			expect(formatTimestamp("not a date")).toBe("—");
		});
	});
});
