/**
 * Where the Maps button goes.
 *
 * A hyperlink and nothing more — no API, no key, no billing, none of what the
 * Places API would involve. On a phone it opens the Maps app with the place
 * pinned; on a desktop it opens maps.google.com. Walking and subway directions
 * are then one tap away, which is the whole point of the button.
 */

import type { StudySpot } from './contract';

/**
 * Google's documented URL interface for showing a place.
 *
 * The name and address are preferred over raw coordinates, because searching
 * for "Jean's, 415 Lafayette Street, New York, NY 10003" lands on the business
 * — with its own hours, photos and reviews — while coordinates land on a bare
 * pin labelled 40.7285, -73.9926. The address makes the name unambiguous, so
 * this is not the loose text search it looks like.
 *
 * Coordinates are the fallback, because 36 of the snapshot's records have no
 * address and a pin in the right place beats no link at all.
 */
export function mapsUrl(spot: StudySpot): string {
	const query = spot.address
		? `${spot.name}, ${spot.address}`
		: `${spot.latitude},${spot.longitude}`;

	return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
}
