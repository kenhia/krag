import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import Toggle from "./Toggle.svelte";

describe("Toggle", () => {
	it("renders in off state by default", () => {
		render(Toggle, { props: { checked: false } });
		const toggle = screen.getByRole("switch");
		expect(toggle).toHaveAttribute("aria-checked", "false");
	});

	it("renders in on state when checked is true", () => {
		render(Toggle, { props: { checked: true } });
		const toggle = screen.getByRole("switch");
		expect(toggle).toHaveAttribute("aria-checked", "true");
	});

	it("calls onchange with toggled value on click", async () => {
		const onchange = vi.fn();
		render(Toggle, { props: { checked: false, onchange } });

		await fireEvent.click(screen.getByRole("switch"));
		expect(onchange).toHaveBeenCalledWith(true);
	});

	it("toggles from on to off on click", async () => {
		const onchange = vi.fn();
		render(Toggle, { props: { checked: true, onchange } });

		await fireEvent.click(screen.getByRole("switch"));
		expect(onchange).toHaveBeenCalledWith(false);
	});

	it("renders disabled state", () => {
		render(Toggle, { props: { checked: false, disabled: true } });
		const toggle = screen.getByRole("switch");
		expect(toggle).toHaveAttribute("aria-disabled", "true");
	});

	it("does not call onchange when disabled", async () => {
		const onchange = vi.fn();
		render(Toggle, {
			props: { checked: false, disabled: true, onchange },
		});

		await fireEvent.click(screen.getByRole("switch"));
		expect(onchange).not.toHaveBeenCalled();
	});

	it("renders label when provided", () => {
		render(Toggle, { props: { checked: false, label: "Debug" } });
		expect(screen.getByText("Debug")).toBeInTheDocument();
	});

	it("toggles on Space key", async () => {
		const onchange = vi.fn();
		render(Toggle, { props: { checked: false, onchange } });

		await fireEvent.keyDown(screen.getByRole("switch"), { key: " " });
		expect(onchange).toHaveBeenCalledWith(true);
	});
});
