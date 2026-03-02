/**
 * Syntax Highlighting Utility
 *
 * Lazy singleton Shiki highlighter with dark/light themes.
 * Loads on first call; subsequent calls reuse the same instance.
 */

import { createHighlighter, type Highlighter } from "shiki";

let highlighterPromise: Promise<Highlighter> | null = null;

const THEMES = ["one-dark-pro", "github-light"] as const;

const LANGS = [
	"python",
	"typescript",
	"javascript",
	"bash",
	"json",
	"rust",
	"sql",
	"markdown",
	"text",
] as const;

/**
 * Get or create the shared Shiki highlighter instance.
 * Lazy-loaded on first call.
 */
function getHighlighter(): Promise<Highlighter> {
	if (!highlighterPromise) {
		highlighterPromise = createHighlighter({
			themes: [...THEMES],
			langs: [...LANGS],
		});
	}
	return highlighterPromise;
}

/**
 * Highlight code with Shiki.
 *
 * @param code - Source code to highlight
 * @param lang - Language identifier (falls back to 'text' if unsupported)
 * @param theme - 'dark' or 'light' — maps to Shiki theme name
 * @returns HTML string with syntax highlighting
 */
export async function highlight(
	code: string,
	lang: string,
	theme: "dark" | "light",
): Promise<string> {
	const highlighter = await getHighlighter();
	const shikiTheme = theme === "dark" ? "one-dark-pro" : "github-light";

	// Normalise lang — if not in loaded set, fall back to 'text'
	const loadedLangs = highlighter.getLoadedLanguages();
	const resolvedLang = loadedLangs.includes(lang) ? lang : "text";

	return highlighter.codeToHtml(code, {
		lang: resolvedLang,
		theme: shikiTheme,
	});
}

/**
 * Reset the highlighter singleton (for testing).
 */
export function resetHighlighter(): void {
	highlighterPromise = null;
}
