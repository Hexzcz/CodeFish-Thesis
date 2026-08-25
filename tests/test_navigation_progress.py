"""Following a route: am I on it, how much further, am I there.

The geometry is deliberately hand-checkable — a 300 m dogleg with known
lengths — so a failure points at the maths rather than at the fixture.
"""
import pytest

from backend.domain.navigation.progress import (
    ARRIVAL_M,
    OFF_ROUTE_M,
    route_progress,
)

# 100 m east, then 200 m north, in [lon, lat] order. At 14.62° N one degree of
# latitude is 111_320 m and one of longitude 107_600 m, per domain.geo.
START = [121.0200, 14.6200]
CORNER = [121.0200 + 100 / 107_600, 14.6200]
END = [CORNER[0], 14.6200 + 200 / 111_320]
DOGLEG = [START, CORNER, END]


def test_standing_at_the_start_has_the_whole_route_left():
    progress = route_progress(DOGLEG, START[1], START[0])
    assert progress.distance_from_route_m == pytest.approx(0.0, abs=0.5)
    assert progress.remaining_m == pytest.approx(300.0, abs=1.0)
    assert progress.travelled_m == pytest.approx(0.0, abs=0.5)
    assert not progress.off_route
    assert not progress.arrived


def test_halfway_down_the_first_leg():
    lat, lon = START[1], (START[0] + CORNER[0]) / 2
    progress = route_progress(DOGLEG, lat, lon)
    assert progress.travelled_m == pytest.approx(50.0, abs=1.0)
    assert progress.remaining_m == pytest.approx(250.0, abs=1.0)
    assert progress.nearest_index == 0


def test_past_the_corner_counts_the_first_leg_as_walked():
    lat = CORNER[1] + 50 / 111_320
    progress = route_progress(DOGLEG, lat, CORNER[0])
    assert progress.nearest_index == 1
    assert progress.travelled_m == pytest.approx(150.0, abs=1.0)
    assert progress.remaining_m == pytest.approx(150.0, abs=1.0)


def test_standing_beside_the_route_is_not_off_it():
    """A GPS fix drifting across the street is normal, not a wrong turn."""
    lat = START[1] + 15 / 111_320
    progress = route_progress(DOGLEG, lat, (START[0] + CORNER[0]) / 2)
    assert progress.distance_from_route_m == pytest.approx(15.0, abs=1.0)
    assert not progress.off_route


def test_a_street_away_is_off_the_route():
    lat = START[1] + (OFF_ROUTE_M + 30) / 111_320
    progress = route_progress(DOGLEG, lat, (START[0] + CORNER[0]) / 2)
    assert progress.off_route
    assert progress.distance_from_route_m > OFF_ROUTE_M


def test_arriving_is_measured_to_the_destination():
    lat = END[1] - (ARRIVAL_M / 2) / 111_320
    progress = route_progress(DOGLEG, lat, END[0])
    assert progress.arrived

    short_of_it = route_progress(DOGLEG, END[1] - 100 / 111_320, END[0])
    assert not short_of_it.arrived


def test_walking_past_the_end_does_not_report_negative_remaining():
    lat = END[1] + 80 / 111_320
    progress = route_progress(DOGLEG, lat, END[0])
    assert progress.remaining_m >= 0.0
    assert progress.travelled_m <= 300.0 + 1.0


def test_a_route_with_nothing_to_follow_is_an_error():
    """Answering '0 m remaining' for an empty route would hide the bug."""
    with pytest.raises(ValueError):
        route_progress([], 14.62, 121.02)
    with pytest.raises(ValueError):
        route_progress([START], 14.62, 121.02)


def test_repeated_points_do_not_divide_by_zero():
    """Snapped routes can contain a zero-length segment."""
    progress = route_progress([START, START, CORNER], START[1], START[0])
    assert progress.remaining_m == pytest.approx(100.0, abs=1.0)
