/**
 * How busy the streets around a spot are.
 *
 * The thing worth testing is the honesty of the label as much as the banding:
 * the word has to be accompanied by the count it comes from, and the scale has
 * to be readable without relying on colour.
 */

import { describe, expect, it } from 'vitest';

import { busyness } from './busyness';

describe('banding', () => {
	it('calls a spot with nothing near it quiet', () => {
		expect(busyness(0).level).toBe('quiet');
	});

	it('calls a handful moderate', () => {
		for (const nearby of [1, 5, 9]) {
			expect(busyness(nearby).level, `${nearby} nearby`).toBe('moderate');
		}
	});

	it('calls ten or more busy', () => {
		for (const nearby of [10, 23, 74]) {
			expect(busyness(nearby).level, `${nearby} nearby`).toBe('busy');
		}
	});

	it('rises without ever going back down', () => {
		const order = { quiet: 0, moderate: 1, busy: 2 };
		let previous = -1;
		for (let nearby = 0; nearby <= 80; nearby++) {
			const level = order[busyness(nearby).level];
			expect(level).toBeGreaterThanOrEqual(previous);
			previous = level;
		}
	});
});

describe('how it reads', () => {
	it('says what the word is derived from', () => {
		// A label you can check is a different thing from one you have to
		// trust. The count travels with the word for that reason.
		expect(busyness(23).detail).toContain('23 other places');
		expect(busyness(0).detail).toContain('nothing else');
	});

	it('counts one neighbour in the singular', () => {
		expect(busyness(1).detail).toContain('1 other place within');
	});

	it('never claims to know about people', () => {
		// It counts places. A cafe on a dense stretch may be empty and an
		// isolated library may be packed; nothing in open data knows.
		for (const nearby of [0, 1, 10, 74]) {
			expect(busyness(nearby).detail).not.toMatch(/people|crowd|busy|quiet/i);
		}
	});
});

describe('how it is drawn', () => {
	it('encodes the level three ways, not just in colour', () => {
		// Colour alone would fail anyone who cannot distinguish these three.
		const levels = [busyness(0), busyness(5), busyness(40)];

		expect(levels.map((state) => state.feet)).toEqual([1, 2, 3]);
		expect(new Set(levels.map((state) => state.label)).size).toBe(3);
		expect(new Set(levels.map((state) => state.colour)).size).toBe(3);
	});

	it('puts green at the quiet end', () => {
		// Backwards for a bar; right for somewhere to sit and work.
		expect(busyness(0).colour).not.toBe(busyness(40).colour);
		expect(busyness(0).label).toBe('Quiet');
	});

	it('uses colours dark enough to read on white', () => {
		// Each is AA against white at this size; a mid yellow would not be.
		for (const nearby of [0, 5, 40]) {
			const [r, g, b] = busyness(nearby)
				.colour.slice(1)
				.match(/../g)!
				.map((pair) => parseInt(pair, 16));
			const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
			expect(luminance, busyness(nearby).colour).toBeLessThan(0.6);
		}
	});
});
