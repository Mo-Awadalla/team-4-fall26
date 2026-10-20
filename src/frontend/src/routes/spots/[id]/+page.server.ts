import { error } from '@sveltejs/kit';

import { allSpots, nearbySpots, spotById } from '$lib/server/snapshot';
import type { EntryGenerator, PageServerLoad } from './$types';

// Every detail page is written as real HTML at build time. The identifiers come
// from the committed snapshot, so the set is known in advance and no route is
// left to a runtime fallback.
export const prerender = true;

export const entries: EntryGenerator = () => allSpots().map((spot) => ({ id: spot.id }));

export const load: PageServerLoad = ({ params }) => {
	const spot = spotById(params.id);
	if (spot === undefined) {
		// Unreachable through `entries`, and the honest answer if the snapshot
		// and a hand-typed URL ever disagree.
		throw error(404, `No study spot has the identifier ${params.id}`);
	}

	return { spot, nearby: nearbySpots(spot) };
};
