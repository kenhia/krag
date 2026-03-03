import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import Input from "./Input.svelte";

describe("Input.svelte", () => {
	it("renders with placeholder", () => {
		render(Input, { props: { value: "", placeholder: "Enter text..." } });
		expect(screen.getByPlaceholderText("Enter text...")).toBeInTheDocument();
	});

	it("renders with initial value", () => {
		render(Input, { props: { value: "hello" } });
		const input = screen.getByRole("textbox") as HTMLInputElement;
		expect(input.value).toBe("hello");
	});

	it("can be disabled", () => {
		render(Input, { props: { value: "", disabled: true } });
		const input = screen.getByRole("textbox");
		expect(input).toBeDisabled();
	});

	it("applies the specified type", () => {
		render(Input, { props: { value: "", type: "password" } });
		// password inputs don't have a "textbox" role
		const input = document.querySelector("input[type='password']");
		expect(input).toBeTruthy();
	});

	it("fires oninput event on user input", async () => {
		const handler = vi.fn();
		render(Input, { props: { value: "", oninput: handler } });
		const input = screen.getByRole("textbox");
		await fireEvent.input(input, { target: { value: "new text" } });
		expect(handler).toHaveBeenCalled();
	});

	it("renders a label when provided", () => {
		render(Input, { props: { value: "", label: "Email" } });
		expect(screen.getByLabelText("Email")).toBeInTheDocument();
	});
});
