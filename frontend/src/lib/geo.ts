// Spherical-slerp great-circle interpolation, mirroring the great-circle
// vector math the backend already uses for route-plausibility checks
// (app/plugins/flights/geo.py) -- reimplemented here since that's Python and
// this needs to run in the map component.
export function greatCirclePoints(
	lat1: number,
	lon1: number,
	lat2: number,
	lon2: number,
	numPoints = 32,
): [number, number][] {
	const toRad = (d: number) => (d * Math.PI) / 180;
	const toDeg = (r: number) => (r * 180) / Math.PI;
	const phi1 = toRad(lat1);
	const lam1 = toRad(lon1);
	const phi2 = toRad(lat2);
	const lam2 = toRad(lon2);

	const angularDistance =
		2 *
		Math.asin(
			Math.sqrt(Math.sin((phi2 - phi1) / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin((lam2 - lam1) / 2) ** 2),
		);

	if (angularDistance < 1e-9) {
		return [
			[lat1, lon1],
			[lat2, lon2],
		];
	}

	const points: [number, number][] = [];
	for (let i = 0; i <= numPoints; i++) {
		const fraction = i / numPoints;
		const a = Math.sin((1 - fraction) * angularDistance) / Math.sin(angularDistance);
		const b = Math.sin(fraction * angularDistance) / Math.sin(angularDistance);
		const x = a * Math.cos(phi1) * Math.cos(lam1) + b * Math.cos(phi2) * Math.cos(lam2);
		const y = a * Math.cos(phi1) * Math.sin(lam1) + b * Math.cos(phi2) * Math.sin(lam2);
		const z = a * Math.sin(phi1) + b * Math.sin(phi2);
		const lat = toDeg(Math.atan2(z, Math.sqrt(x * x + y * y)));
		const lon = toDeg(Math.atan2(y, x));
		points.push([lat, lon]);
	}

	// Leaflet draws a straight line between consecutive polyline vertices, so
	// a route crossing the antimeridian needs its longitudes unwrapped --
	// otherwise consecutive points near +/-180 degrees produce a line that
	// jumps across the entire map instead of continuing smoothly.
	for (let i = 1; i < points.length; i++) {
		const prevLon = points[i - 1][1];
		let lon = points[i][1];
		while (lon - prevLon > 180) lon -= 360;
		while (lon - prevLon < -180) lon += 360;
		points[i][1] = lon;
	}

	return points;
}
