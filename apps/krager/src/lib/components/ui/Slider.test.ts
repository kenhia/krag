import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import Slider from "./Slider.svelte";

describe("Slider", () => {
	it("renders with current value displayed", () => {
		render(Slider, { props: { value: 0.7, min: 0, max: 1, step: 0.05 } });
		const slider = screen.getByRole("slider");
		expect(slider).toHaveValue("0.7");
	});

	it("renders label when provided", () => {
		render(Slider, {
			props: { value: 5, min: 1, max: 10, step: 1, label: "Top K" },
		});
		expect(screen.getByText("Top K")).toBeInTheDocument();
	});

	it("displays value label", () => {
		render(Slider, {
			props: { value: 0.75, min: 0, max: 1, step: 0.05 },
		});
		expect(screen.getByText("0.75")).toBeInTheDocument();
	});

	it("calls onchange with new value on input", async () => {
		const onchange = vi.fn();
		render(Slider, {
			props: { value: 5, min: 1, max: 10, step: 1, onchange },
		});

		const slider = screen.getByRole("slider");
		await fireEvent.input(slider, { target: { value: "8" } });
		expect(onchange).toHaveBeenCalledWith(8);
	});

	it("respects min/max attributes", () => {
		render(Slider, {
			props: { value: 5, min: 1, max: 100, step: 1 },
		});
		const slider = screen.getByRole("slider");
		expect(slider).toHaveAttribute("min", "1");
		expect(slider).toHaveAttribute("max", "100");
	});

	it("respects step attribute", () => {
		render(Slider, {
			props: { value: 0.5, min: 0, max: 1, step: 0.05 },
		});
		const slider = screen.getByRole("slider");
		expect(slider).toHaveAttribute("step", "0.05");
	});

	it("renders disabled state", () => {
		render(Slider, {
			props: { value: 5, min: 1, max: 10, step: 1, disabled: true },
		});
		const slider = screen.getByRole("slider");
		expect(slider).toBeDisabled();
	});
});
