from __future__ import annotations

from app.plugins.flights.geo import haversine_nm, is_route_plausible

# Real coordinates used throughout: DFW/SAN form a genuine plausible route
# for the SWA4429 investigation case; DEN/BNA and CLT/BOS are the two
# real wrong answers ADSBDB and adsb.lol's routeset each returned for
# aircraft actually flying near Phoenix, AZ / Queen Creek, AZ.
DFW = (32.8998, -97.0403)
SAN = (32.7338, -117.1933)
PHX_AIRCRAFT = (33.37175, -111.848621)  # SWA4429's actual live position near Phoenix
DEN = (39.8617, -104.6731)
BNA = (36.1245, -86.6782)
CLT = (35.2144, -80.9473)
BOS = (42.3656, -71.0096)
QUEEN_CREEK_AIRCRAFT = (33.2487, -111.6343)


def test_haversine_nm_matches_known_distance():
    # DFW-SAN great-circle distance is ~1015nm.
    assert 1000 <= haversine_nm(*DFW, *SAN) <= 1030


def test_plausible_for_aircraft_actually_on_the_route():
    assert is_route_plausible(*PHX_AIRCRAFT, *DFW, *SAN) is True


def test_implausible_for_route_far_from_aircraft():
    # Real bug case: ADSBDB reported DEN->BNA for an aircraft near Phoenix.
    assert is_route_plausible(*PHX_AIRCRAFT, *DEN, *BNA) is False


def test_implausible_for_cross_country_route_near_queen_creek():
    # Real bug case: a route between two East Coast cities reported for an
    # aircraft near Queen Creek, AZ.
    assert is_route_plausible(*QUEEN_CREEK_AIRCRAFT, *CLT, *BOS) is False


def test_plausible_at_origin_and_destination_airports():
    assert is_route_plausible(*DFW, *DFW, *SAN) is True
    assert is_route_plausible(*SAN, *DFW, *SAN) is True


def test_plausible_near_route_midpoint():
    assert is_route_plausible(32.8, -107.0, *DFW, *SAN) is True


def test_implausible_far_off_to_the_side_of_the_route():
    assert is_route_plausible(40.0, -107.0, *DFW, *SAN) is False


def test_implausible_far_beyond_either_end_of_the_route():
    # ~9 degrees (~540nm) past the origin, in the direction away from the
    # destination -- well beyond the along-track slop allowance.
    assert is_route_plausible(32.8998, -97.0403 + 9.0, *DFW, *SAN) is False
    # ~9 degrees past the destination, continuing away from the origin.
    assert is_route_plausible(32.7338, -117.1933 - 9.0, *DFW, *SAN) is False
