"""Test MQTT telemetry ingestion, schema validation, and idempotent deduplication."""

import pytest
from ewp_p2a.ingest.consumer import IngestionWorker


def test_telemetry_ingest_and_deduplication():
    """Verify that incoming telemetry is validated and duplicate messages are ignored idempotently."""
    worker = IngestionWorker()

    valid_payload = {
        "ts": "2026-10-10T06:15:00Z",
        "site_id": "SITE-0007",
        "sensor_id": "GNSS-02",
        "channel": "gnss_enu",
        "values": {"e_mm": 1.2, "n_mm": -0.4, "u_mm": 0.9},
        "sigma": {"h_mm": 2.0, "v_mm": 4.0},
        "quality": "OK",
        "battery_v": 12.6,
        "seq": 88412,
    }

    # First ingestion -> ACCEPTED
    res1 = worker.ingest_message(valid_payload)
    assert res1["status"] == "ACCEPTED"
    assert res1["sensor_id"] == "GNSS-02"

    # Exact duplicate message -> DUPLICATE_IGNORED
    res2 = worker.ingest_message(valid_payload)
    assert res2["status"] == "DUPLICATE_IGNORED"


def test_late_arriving_backfill():
    """Verify that late-arriving backfill from field logger buffer is accepted and identified."""
    worker = IngestionWorker()

    msg_t2 = {
        "ts": "2026-10-10T08:00:00Z",
        "site_id": "SITE-0007",
        "sensor_id": "GNSS-02",
        "channel": "gnss_enu",
        "values": {"e_mm": 2.0, "n_mm": 0.0, "u_mm": 1.0},
        "quality": "OK",
        "battery_v": 12.5,
        "seq": 88500,
    }
    worker.ingest_message(msg_t2)

    # Late-arriving reading from t1 (07:00:00Z)
    msg_t1 = {
        "ts": "2026-10-10T07:00:00Z",
        "site_id": "SITE-0007",
        "sensor_id": "GNSS-02",
        "channel": "gnss_enu",
        "values": {"e_mm": 1.5, "n_mm": -0.2, "u_mm": 0.95},
        "quality": "OK",
        "battery_v": 12.5,
        "seq": 88450,
    }
    res_late = worker.ingest_message(msg_t1)
    assert res_late["status"] == "ACCEPTED"
    assert res_late["is_late_backfill"] is True
