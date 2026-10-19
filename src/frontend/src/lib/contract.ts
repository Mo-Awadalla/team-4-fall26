/**
 * The shared study-spot contract, as the browser sees it.
 *
 * These mirror `spots.models.StudySpot` and the response shapes in
 * `docs/source/api.md`. They are written out rather than generated because the
 * contract is small and changes need sign-off from every consumer; a generated
 * type would let a backend change land here silently.
 *
 * Nullability follows what NYC Open Data supplies: `address` and `neighborhood`
 * are genuinely absent for some records, and `university` is absent for every
 * record the importer does not take from a curated campus list.
 */

export const BOROUGHS = ['Manhattan', 'Brooklyn', 'Queens', 'Bronx', 'Staten Island'] as const;

export type Borough = (typeof BOROUGHS)[number];

export type StudySpot = {
	/** Stable identifier, prefixed with its source dataset, as in `facdb:a1b2c3`. */
	id: string;
	name: string;
	category: string;
	address: string | null;
	neighborhood: string | null;
	borough: Borough;
	latitude: number;
	longitude: number;
	/**
	 * The closest campus within 500 m, or the campus itself for a campus record.
	 * This is proximity and never affiliation, endorsement, or a claim of access.
	 */
	university: string | null;
};

/** Where a page sits in the full result set. */
export type Pagination = {
	limit: number;
	offset: number;
	count: number;
	total: number;
	has_more: boolean;
};

export type SpotPage = {
	items: StudySpot[];
	pagination: Pagination;
};

/** One specific problem with a request. */
export type ErrorDetail = {
	field: string | null;
	message: string;
	type: string | null;
};

/** The envelope every non-2xx response uses. */
export type ErrorEnvelope = {
	error: {
		code: string;
		message: string;
		details: ErrorDetail[];
	};
};
