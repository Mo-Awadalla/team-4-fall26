/**
 * Presenting the nearest subway.
 *
 * The data is on the spot already — the importer derives it, so a card and a
 * detail page read the same four fields. What lives here is only how to show
 * them: which colour a line is, and how long the walk takes.
 */

/**
 * The MTA's own line colours, which people read faster than the letters.
 *
 * Grouped by trunk line the way the system is: the A, C and E share a colour
 * because they share a trunk, not because they go to the same places. These
 * are the published values and they change about once a decade.
 */
const TRUNK_COLOURS: ReadonlyArray<readonly [readonly string[], string]> = [
	[['1', '2', '3'], '#ee352e'],
	[['4', '5', '6'], '#00933c'],
	[['7'], '#b933ad'],
	[['A', 'C', 'E'], '#0039a6'],
	[['B', 'D', 'F', 'M'], '#ff6319'],
	[['G'], '#6cbe45'],
	[['J', 'Z'], '#996633'],
	[['L'], '#a7a9ac'],
	[['N', 'Q', 'R', 'W'], '#fccc0a'],
	[['S'], '#808183'],
	[['SIR', 'SI'], '#0039a6']
];

/**
 * The lines a station serves, grouped so that same-coloured bullets sit
 * together.
 *
 * The stored value keeps the MTA's own ordering, which is alphabetical and
 * therefore interleaves trunks: W 4 St-Wash Sq publishes "A B C D E F M",
 * which renders blue-orange-blue-orange-blue-orange-orange and is harder to
 * read than it needs to be. Grouped, it is "A C E" then "B D F M" -- two
 * blocks of colour, which is how the signage does it.
 *
 * Ordering is presentation, so it happens here rather than in the importer:
 * the trunks are defined by the colour table above, and duplicating that
 * knowledge in Python to sort the stored string would be two places to keep
 * in step.
 */
export function orderByTrunk(routes: string[]): string[] {
	const position = new Map<string, number>();
	TRUNK_COLOURS.forEach(([lines], trunk) => {
		lines.forEach((line, within) => position.set(line, trunk * 100 + within));
	});

	// A line the table does not know keeps its grey bullet and goes last,
	// rather than landing in whichever group it sorts next to.
	const rank = (route: string) => position.get(route.toUpperCase()) ?? Number.MAX_SAFE_INTEGER;
	return [...routes].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
}

/** Lines whose colour is too light for white text. */
const DARK_TEXT = new Set(['N', 'Q', 'R', 'W']);

const FALLBACK_COLOUR = '#808183';

/** The colour of a line's bullet, or a neutral grey for one we do not know. */
export function routeColour(route: string): string {
	const key = route.toUpperCase();
	for (const [routes, colour] of TRUNK_COLOURS) {
		if (routes.includes(key)) return colour;
	}
	// A new line, or an express suffix the MTA has not used before. Grey says
	// "a train stops here" without inventing a colour for it.
	return FALLBACK_COLOUR;
}

/** Black on yellow, white on everything else. */
export function routeTextColour(route: string): string {
	return DARK_TEXT.has(route.toUpperCase()) ? '#000000' : '#ffffff';
}

/** Metres a minute: roughly 4.8 km/h, an unhurried walk rather than a commuter's. */
const METRES_PER_MINUTE = 80;

/**
 * How long the walk is, as a person would say it.
 *
 * Nobody converts 409 m in their head. The distance is straight-line rather
 * than along streets, so this is already an approximation, and rounding it to
 * a minute admits that rather than dressing it up — "5 min walk" is honest
 * where "5.1 min" would not be.
 */
export function walkMinutes(metres: number): number {
	return Math.max(1, Math.round(metres / METRES_PER_MINUTE));
}

/** The three accessibility states, as the MTA publishes them. */
export const STEP_FREE: Record<string, string> = {
	full: 'step-free',
	partial: 'step-free one way only',
	none: 'no step-free access'
};
