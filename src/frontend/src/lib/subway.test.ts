/**
 * Showing the nearest subway.
 *
 * The data is derived by the importer; this is only how it reads. The colours
 * matter because people recognise a line by its colour before its letter, and
 * a wrong one is worse than none.
 */

import { describe, expect, it } from 'vitest';

import { orderByTrunk, routeColour, routeTextColour, STEP_FREE, walkMinutes } from './subway';

describe('line colours', () => {
	it('groups by trunk line, as the system does', () => {
		// The A, C and E share a colour because they share a trunk, not because
		// they go to the same places.
		expect(routeColour('A')).toBe(routeColour('C'));
		expect(routeColour('A')).toBe(routeColour('E'));
		expect(routeColour('1')).toBe(routeColour('2'));
	});

	it('keeps different trunks apart', () => {
		const trunks = ['1', '4', '7', 'A', 'B', 'G', 'J', 'L', 'N'].map(routeColour);
		expect(new Set(trunks).size).toBe(trunks.length);
	});

	it('is case insensitive', () => {
		expect(routeColour('a')).toBe(routeColour('A'));
	});

	it('falls back to grey for a line it does not know', () => {
		// A new line, or a suffix the MTA has not used before. Grey says "a
		// train stops here" without inventing a colour for it.
		expect(routeColour('ZZ')).toBe('#808183');
	});

	it('puts dark text on the yellow lines only', () => {
		for (const route of ['N', 'Q', 'R', 'W']) {
			expect(routeTextColour(route)).toBe('#000000');
		}
		for (const route of ['A', '1', 'L', 'G']) {
			expect(routeTextColour(route)).toBe('#ffffff');
		}
	});
});

describe('grouping by trunk', () => {
	it('keeps same-coloured lines together', () => {
		// W 4 St-Wash Sq is published "A B C D E F M", which renders
		// blue-orange-blue-orange-blue-orange-orange.
		expect(orderByTrunk(['A', 'B', 'C', 'D', 'E', 'F', 'M'])).toEqual([
			'A',
			'C',
			'E',
			'B',
			'D',
			'F',
			'M'
		]);
	});

	it('leaves each group in one run of colour', () => {
		const colours = orderByTrunk(['A', 'B', 'C', 'D', 'E', 'F', 'M']).map(routeColour);
		const runs = colours.filter((colour, i) => colour !== colours[i - 1]);
		// One run per distinct colour means no colour is split in two.
		expect(runs.length).toBe(new Set(colours).size);
	});

	it('orders the groups as the system numbers them', () => {
		expect(orderByTrunk(['N', '4', 'A'])).toEqual(['4', 'A', 'N']);
	});

	it('puts a line it does not know last', () => {
		// Rather than landing in whichever group it sorts next to.
		expect(orderByTrunk(['ZZ', '6'])).toEqual(['6', 'ZZ']);
	});

	it('does not drop or invent a line', () => {
		const routes = ['L', 'N', 'Q', 'R', 'W', '4', '5', '6'];
		expect(orderByTrunk(routes).sort()).toEqual([...routes].sort());
	});

	it('leaves the caller’s array alone', () => {
		const routes = ['M', 'A'];
		orderByTrunk(routes);
		expect(routes).toEqual(['M', 'A']);
	});
});

describe('walk time', () => {
	it('reads as a person would say it', () => {
		// Nobody converts 409 m in their head.
		expect(walkMinutes(409)).toBe(5);
		expect(walkMinutes(800)).toBe(10);
	});

	it('never says zero minutes', () => {
		// A station across the street is a one-minute walk, not a no-minute one.
		expect(walkMinutes(0)).toBe(1);
		expect(walkMinutes(12)).toBe(1);
	});

	it('is a whole number', () => {
		// The distance is straight-line rather than along streets, so it is
		// already an approximation; a decimal would dress that up.
		for (const metres of [100, 250, 409, 777, 1199]) {
			expect(Number.isInteger(walkMinutes(metres))).toBe(true);
		}
	});
});

describe('step-free wording', () => {
	it('keeps the MTA’s three states apart', () => {
		expect(new Set(Object.values(STEP_FREE)).size).toBe(3);
	});

	it('says plainly when there is none', () => {
		// For someone who needs step-free access, silence is the one unhelpful
		// answer, and here the MTA is making a positive claim.
		expect(STEP_FREE.none).toContain('no step-free');
	});

	it('does not round one direction to both', () => {
		expect(STEP_FREE.partial).not.toBe(STEP_FREE.full);
		expect(STEP_FREE.partial).toContain('one way');
	});
});
