"""Unit tests for data models."""

from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from around_the_grounds.models import Venue, Event


class TestVenue:
    """Test the Venue model."""

    def test_venue_creation(self) -> None:
        """Test basic venue creation."""
        venue = Venue(
            key="test-key", name="Test Venue", url="https://example.com",
            source_type="html"
        )
        assert venue.key == "test-key"
        assert venue.name == "Test Venue"
        assert venue.url == "https://example.com"
        assert venue.source_type == "html"
        assert venue.parser_config == {}

    def test_venue_invalid_source_type(self) -> None:
        """Test venue validation rejects invalid source_type."""
        import pytest
        with pytest.raises(ValueError, match="Invalid source_type"):
            Venue(key="k", name="n", url="u", source_type="invalid")

    def test_venue_valid_source_types(self) -> None:
        """Test all valid source types."""
        for st in ["html", "ical", "api"]:
            v = Venue(key="k", name="n", url="u", source_type=st)
            assert v.source_type == st


class TestEvent:
    """Test the Event model."""

    def test_event_creation(self) -> None:
        """Test basic event creation with tz-aware datetime."""
        dt = datetime(2025, 7, 5, 12, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        event = Event(
            venue_key="test-venue",
            venue_name="Test Venue",
            title="Test Truck",
            datetime_start=dt,
        )
        assert event.venue_key == "test-venue"
        assert event.venue_name == "Test Venue"
        assert event.title == "Test Truck"
        assert event.datetime_start == dt
        assert event.datetime_end is None
        assert event.extraction_method == "html"

    def test_event_rejects_naive_datetime(self) -> None:
        """Test that naive datetime_start raises ValueError."""
        import pytest
        with pytest.raises(ValueError, match="timezone-aware"):
            Event(
                venue_key="k",
                venue_name="n",
                title="t",
                datetime_start=datetime(2025, 7, 5, 12, 0, 0),  # naive
            )

    def test_event_with_end_time(self) -> None:
        """Test event with tz-aware end time."""
        dt = datetime(2025, 7, 5, 12, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        end = datetime(2025, 7, 5, 20, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        event = Event(
            venue_key="k", venue_name="n", title="t",
            datetime_start=dt, datetime_end=end,
        )
        assert event.datetime_end == end
