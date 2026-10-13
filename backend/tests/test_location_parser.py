import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.schemas import ParticipantLocationInput
from app.services.location_parser import parse_location_input


def test_parse_plain_lat_lng_coordinates():
    result = asyncio.run(
        parse_location_input(
            ParticipantLocationInput(label="A", value="39.9208, 32.8541", delta_weight=1.2)
        )
    )

    assert result.error is None
    assert result.lat == 39.9208
    assert result.lng == 32.8541
    assert result.location_input_type == "coordinate"
    assert result.delta_weight == 1.2


def test_parse_google_maps_at_coordinates():
    result = asyncio.run(
        parse_location_input(
            ParticipantLocationInput(
                label="B",
                value="https://www.google.com/maps/place/Test/@39.9208,32.8541,15z",
            )
        )
    )

    assert result.error is None
    assert result.lat == 39.9208
    assert result.lng == 32.8541
    assert result.location_input_type == "link"


def test_parse_invalid_location_returns_row_error():
    result = asyncio.run(
        parse_location_input(ParticipantLocationInput(label="C", value="not-a-real-location"))
    )

    assert result.lat is None
    assert result.lng is None
    assert result.error
