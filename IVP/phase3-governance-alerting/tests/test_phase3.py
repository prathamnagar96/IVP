from datetime import datetime, timedelta, timezone
import pytest

from ewp_p3.audit.chain import AuditChain
from ewp_p3.cap.builder import build_cap, validate_cap
from ewp_p3.channels.delivery import required_channels
from ewp_p3.workflow.state import Decision, EventState, EventWorkflow, Role


def test_exercise_flow_requires_distinct_two_person_approval():
    workflow = EventWorkflow("event-1", "CRITICAL")
    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    workflow.trigger(now=now)
    workflow.add_decision(
        role=Role.EXPERT, user_id="expert-1", decision=Decision.CONFIRM,
        comment="Evidence reviewed", evidence_hash="evidence-hash", now=now,
    )
    assert workflow.can_broadcast() is False
    with pytest.raises(PermissionError):
        workflow.add_decision(
            role=Role.AUTHORITY, user_id="expert-1", decision=Decision.APPROVE,
            comment="Approved", evidence_hash="evidence-hash", now=now,
        )
    workflow.add_decision(
        role=Role.AUTHORITY, user_id="authority-1", decision=Decision.APPROVE,
        comment="Approved for exercise", evidence_hash="evidence-hash", now=now,
    )
    assert workflow.state == EventState.BROADCAST
    assert workflow.can_broadcast() is True


def test_sla_expiry_escalates_without_broadcast():
    workflow = EventWorkflow("event-2", "WARNING")
    start = datetime(2026, 10, 13, tzinfo=timezone.utc)
    workflow.trigger(now=start)
    assert workflow.escalate_if_expired(
        now=start + timedelta(minutes=16), expert_deadline_minutes=15
    )
    assert workflow.state == EventState.ESCALATED
    assert workflow.can_broadcast() is False


def test_cap_exercise_message_round_trip_and_polygon_gate():
    xml = build_cap(
        identifier="EWP-R01-2026-000123", sender="ewp@example.org",
        level="CRITICAL", area_description="Zone A",
        polygon=[(18.0, 73.0), (18.1, 73.0), (18.1, 73.1), (18.0, 73.0)],
        headline="Landslide danger: leave the marked area now",
        description="Ground movement is accelerating.",
        instruction="Move to the designated shelter.",
        expires=datetime.now(timezone.utc) + timedelta(hours=12),
    )
    validate_cap(xml)
    assert "<status>Exercise</status>" in xml
    with pytest.raises(ValueError):
        build_cap(
            identifier="bad", sender="x", level="CRITICAL", area_description="z",
            polygon=[(1, 1), (2, 2), (3, 3)],
            headline="h", description="d", instruction="i",
            expires=datetime.now(timezone.utc),
        )


def test_audit_chain_detects_tampering_and_critical_needs_two_channels():
    chain = AuditChain()
    chain.append("expert-1", "review", {"event_id": "e1"})
    chain.append("authority-1", "approve", {"event_id": "e1"})
    assert chain.verify()
    chain.records[0].payload["event_id"] = "tampered"
    assert chain.verify() is False
    with pytest.raises(ValueError):
        required_channels("CRITICAL", {"critical": ["sms"]})
    assert len(required_channels("CRITICAL", {"critical": ["sms", "sirens"]})) == 2
