import { describe, expect, it } from 'vitest';
import { ApiError, listSpots, searchSpots } from './api';
import type { SpotPage } from './contract';

/** A page shaped like the API's, with as many identical items as asked for. */
function page(total: number, count = total, offset = 0): SpotPage {
	return {
		items: Array.from({ length: count }, (_, index) => ({
			id: `facdb:${offset + index}`,
			name: `Spot ${offset + index}`,
			category: 'library',
			address: null,
			neighborhood: 'Greenpoint',
			borough: 'Brooklyn' as const,
			latitude: 40.73,
			longitude: -73.95,
			university: null
		})),
		pagination: {
			limit: 20,
			offset,
			count,
			total,
			has_more: offset + count < total
		}
	};
}

function json(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'content-type': 'application/json' }
	});
}

/** Records every URL it is called with, and replies from a queue. */
function recorder(...replies: Array<() => Response | Promise<Response>>) {
	const urls: string[] = [];
	let call = 0;
	const fetcher = async (input: RequestInfo | URL) => {
		urls.push(String(input));
		const reply = replies[Math.min(call++, replies.length - 1)];
		return reply();
	};
	return { urls, fetcher: fetcher as unknown as typeof globalThis.fetch };
}

describe('searchSpots', () => {
	it('filters by name and asks for the default page size', async () => {
		const { urls, fetcher } = recorder(() => json(page(3)));

		const result = await searchSpots('library', { fetcher });

		expect(result.pagination.total).toBe(3);
		expect(urls).toHaveLength(1);
		expect(urls[0]).toContain('name=library');
		expect(urls[0]).toContain('limit=20');
		expect(urls[0]).toContain('offset=0');
	});

	it('falls back to a neighborhood match when the name finds nothing', async () => {
		// The search box offers to find a neighborhood, but the API has no
		// combined search: name is a substring match and neighborhood an exact
		// one, so the fallback is what makes the placeholder honest.
		const { urls, fetcher } = recorder(
			() => json(page(0, 0)),
			() => json(page(1))
		);

		const result = await searchSpots('Greenpoint', { fetcher });

		expect(result.pagination.total).toBe(1);
		expect(urls).toHaveLength(2);
		expect(urls[0]).toContain('name=Greenpoint');
		expect(urls[1]).toContain('neighborhood=Greenpoint');
	});

	it('does not make the second request when the name already matched', async () => {
		const { urls, fetcher } = recorder(() => json(page(2)));

		await searchSpots('library', { fetcher });

		expect(urls).toHaveLength(1);
	});

	it('passes an offset through for paging', async () => {
		const { urls, fetcher } = recorder(() => json(page(40, 20, 20)));

		const result = await searchSpots('library', { offset: 20, fetcher });

		expect(result.pagination.offset).toBe(20);
		expect(urls[0]).toContain('offset=20');
	});

	it('encodes a query that contains characters a URL would eat', async () => {
		const { urls, fetcher } = recorder(() => json(page(1)));

		await searchSpots('100% Coffee & Tea', { fetcher });

		expect(urls[0]).toContain('name=100%25+Coffee+%26+Tea');
	});
});

describe('error handling', () => {
	it('reports the API error code and message from the envelope', async () => {
		const { fetcher } = recorder(() =>
			json(
				{
					error: {
						code: 'validation_error',
						message: 'The request could not be validated.',
						details: []
					}
				},
				422
			)
		);

		const failure = await searchSpots('x', { fetcher }).catch((error: unknown) => error);

		expect(failure).toBeInstanceOf(ApiError);
		expect((failure as ApiError).code).toBe('validation_error');
		expect((failure as ApiError).status).toBe(422);
	});

	it('distinguishes a database outage, which the page words differently', async () => {
		const { fetcher } = recorder(() =>
			json(
				{
					error: {
						code: 'database_unavailable',
						message: 'The study-spot database is unavailable.',
						details: []
					}
				},
				503
			)
		);

		const failure = await searchSpots('x', { fetcher }).catch((error: unknown) => error);

		expect((failure as ApiError).code).toBe('database_unavailable');
	});

	it('reports a transport failure as a network error rather than a status', async () => {
		const { fetcher } = recorder(() => {
			throw new TypeError('Failed to fetch');
		});

		const failure = await searchSpots('x', { fetcher }).catch((error: unknown) => error);

		expect((failure as ApiError).code).toBe('network_error');
		expect((failure as ApiError).status).toBe(0);
	});

	it('reports a non-JSON body rather than throwing a parse error at the caller', async () => {
		const { fetcher } = recorder(
			() => new Response('<html>502 Bad Gateway</html>', { status: 502 })
		);

		const failure = await searchSpots('x', { fetcher }).catch((error: unknown) => error);

		expect((failure as ApiError).code).toBe('invalid_response');
	});

	it('still reports an error when a failure carries no envelope', async () => {
		const { fetcher } = recorder(() => json({ Message: null }, 403));

		const failure = await searchSpots('x', { fetcher }).catch((error: unknown) => error);

		expect((failure as ApiError).status).toBe(403);
	});
});

describe('listSpots', () => {
	it('asks for a page with no filter', async () => {
		const { urls, fetcher } = recorder(() => json(page(380, 20)));

		const result = await listSpots({ fetcher });

		expect(result.pagination.total).toBe(380);
		expect(urls[0]).not.toContain('name=');
	});
});
