/**
 * What a result card says about the places around a spot.
 *
 * This line used to be a Quiet/Moderate/Busy label with a row of icons. The
 * number underneath it counts *other study spots* within 400 m -- places, not
 * people -- so "Busy" sitting under a cafe's name read as a claim about that
 * cafe that nothing in the data could support. These assertions pin the
 * replacement: the count itself, and no word derived from it.
 */

import { page } from 'vitest/browser';
import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';

import SpotResults from './SpotResults.svelte';
import type { StudySpot } from './contract';

function spot(nearby: number): StudySpot {
	return {
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
		nearby_spots: nearby
	};
}

function show(nearby: number): void {
	render(SpotResults, { spots: [spot(nearby)], total: 1, hasMore: false });
}

describe('the alternatives line', () => {
	it('gives the count when there are several', async () => {
		show(41);

		await expect
			.element(page.getByText('41 alternatives within a 5-minute walk'))
			.toBeInTheDocument();
	});

	it('says it in the singular when there is one', async () => {
		show(1);

		await expect
			.element(page.getByText('1 alternative within a 5-minute walk'))
			.toBeInTheDocument();
	});

	it('says so plainly when there are none', async () => {
		// Not an empty line: that this one is on its own is the thing worth
		// knowing before making the trip.
		show(0);

		await expect
			.element(page.getByText('No alternatives within a 5-minute walk'))
			.toBeInTheDocument();
	});

	it('draws no conclusion about how busy the place is', async () => {
		// The count is of places, not people. A word here would be an inference
		// presented as a measurement, which is what this replaced.
		show(41);

		await expect.element(page.getByText('Bobst Library')).toBeInTheDocument();
		await expect.element(page.getByText(/Quiet|Moderate|Busy/)).not.toBeInTheDocument();
	});
});
