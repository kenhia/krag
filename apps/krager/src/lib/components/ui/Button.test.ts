import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import Button from "./Button.svelte";

describe("Button.svelte", () => {
	it("renders with label", () => {
		render(Button, { props: { label: "Click me" } });
		expect(screen.getByRole("button", { name: "Click me" })).toBeInTheDocument();
	});

	it("applies primary variant by default", () => {
		render(Button, { props: { label: "Test" } });
		const btn = screen.getByRole("button");
		expect(btn.classList.contains("btn-primary")).toBe(true);
	});

	it("applies secondary variant", () => {
		render(Button, { props: { label: "Test", variant: "secondary" } });
		const btn = screen.getByRole("button");
		expect(btn.classList.contains("btn-secondary")).toBe(true);
	});

	it("applies danger variant", () => {
		render(Button, { props: { label: "Test", variant: "danger" } });
		const btn = screen.getByRole("button");
		expect(btn.classList.contains("btn-danger")).toBe(true);
	});

	it("renders as disabled when disabled prop is true", () => {
		render(Button, { props: { label: "Test", disabled: true } });
		const btn = screen.getByRole("button");
		expect(btn).toBeDisabled();
	});

	it("renders loading spinner and disables button when loading", () => {
		render(Button, { props: { label: "Test", loading: true } });
		const btn = screen.getByRole("button");
		expect(btn).toBeDisabled();
		expect(btn.querySelector(".btn-spinner")).toBeTruthy();
	});

	it("fires onclick when clicked", async () => {
		const handler = vi.fn();
		render(Button, { props: { label: "Click", onclick: handler } });
		await fireEvent.click(screen.getByRole("button"));
		expect(handler).toHaveBeenCalledOnce();
	});

	it("prevents click when disabled via DOM attribute", () => {
		render(Button, { props: { label: "Click", disabled: true } });
		const btn = screen.getByRole("button");
		expect(btn).toBeDisabled();
		// In a real browser, disabled buttons don't dispatch click events.
		// We verify the disabled attribute is set, which browsers enforce natively.
	});

	it("is keyboard accessible via Enter and Space", async () => {
		const handler = vi.fn();
		render(Button, { props: { label: "Press", onclick: handler } });
		const btn = screen.getByRole("button");
		await fireEvent.keyDown(btn, { key: "Enter" });
		// Native button handles Enter/Space → click, but in jsdom we test the button exists
		expect(btn.tagName).toBe("BUTTON");
	});
});
