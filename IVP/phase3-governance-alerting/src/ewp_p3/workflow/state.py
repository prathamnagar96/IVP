"""Explicit Phase 3 workflow state machine and approval gate."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List


class EventState(str, Enum):
    MONITORING = "MONITORING"
    TRIGGERED = "TRIGGERED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ESCALATED = "ESCALATED"
    AWAITING_AUTHORITY = "AWAITING_AUTHORITY"
    BROADCAST = "BROADCAST"
    ACTIVE = "ACTIVE"
    DE_ESCALATING = "DE_ESCALATING"
    CLOSED = "CLOSED"


class Role(str, Enum):
    EXPERT = "DGE"
    AUTHORITY = "CADO"


class Decision(str, Enum):
    CONFIRM = "CONFIRM"
    REJECT = "REJECT"
    DOWNGRADE = "DOWNGRADE"
    APPROVE = "APPROVE"


@dataclass(frozen=True)
class Approval:
    role: Role
    user_id: str
    decision: Decision
    comment: str
    at: datetime
    evidence_hash: str


@dataclass
class EventWorkflow:
    event_id: str
    proposed_level: str
    state: EventState = EventState.MONITORING
    approvals: Dict[Role, Approval] = field(default_factory=dict)
    transitions: List[dict] = field(default_factory=list)
    review_deadline: datetime | None = None

    def _transition(self, target: EventState, actor: str, reason: str, now: datetime) -> None:
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        self.transitions.append({
            "from": self.state.value,
            "to": target.value,
            "at": now.isoformat(),
            "actor": actor,
            "reason": reason,
        })
        self.state = target

    def trigger(self, actor: str = "phase2", now: datetime | None = None) -> None:
        self._transition(EventState.TRIGGERED, actor, "machine proposal received", now or datetime.now(timezone.utc))
        self._transition(EventState.UNDER_REVIEW, "system", "review task created", now or datetime.now(timezone.utc))

    def add_decision(
        self,
        *,
        role: Role,
        user_id: str,
        decision: Decision,
        comment: str,
        evidence_hash: str,
        now: datetime | None = None,
    ) -> None:
        if not user_id or not comment.strip() or not evidence_hash:
            raise ValueError("user_id, comment, and evidence_hash are required")
        if role == Role.AUTHORITY and self.approvals.get(Role.EXPERT, None) is None:
            raise PermissionError("authority approval requires an expert decision first")
        if role == Role.AUTHORITY:
            expert = self.approvals.get(Role.EXPERT)
            if expert is not None and expert.user_id == user_id:
                raise PermissionError("expert and authority approvals require distinct identities")
        timestamp = now or datetime.now(timezone.utc)
        self.approvals[role] = Approval(role, user_id, decision, comment, timestamp, evidence_hash)
        if role == Role.EXPERT:
            if decision == Decision.REJECT:
                self._transition(EventState.CLOSED, user_id, comment, timestamp)
            elif decision in (Decision.CONFIRM, Decision.DOWNGRADE):
                self._transition(EventState.AWAITING_AUTHORITY, user_id, comment, timestamp)
        elif role == Role.AUTHORITY:
            if decision == Decision.APPROVE:
                self._transition(EventState.BROADCAST, user_id, comment, timestamp)
            elif decision == Decision.REJECT:
                self._transition(EventState.CLOSED, user_id, comment, timestamp)

    def can_broadcast(self) -> bool:
        expert = self.approvals.get(Role.EXPERT)
        authority = self.approvals.get(Role.AUTHORITY)
        return (
            self.state == EventState.BROADCAST
            and expert is not None
            and authority is not None
            and expert.decision in (Decision.CONFIRM, Decision.DOWNGRADE)
            and authority.decision == Decision.APPROVE
            and expert.user_id != authority.user_id
        )

    def escalate_if_expired(
        self,
        *,
        now: datetime,
        expert_deadline_minutes: int,
        actor: str = "system",
    ) -> bool:
        if self.state not in (EventState.UNDER_REVIEW, EventState.AWAITING_AUTHORITY):
            return False
        if self.review_deadline is None:
            self.review_deadline = self.transitions[-1]["at"]
            start = datetime.fromisoformat(self.review_deadline)
            self.review_deadline = start + timedelta(minutes=expert_deadline_minutes)
        if now >= self.review_deadline:
            self._transition(EventState.ESCALATED, actor, "SLA expired; notify backup and authority", now)
            return True
        return False

    def close_step(self, *, conditions_clear: bool, expert_user: str, authority_user: str, now: datetime) -> None:
        if self.state not in (EventState.ACTIVE, EventState.BROADCAST):
            raise ValueError("only active events can de-escalate")
        if not conditions_clear:
            raise ValueError("all-clear conditions are not satisfied")
        if expert_user == authority_user:
            raise PermissionError("expert and authority must be distinct identities")
        self._transition(EventState.DE_ESCALATING, expert_user, "clearing conditions verified", now)
        self._transition(EventState.CLOSED, authority_user, "all-clear approved", now)
