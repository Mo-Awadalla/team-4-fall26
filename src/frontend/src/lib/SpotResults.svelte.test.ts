/**
 * What a result card does not say.
 *
 * The card briefly carried a Quiet/Moderate/Busy label, then a count of the
 * other spots within 400 m. Both came from the same number, and that number
 * counts *places, not people* -- nothing in open data knows whether a cafe has
 * a free table. The label inferred a conclusion the data could not support,
 * and the count restated the list the card already sits in.
 *
 * So the card says neither. This holds that line, because the pull to put a
 * lively-looking word back on a card is a strong one.
 */

import { page } from 'vitest/browser';
import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';

import SpotResults from './SpotResults.svelte';
import type { StudySpot } from './contract';

const SPOT: StudySpot = {
	id: 'facdb:bobst',
	name: 'Bobst Library',
	category: 'academic_library',
	address: '70 Washington Square South, New York, NY 10012',
	neighborhood: 'Greenwich Village',
	borough: 'Manhattan',
	latitude: 40.72925,
	longitude: -73.99712,
	university: 'New York University',
	operator: 'New York University',
	free_public_wifi: true,
	no_purchase_needed: false,
	subway_station: 'W 4 St-Wash Sq',
	subway_routes: 'A C E',
	subway_metres: 409,
	subway_step_free: 'full',
	nearby_spots: 41,
	outdoor_seating: false
};

describe('a result card', () => {
	it('shows what it knows about the place', async () => {
		render(SpotResults, { spots: [SPOT], total: 1, hasMore: false });

		await expect.element(page.getByText('Bobst Library')).toBeInTheDocument();
		await expect.element(page.getByText(/W 4 St-Wash Sq/)).toBeInTheDocument();
	});

	it('draws no conclusion about how busy the place is', async () => {
		render(SpotResults, { spots: [SPOT], total: 1, hasMore: false });

		await expect.element(page.getByText('Bobst Library')).toBeInTheDocument();
		await expect.element(page.getByText(/Quiet|Moderate|Busy/)).not.toBeInTheDocument();
	});

	it('does not count the places around it', async () => {
		// nearby_spots is 41 above. The detail page lists those neighbours by
		// name, which is actionable; a bare number on a card in a list of
		// alternatives is not.
		render(SpotResults, { spots: [SPOT], total: 1, hasMore: false });

		await expect.element(page.getByText('Bobst Library')).toBeInTheDocument();
		await expect.element(page.getByText(/41|alternatives?|nearby/i)).not.toBeInTheDocument();
	});
});
