"""Great-circle geometry helpers for sanity-checking flight routes.

Route lookups (ADSBDB, adsb.lol's routeset) are keyed purely by callsign
with no notion of "today's actual flight" -- airlines reuse flight
numbers for different city-pairs over time, so these APIs frequently
return a stale or simply wrong route. `is_route_plausible` cross-checks a
candidate route against the aircraft's live position before it's trusted.
"""

from __future__ import annotations

import math

_EARTH_RADIUS_NM = 3440.065

Vector3 = tuple[float, float, float]

# An aircraft this far off the great-circle line between origin and
# destination is not meaningfully "on that route" -- generous enough to
# tolerate normal ATC vectoring/weather deviation without accepting
# obviously unrelated routes (e.g. a route 1000+nm away).
_MAX_CROSS_TRACK_NM = 100.0

# Allowance beyond each airport along the route line, to tolerate
# climb-out/approach paths that extend a bit past the airports themselves.
_ALONG_TRACK_SLOP_NM = 50.0


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in nautical miles."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return 2 * _EARTH_RADIUS_NM * math.asin(math.sqrt(a))


def _unit_vector(lat: float, lon: float) -> Vector3:
    phi, lam = math.radians(lat), math.radians(lon)
    return (math.cos(phi) * math.cos(lam), math.cos(phi) * math.sin(lam), math.sin(phi))


def _dot(a: Vector3, b: Vector3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vector3, b: Vector3) -> Vector3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a: Vector3) -> float:
    return math.sqrt(_dot(a, a))


def _normalize(a: Vector3) -> Vector3:
    n = _norm(a)
    return (a[0] / n, a[1] / n, a[2] / n)


def is_route_plausible(
    ac_lat: float,
    ac_lon: float,
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> bool:
    """Whether the aircraft's live position is consistent with flying the
    origin -> destination route: close to the great-circle line between
    them, and projected between the two airports (not far beyond either end).
    """
    origin_vec = _unit_vector(origin_lat, origin_lon)
    dest_vec = _unit_vector(dest_lat, dest_lon)
    ac_vec = _unit_vector(ac_lat, ac_lon)

    normal = _cross(origin_vec, dest_vec)
    normal_magnitude = _norm(normal)
    if normal_magnitude < 1e-9:
        # Origin and destination are (anti)podal/identical -- degenerate great
        # circle, no meaningful line to check against.
        return True
    normal_unit = (normal[0] / normal_magnitude, normal[1] / normal_magnitude, normal[2] / normal_magnitude)

    cross_track_nm = abs(math.asin(max(-1.0, min(1.0, _dot(ac_vec, normal_unit))))) * _EARTH_RADIUS_NM
    if cross_track_nm > _MAX_CROSS_TRACK_NM:
        return False

    # Unit tangent at the origin, within the great-circle plane, pointing
    # towards the destination -- lets us measure the aircraft's signed
    # along-track position via a simple atan2 of its components along this
    # tangent and along the origin vector.
    dest_tangent = _normalize(
        (
            dest_vec[0] - origin_vec[0] * _dot(dest_vec, origin_vec),
            dest_vec[1] - origin_vec[1] * _dot(dest_vec, origin_vec),
            dest_vec[2] - origin_vec[2] * _dot(dest_vec, origin_vec),
        )
    )
    along_track_nm = math.atan2(_dot(ac_vec, dest_tangent), _dot(ac_vec, origin_vec)) * _EARTH_RADIUS_NM
    route_distance_nm = haversine_nm(origin_lat, origin_lon, dest_lat, dest_lon)

    return -_ALONG_TRACK_SLOP_NM <= along_track_nm <= route_distance_nm + _ALONG_TRACK_SLOP_NM
