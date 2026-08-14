from __future__ import annotations

import re
from typing import Any

from .models import Gap, ProcessDefinition, ProcessStep, Provenance, ReviewResult, Value


def is_topic_only(message: str) -> bool:
    text = message.strip()
    action_markers = (
        " then ",
        " verifies ",
        " updates ",
        " approves ",
        " sends ",
        " refreshes ",
        " stores ",
    )
    return len(text.split()) < 18 and not any(x in text.lower() for x in action_markers)


def first_response(message: str) -> str:
    if is_topic_only(message):
        return (
            "**SOP Recommended: Yes**\n\nThis process may benefit from consistent execution, clear ownership, "
            "and training. Please describe the process from start to finish so I can assess maturity and governance gaps."
        )
    return "Thank you. I will extract the process information and assess its documentation readiness."


def extract_process(title: str, description: str) -> ProcessDefinition:
    p = ProcessDefinition()
    p.sop_title = Value(title.strip(), Provenance.USER)
    p.purpose = Value(
        f"The purpose of this SOP is to standardize {title.strip().lower()}.",
        Provenance.INFERRED,
    )
    p.in_scope = Value(
        f"Activities required to complete {title.strip().lower()}.", Provenance.INFERRED
    )
    p.out_of_scope = Value("TBD", Provenance.MISSING)
    sentences = [
        s.strip()
        for s in re.split(r"[.\n]+", description)
        if len(s.strip().split()) >= 3
    ]
    roles = []
    for sentence in sentences:
        role_match = re.match(
            r"(?:If it is missing,\s*)?(?:The\s+)?([A-Z][A-Za-z ]{1,35}?)(?:\s+(?:verifies|works|updates|refreshes|sends|launches|validates|approves|stores|informs))\b",
            sentence,
        )
        role = role_match.group(1).strip() if role_match else "TBD"
        if role not in roles and role != "TBD":
            roles.append(role)
        p.process_steps.append(
            ProcessStep(len(p.process_steps) + 1, role, sentence, Provenance.USER)
        )
    if p.process_steps:
        p.process_trigger = Value(p.process_steps[0].action, Provenance.INFERRED)
        p.process_output = Value(p.process_steps[-1].action, Provenance.INFERRED)
    primary = next((r for r in roles if "Analyst" in r), roles[0] if roles else None)
    if primary:
        p.responsible_role = Value(primary, Provenance.INFERRED)
    p.consulted_roles = Value(
        [r for r in roles if r != primary],
        Provenance.INFERRED if roles else Provenance.MISSING,
    )
    p.validate()
    return p


def apply_demo_clarification(p: ProcessDefinition, text: str) -> None:
    low = text.lower()
    if "analytics manager" in low:
        p.accountable_role = Value("Analytics Manager", Provenance.USER)
    if "business requester" in low and "validat" in low:
        p.validation_criteria = Value(
            "Business requester validates the dashboard update", Provenance.USER
        )
    if "approv" in low:
        p.approvals = Value("Analytics Manager approves release", Provenance.USER)
    if "sharepoint" in low:
        p.required_records = Value(
            "Request ticket and validation email stored in SharePoint", Provenance.USER
        )


GAP_RULES = [
    (
        "responsible",
        "Missing Responsible role",
        "No single role is assigned to execute the process.",
        "Who is responsible for executing the process?",
    ),
    (
        "accountable",
        "Accountable role missing",
        "No single process owner is accountable for the outcome.",
        "Who is accountable for this process?",
    ),
    (
        "approval",
        "Approval not defined",
        "Release authority and decision point are not documented.",
        "Who approves the completed output?",
    ),
    (
        "validation",
        "Validation criteria not defined",
        "Success criteria are not sufficiently explicit.",
        "How is the completed output validated?",
    ),
    (
        "records",
        "Required records not specified",
        "Evidence of completion and its storage location are absent.",
        "What evidence is retained, and where?",
    ),
    (
        "escalation",
        "Escalation path missing",
        "Exceptions or rejected requests have no documented route.",
        "What happens when the request is rejected or blocked?",
    ),
]


def governance_gaps(p: ProcessDefinition) -> list[Gap]:
    checks = {
        "responsible": p.responsible_role,
        "accountable": p.accountable_role,
        "approval": p.approvals,
        "validation": p.validation_criteria,
        "records": p.required_records,
        "escalation": p.escalation_path,
    }
    return [Gap(*rule) for rule in GAP_RULES if not checks[rule[0]].present()]


def readiness(p: ProcessDefinition) -> dict:
    # Explicit weighted method, rounded to whole percentage points.
    checks = {
        "process_owner_defined": (p.accountable_role.present(), 20),
        "roles_defined": (p.responsible_role.present(), 15),
        "trigger_defined": (p.process_trigger.present(), 15),
        "output_defined": (p.process_output.present(), 15),
        "approvals_defined": (p.approvals.present(), 15),
        "records_defined": (p.required_records.present(), 10),
        "steps_defined": (bool(p.process_steps), 10),
    }
    return {
        "sop_recommendation": "Yes",
        **{k: v[0] for k, v in checks.items()},
        "documentation_readiness_score": sum(
            weight for ok, weight in checks.values() if ok
        ),
    }


SECTION_ORDER = [
    "Document Control",
    "Purpose",
    "Scope",
    "References and Terminology",
    "Roles and Responsibilities",
    "Process Flow",
    "Procedure",
    "Record of revisions",
    "Appendices",
]


def generate_draft(p: ProcessDefinition, cycle: int = 1) -> dict:
    def val(item: Value, default: Any = "TBD") -> Any:
        return item.value if item.present() else default

    roles = {
        "Responsible": val(p.responsible_role),
        "Accountable": val(p.accountable_role),
        "Consulted": ", ".join(val(p.consulted_roles, [])) or "TBD",
        "Informed": ", ".join(val(p.informed_roles, [])) or "TBD",
    }
    steps = [
        {
            "order": s.order,
            "role": s.role or "TBD",
            "action": s.action.rstrip(".") + ".",
        }
        for s in p.process_steps
    ]
    return {
        "title": val(p.sop_title),
        "qd_reference": val(p.qd_reference),
        "version": "1.0",
        "effective_date": "TBD",
        "sections": {
            "Document Control": val(p.document_control_information, {}),
            "Purpose": val(p.purpose),
            "Scope": {"In-scope": val(p.in_scope), "Out-of-scope": val(p.out_of_scope)},
            "References and Terminology": val(p.references, []),
            "Roles and Responsibilities": roles,
            "Process Flow": val(p.process_flow_reference),
            "Procedure": {
                "General considerations": val(p.general_considerations),
                "Process details": steps,
            },
            "Record of revisions": [
                {
                    "Version": "1.0",
                    "Effective Date": "TBD",
                    "Nature of Revision": "New SOP",
                }
            ],
            "Appendices": val(p.appendices, []) or "None",
        },
        "trigger": val(p.process_trigger),
        "output": val(p.process_output),
        "approvals": val(p.approvals),
        "validation": val(p.validation_criteria),
        "records": val(p.required_records),
        "cycle": cycle,
        "provenance_snapshot": p.to_dict(),
    }


def review_draft(d: dict, cycle: int) -> ReviewResult:
    blocking = []
    passed = []
    sections = d.get("sections", {})

    def check(ok: bool, label: str):
        (passed if ok else blocking).append(label if ok else label)

    check(list(sections) == SECTION_ORDER, "Required sections exist in TMP-10031 order")
    check(
        str(sections.get("Purpose", "")).startswith("The purpose of this SOP is to"),
        "Purpose uses mandatory opening",
    )
    scope = sections.get("Scope", {})
    check(
        bool(scope.get("In-scope")) and bool(scope.get("Out-of-scope")),
        "Scope includes in-scope and out-of-scope",
    )
    roles = sections.get("Roles and Responsibilities", {})
    check(
        all(
            roles.get(x)
            for x in ("Responsible", "Accountable", "Consulted", "Informed")
        ),
        "RACI is complete or explicitly TBD",
    )
    steps = sections.get("Procedure", {}).get("Process details", [])
    check(
        bool(steps) and all(x.get("role") and x.get("action") for x in steps),
        "Ordered actionable steps have roles",
    )
    for key, label in (
        ("trigger", "Trigger is defined"),
        ("output", "Output is defined"),
        ("approvals", "Approvals captured or TBD"),
        ("records", "Records captured or TBD"),
    ):
        check(bool(d.get(key)), label)
    check(
        bool(sections.get("Process Flow")), "Process flow is supplied or explicitly TBD"
    )
    vague = any(
        re.search(
            r"\b(etc\.|and so on|if applicable|where needed)\b",
            x.get("action", ""),
            re.I,
        )
        for x in steps
    )
    check(not vague, "Vague expressions are avoided")
    check(bool(sections.get("Record of revisions")), "Revision history exists")
    check("Appendices" in sections, "Appendices section exists")
    score = max(0, round(100 * len(passed) / (len(passed) + len(blocking))))
    return ReviewResult(
        cycle,
        score,
        blocking,
        passed,
        (
            ["Resolve remaining TBD governance values before controlled publication"]
            if "TBD" in str(d)
            else []
        ),
        blocking[:],
    )


def review_loop(
    p: ProcessDefinition, max_cycles: int = 3
) -> tuple[dict, list[ReviewResult]]:
    reviews = []
    draft = {}
    for cycle in range(1, min(max_cycles, 3) + 1):
        draft = generate_draft(p, cycle)
        result = review_draft(draft, cycle)
        reviews.append(result)
        if not result.blocking_issues and result.score >= 90:
            break
    return draft, reviews
