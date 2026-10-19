// Strips the public /api prefix before the request reaches Django.
//
// The API's own routes are /health/live and /spots, while the public paths are
// /api/health/live and /api/spots, so the edge removes exactly one leading
// /api segment and Django never learns about the prefix.

function handler(event) {
	var request = event.request;

	// Only this behavior's /api/* pattern reaches here, so the prefix is always
	// present. Removing it can leave an empty string, which is not a valid URI.
	request.uri = request.uri.slice(4) || '/';

	return request;
}
