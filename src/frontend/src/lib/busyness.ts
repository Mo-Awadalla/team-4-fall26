/**
 * How busy the streets around a spot are.
 *
 * Derived from one number the importer stores: how many other study spots sit
 * within 400 m, about a five-minute walk.
 *
 * **It counts places, not people.** A café on a dense stretch may be empty and
 * an isolated library may be packed; nothing in open data knows. What the
 * count does support is how lively the surrounding block is, and whether there
 * is anywhere else to go if this one is full — which is the question a reader
 * can act on. The count is shown beside the word for exactly that reason: a
 * label you can check is a different thing from one you have to trust.
 *
 * Green is the quiet end on purpose. For a bar that would be backwards; for
 * somewhere to sit and work it is not.
 */

export type Busyness = {
	/** `quiet`, `moderate` or `busy`. */
	level: 'quiet' | 'moderate' | 'busy';
	/** The word shown to a reader. */
	label: string;
	/** How many footprints to draw, 1 to 3 — redundant with the colour. */
	feet: 1 | 2 | 3;
	/** Accessible against white; each is AA at this size. */
	colour: string;
	/** What the word is derived from, said plainly. */
	detail: string;
};

/**
 * Thresholds chosen from the real distribution rather than to balance the
 * bands.
 *
 * Median neighbours by borough: Manhattan 23, Brooklyn 6, Queens 3, Bronx 1,
 * Staten Island 0. Splitting at 0 and 10 therefore separates the places that
 * genuinely differ. Forcing even thirds would have fitted the labels to the
 * histogram instead of to the city, and 58% of the snapshot really is on a
 * busy block.
 */
const BUSY_FROM = 10;

export function busyness(nearby: number): Busyness {
	if (nearby === 0) {
		return {
			level: 'quiet',
			label: 'Quiet',
			feet: 1,
			colour: '#1a7f37',
			detail: 'nothing else within a 5-minute walk'
		};
	}

	if (nearby < BUSY_FROM) {
		return {
			level: 'moderate',
			label: 'Moderate',
			feet: 2,
			colour: '#9a6700',
			detail: `${nearby} other ${nearby === 1 ? 'place' : 'places'} within a 5-minute walk`
		};
	}

	return {
		level: 'busy',
		label: 'Busy',
		feet: 3,
		colour: '#cf222e',
		detail: `${nearby} other places within a 5-minute walk`
	};
}
