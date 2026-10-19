/**
 * The browser's view of the StudySpot API.
 *
 * Every request is relative to `/api`, which works unchanged in all three
 * places this runs: Vite proxies it to the backend in development, and both
 * CloudFront and Vercel route it to the application in deployments. Nothing
 * here needs to know a hostname.
 */

import type { ErrorEnvelope, SpotPage } from './contract';

/** Matches the API's own default page size, so the first page agrees. */
export const DEFAULT_LIMIT = 20;

/**
 * An error the API reported in its own envelope, or a transport failure.
 *
 * `code` carries the API's machine-readable code where there was one, so a
 * caller can distinguish a validation problem from the database being down
 * without parsing a message meant for a person.
 */
export class ApiError extends Error {
	constructor(
		readonly code: string,
		message: string,
		readonly status: number
	) {
		super(message);
		this.name = 'ApiError';
	}
}

/** Narrow an unknown body to the shared error envelope. */
function isErrorEnvelope(body: unknown): body is ErrorEnvelope {
	if (typeof body !== 'object' || body === null || !('error' in body)) return false;
	const error = (body as { error: unknown }).error;
	return typeof error === 'object' && error !== null && 'code' in error && 'message' in error;
}

/** The dependency tests replace, rather than reaching for a global stub. */
export type Fetcher = typeof globalThis.fetch;

async function getSpots(parameters: URLSearchParams, fetcher: Fetcher): Promise<SpotPage> {
	let response: Response;
	try {
		response = await fetcher(`/api/spots?${parameters}`, {
			headers: { accept: 'application/json' }
		});
	} catch {
		// A network failure has no status and no envelope, so it gets a code of
		// its own rather than being reported as whatever the last status was.
		throw new ApiError('network_error', 'Could not reach the StudySpot API.', 0);
	}

	let body: unknown;
	try {
		body = await response.json();
	} catch {
		throw new ApiError(
			'invalid_response',
			'The API returned a response that was not JSON.',
			response.status
		);
	}

	if (!response.ok) {
		if (isErrorEnvelope(body)) {
			throw new ApiError(body.error.code, body.error.message, response.status);
		}
		throw new ApiError('error', `The API returned ${response.status}.`, response.status);
	}

	return body as SpotPage;
}

export type SearchOptions = {
	limit?: number;
	offset?: number;
	fetcher?: Fetcher;
};

/**
 * Search spots by a single free-text query.
 *
 * The search box offers to find a place "or neighborhood", but `GET /spots`
 * has no combined search: `name` is a substring match and `neighborhood` is an
 * exact one, and supplying both narrows rather than widens because filters are
 * combined with AND. So this tries the name first and falls back to treating
 * the query as a neighborhood when that finds nothing, which is what makes the
 * placeholder honest.
 *
 * It is deliberately two requests rather than something cleverer. The real fix
 * is the `GET /spots/search?q=` endpoint that `docs/source/api.md` lists as
 * planned; when that exists, this function becomes one call and the fallback
 * goes away.
 */
export async function searchSpots(query: string, options: SearchOptions = {}): Promise<SpotPage> {
	const { limit = DEFAULT_LIMIT, offset = 0, fetcher = globalThis.fetch } = options;
	const paging = { limit: String(limit), offset: String(offset) };

	const byName = await getSpots(new URLSearchParams({ ...paging, name: query }), fetcher);
	if (byName.pagination.total > 0) return byName;

	return getSpots(new URLSearchParams({ ...paging, neighborhood: query }), fetcher);
}

/** Fetch one page without a filter, for a default listing. */
export function listSpots(options: SearchOptions = {}): Promise<SpotPage> {
	const { limit = DEFAULT_LIMIT, offset = 0, fetcher = globalThis.fetch } = options;
	return getSpots(new URLSearchParams({ limit: String(limit), offset: String(offset) }), fetcher);
}
