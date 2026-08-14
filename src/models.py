from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Provenance(str, Enum):
    USER = "user provided"
    DOCUMENT = "extracted from uploaded document"
    INFERRED = "inferred"
    MISSING = "missing / TBD"


@dataclass
class Value:
    value: Any = None
    provenance: Provenance = Provenance.MISSING

    def present(self) -> bool:
        return self.value not in (None, "", [], "TBD")

    def explicit_none(self) -> bool:
        return str(self.value).strip().lower() in {"none", "not applicable", "n/a"}


@dataclass
class ProcessStep:
    order: int
    role: str
    action: str
    provenance: Provenance = Provenance.USER


FIELDS = (
    "sop_title",
    "qd_reference",
    "purpose",
    "in_scope",
    "out_of_scope",
    "responsible_role",
    "accountable_role",
    "consulted_roles",
    "informed_roles",
    "process_trigger",
    "process_output",
    "approvals",
    "validation_criteria",
    "required_records",
    "escalation_path",
    "references",
    "process_flow_reference",
    "general_considerations",
    "document_control_information",
    "appendices",
)


@dataclass
class ProcessDefinition:
    sop_title: Value = field(default_factory=Value)
    qd_reference: Value = field(default_factory=Value)
    purpose: Value = field(default_factory=Value)
    in_scope: Value = field(default_factory=Value)
    out_of_scope: Value = field(default_factory=Value)
    responsible_role: Value = field(default_factory=Value)
    accountable_role: Value = field(default_factory=Value)
    consulted_roles: Value = field(default_factory=lambda: Value([]))
    informed_roles: Value = field(default_factory=lambda: Value([]))
    process_trigger: Value = field(default_factory=Value)
    process_output: Value = field(default_factory=Value)
    process_steps: list[ProcessStep] = field(default_factory=list)
    approvals: Value = field(default_factory=Value)
    validation_criteria: Value = field(default_factory=Value)
    required_records: Value = field(default_factory=Value)
    escalation_path: Value = field(default_factory=Value)
    references: Value = field(default_factory=lambda: Value([]))
    process_flow_reference: Value = field(default_factory=Value)
    general_considerations: Value = field(default_factory=Value)
    document_control_information: Value = field(default_factory=lambda: Value({}))
    appendices: Value = field(default_factory=lambda: Value([]))

    def validate(self) -> None:
        if self.sop_title.present() and len(str(self.sop_title.value).strip()) < 3:
            raise ValueError("SOP title must contain at least three characters")
        orders = [s.order for s in self.process_steps]
        if orders and orders != list(range(1, len(orders) + 1)):
            raise ValueError("Process steps must be consecutively ordered from 1")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProcessDefinition":
        kwargs: dict[str, Any] = {
            n: Value(
                data.get(n, {}).get("value"),
                Provenance(data.get(n, {}).get("provenance", Provenance.MISSING)),
            )
            for n in FIELDS
        }
        kwargs["process_steps"] = [
            ProcessStep(
                **{**x, "provenance": Provenance(x.get("provenance", Provenance.USER))}
            )
            for x in data.get("process_steps", [])
        ]
        return cls(**kwargs)


@dataclass
class Gap:
    code: str
    label: str
    reason: str
    question: str


@dataclass
class ReviewResult:
    cycle: int
    score: int
    blocking_issues: list[str]
    passed_checks: list[str]
    recommendations: list[str]
    suggested_revisions: list[str]
