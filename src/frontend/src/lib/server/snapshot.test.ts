/**
 * The build-time half of the detail pages.
 *
 * These run against the real committed snapshot rather than a fixture, because
 * what they are checking is that the snapshot can actually be read and that
 * every identifier the build will generate a page for is in it. A fixture would
 * pass while the real file was missing or moved.
 */

import { describe, expect, it } from 'vitest';

import { allSpots, allStations, nearbySpots, nearestStation, spotById } from './snapshot';

describe('reading the snapshot', () => {
	it('finds the committed file', () => {
		// Resolved by walking up from the working directory, which differs
		// between `vite build`, `vite dev` and this test runner.
		expect(allSpots().length).toBeGreaterThan(0);
	});

	it('reads it once however many times it is asked', () => {
		// Prerendering 1,916 pages would otherwise parse it 1,916 times.
		expect(allSpots()).toBe(allSpots());
	});

	it('carries every field the detail page shows', () => {
		const spot = allSpots()[0];

		for (const field of [
			'id',
			'name',
			'category',
			'borough',
			'latitude',
			'longitude',
			'operator',
			'free_public_wifi',
			'no_purchase_needed'
		]) {
			expect(spot, `${field} is missing from the snapshot`).toHaveProperty(field);
		}
	});

	it('gives every spot a unique identifier', () => {
		// Two pages would otherwise be written to the same key, and one would
		// silently win.
		const ids = allSpots().map((spot) => spot.id);
		expect(new Set(ids).size).toBe(ids.length);
	});

	it('gives every identifier a safe filename', () => {
		// Each becomes an S3 key and a URL path segment. A dot would also defeat
		// the edge rewrite, which appends .html only to segments without one.
		for (const spot of allSpots()) {
			expect(spot.id, `${spot.id} is not safe as a key`).toMatch(/^[A-Za-z0-9:_-]+$/);
		}
	});
});

describe('looking one up', () => {
	it('returns the spot', () => {
		const wanted = allSpots()[0];
		expect(spotById(wanted.id)?.name).toBe(wanted.name);
	});

	it('returns nothing for an identifier the snapshot does not have', () => {
		expect(spotById('facdb:nothing')).toBeUndefined();
	});
});

describe('what is nearby', () => {
	// A curated NYU building, chosen because it genuinely has close neighbours.
	// The first spot in the file has none within a few hundred metres, which
	// made an earlier version of these pass without asserting anything -- caught
	// by this project's `requireAssertions` setting rather than by review.
	const anchor = spotById('nyu:bobst-library');

	it('has an anchor to measure from', () => {
		expect(anchor).toBeDefined();
	});

	it('never includes the spot itself', () => {
		const found = nearbySpots(anchor!, 10, 1000);
		expect(found.length).toBeGreaterThan(0);
		expect(found.map((entry) => entry.spot.id)).not.toContain(anchor!.id);
	});

	it('is ordered nearest first', () => {
		const distances = nearbySpots(anchor!, 6, 1000).map((entry) => entry.metres);
		expect(distances.length).toBeGreaterThan(1);
		expect(distances).toEqual([...distances].sort((a, b) => a - b));
	});

	it('stays inside the radius it is given', () => {
		const found = nearbySpots(anchor!, 50, 200);
		expect(found.length).toBeGreaterThan(0);
		for (const entry of found) {
			expect(entry.metres).toBeLessThanOrEqual(200);
		}
	});

	it('returns no more than it is asked for', () => {
		expect(nearbySpots(anchor!, 2, 1000).length).toBe(2);
	});

	it('measures metres rather than something else', () => {
		// The failure this guards is a degrees-for-radians slip in the
		// haversine, which does not throw -- it just returns a number off by a
		// factor of sixty. Bobst has neighbours on the same block.
		const [nearest] = nearbySpots(anchor!, 1, 1000);
		expect(nearest.metres).toBeGreaterThan(0);
		expect(nearest.metres).toBeLessThan(200);
	});
});

describe('the nearest subway', () => {
	const bobst = spotById('nyu:bobst-library');

	it('reads the committed station list', () => {
		expect(allStations().length).toBeGreaterThan(400);
	});

	it('merges a complex into one station', () => {
		// The MTA publishes one row per line, so W 4 St-Wash Sq arrives twice --
		// as "A C E" and as "B D F M" at identical coordinates. Unmerged, a page
		// would show half the trains.
		const w4 = allStations().filter((station) => station.name.startsWith('W 4 St'));
		expect(w4).toHaveLength(1);
		expect(w4[0].routes).toEqual(expect.arrayContaining(['A', 'C', 'E', 'B', 'D', 'F', 'M']));
	});

	it('finds the closest one, not merely a close one', () => {
		const found = nearestStation(bobst!);
		expect(found).not.toBeNull();

		const closest = allStations()
			.map((station) => ({
				station,
				metres: Math.hypot(
					(station.latitude - bobst!.latitude) * 111_000,
					(station.longitude - bobst!.longitude) * 84_000
				)
			}))
			.sort((a, b) => a.metres - b.metres)[0];
		expect(found!.station.name).toBe(closest.station.name);
	});

	it('returns nothing when none is within the cutoff', () => {
		// Rather than a number nobody would act on: the furthest spot from any
		// station is 7.7 km away, on Staten Island.
		expect(nearestStation(bobst!, 1)).toBeNull();
	});

	it('reports one of the three accessibility states', () => {
		for (const station of allStations()) {
			expect(['full', 'partial', 'none']).toContain(station.step_free);
		}
	});

	it('places every station inside the city', () => {
		// The same check the importer now applies to spots, after one arrived
		// geocoded into Massachusetts Bay.
		for (const station of allStations()) {
			expect(station.latitude).toBeGreaterThan(40.47);
			expect(station.latitude).toBeLessThan(40.93);
			expect(station.longitude).toBeGreaterThan(-74.3);
			expect(station.longitude).toBeLessThan(-73.68);
		}
	});
});
