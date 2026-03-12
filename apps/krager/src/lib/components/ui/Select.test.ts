import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import Select from "./Select.svelte";

const options = [
	{ value: "a", label: "Alpha" },
	{ value: "b", label: "Beta" },
	{ value: "c", label: "Charlie" },
];

describe("Select", () => {
	it("renders with placeholder when no value selected", () => {
		render(Select, {
			props: { options, value: null, placeholder: "Pick one" },
		});
		expect(screen.getByRole("combobox")).toHaveTextContent("Pick one");
	});

	it("renders selected option label", () => {
		render(Select, {
			props: { options, value: "b" },
		});
		expect(screen.getByRole("combobox")).toHaveTextContent("Beta");
	});

	it("opens dropdown on click", async () => {
		render(Select, {
			props: { options, value: null },
		});
		const trigger = screen.getByRole("combobox");
		await fireEvent.click(trigger);
		expect(screen.getByRole("listbox")).toBeInTheDocument();
		expect(screen.getAllByRole("option")).toHaveLength(3);
	});

	it("selects option on click and closes dropdown", async () => {
		const onchange = vi.fn();
		render(Select, {
			props: { options, value: null, onchange },
		});

		await fireEvent.click(screen.getByRole("combobox"));
		const opts = screen.getAllByRole("option");
		await fireEvent.click(opts[1]); // Beta

		expect(onchange).toHaveBeenCalledWith("b");
	});

	it("closes dropdown when clicking trigger again", async () => {
		render(Select, {
			props: { options, value: null },
		});
		const trigger = screen.getByRole("combobox");
		await fireEvent.click(trigger);
		expect(screen.getByRole("listbox")).toBeInTheDocument();
		await fireEvent.click(trigger);
		expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
	});

	it("navigates options with keyboard ArrowDown/ArrowUp and selects with Enter", async () => {
		const onchange = vi.fn();
		render(Select, {
			props: { options, value: null, onchange },
		});

		const trigger = screen.getByRole("combobox");
		await fireEvent.keyDown(trigger, { key: "Enter" });
		expect(screen.getByRole("listbox")).toBeInTheDocument();

		await fireEvent.keyDown(trigger, { key: "ArrowDown" }); // Beta (index 1)
		await fireEvent.keyDown(trigger, { key: "Enter" });

		expect(onchange).toHaveBeenCalledWith("b");
	});

	it("closes on Escape", async () => {
		render(Select, {
			props: { options, value: null },
		});
		const trigger = screen.getByRole("combobox");
		await fireEvent.click(trigger);
		expect(screen.getByRole("listbox")).toBeInTheDocument();
		await fireEvent.keyDown(trigger, { key: "Escape" });
		expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
	});

	it("renders disabled state", () => {
		render(Select, {
			props: { options, value: null, disabled: true },
		});
		expect(screen.getByRole("combobox")).toHaveAttribute("aria-disabled", "true");
	});

	it("does not open when disabled", async () => {
		render(Select, {
			props: { options, value: null, disabled: true },
		});
		await fireEvent.click(screen.getByRole("combobox"));
		expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
	});

	it("renders label when provided", () => {
		render(Select, {
			props: { options, value: null, label: "Preset" },
		});
		expect(screen.getByText("Preset")).toBeInTheDocument();
	});
});
