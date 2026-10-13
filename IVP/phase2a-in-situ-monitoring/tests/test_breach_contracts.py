"""Contract tests for BreachEvent schema compliance."""

import pytest
from datetime import datetime, timezone
from ewp_p2a.publish.emitter import BreachEmitter
from ewp_p2a.common.types import (
    ProposedLevel,
    BreachTrigger,
    IVMForecast,
    IVMStatus,
    RainContext,
    RainIDClass,
    MonitoringStatus,
)


def test_breach_event_validates_against_contract():
    """Verify that emitted BreachEvent matches contracts/breach_event.schema.json."""
    emitter = BreachEmitter()

    event = emitter.build_breach_event(
        site_id="SITE-0007",
        proposed_level=ProposedLevel.WARNING,
        triggers=[
            BreachTrigger(
                rule="v_warn",
                sensor_id="GNSS-02",
                value=12.4,
                unit="mm/day",
                threshold_version="th-2026-09-01",
            ),
            BreachTrigger(
                rule="v_warn",
                sensor_id="EXT-01",
                value=11.1,
                unit="mm/day",
                threshold_version="th-2026-09-01",
            ),
        ],
        ivm_forecast=IVMForecast(
            status=IVMStatus.VALID,
            tf_window_utc=["2026-10-11T12:00:00Z", "2026-10-12T18:00:00Z"],
            validity="MEDIUM",
        ),
        rain_context=RainContext(
            id_class=RainIDClass.EXCEEDED,
            api_mm=212.0,
        ),
        monitoring_status=MonitoringStatus.NOMINAL,
        evidence_url="https://landslide-ewp.org/sites/SITE-0007/evidence/e1",
        now=datetime(2026, 10, 10, 6, 20, tzinfo=timezone.utc),
        validate=True,
    )

    assert event.site_id == "SITE-0007"
    assert event.proposed_level == ProposedLevel.WARNING
    assert len(event.triggers) == 2
    assert event.monitoring_status == MonitoringStatus.NOMINAL
