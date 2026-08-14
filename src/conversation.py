from __future__ import annotations

import re
from typing import Any

from .agents import first_response, governance_gaps, is_topic_only, readiness
from .models import FIELDS, ProcessDefinition, ProcessStep, Provenance, Value
from .openai_service import OpenAIService

QUESTION_PRIORITY = [
    "accountable",
    "approval",
    "validation",
    "records",
    "escalation",
    "responsible",
]


def assessment_message(process: ProcessDefinition, next_prompt: str) -> str:
    maturity = readiness(process)
    gaps = governance_gaps(process)
    captured = []
    for label, value in (
        ("Responsible", process.responsible_role),
        ("Accountable", process.accountable_role),
        ("Trigger", process.process_trigger),
        ("Output", process.process_output),
    ):
        if value.present():
            captured.append(f"✅ **{label}:** {value.value}")
    lines = [
        "### Process Maturity Assessment",
        "- **SOP Recommended:** Yes",
        f"- **Documentation readiness:** {maturity['documentation_readiness_score']}%",
    ]
    if captured:
        lines += ["", "### Information captured", *captured]
    if gaps:
        lines += ["", "### Governance gaps"] + [
            f"⚠️ **{gap.label}** — {gap.reason}" for gap in gaps
        ]
    lines += ["", f"**Next question:** {next_prompt}"]
    return "\n".join(lines)


def merge_updates(
    process: ProcessDefinition,
    updates: Any,
    provenance: Provenance = Provenance.USER,
) -> None:
    """Merge supported fields without erasing previous state or accepting unknown fields."""
    if not isinstance(updates, dict):
        return
    for name, value in updates.items():
        if name == "process_steps" and isinstance(value, list):
            existing = {step.action.lower() for step in process.process_steps}
            for item in value:
                if isinstance(item, str):
                    action = item.strip()
                    role = "TBD"
                elif isinstance(item, dict):
                    action = str(item.get("action", "")).strip()
                    role = str(item.get("role") or "TBD").strip()
                else:
                    continue
                if action and action.lower() not in existing:
                    process.process_steps.append(
                        ProcessStep(
                            len(process.process_steps) + 1,
                            role,
                            action,
                            provenance,
                        )
                    )
                    existing.add(action.lower())
            continue
        if name in FIELDS and value not in (None, "", []):
            current = getattr(process, name)
            if not current.present() or current.provenance in (
                Provenance.INFERRED,
                Provenance.MISSING,
            ):
                setattr(process, name, Value(value, provenance))
    process.validate()


def deterministic_updates(message: str, process: ProcessDefinition) -> dict[str, Any]:
    """Conservative fallback extraction for conversational use without an API key."""
    low = message.lower()
    updates: dict[str, Any] = {}
    if not process.sop_title.present():
        title = re.sub(
            r"^(please\s+)?(create|write|build|make)\s+(an?\s+)?sop\s+(for|about)\s+",
            "",
            message,
            flags=re.I,
        ).strip(" .")
        updates["sop_title"] = title or message.strip(" .")
    if "accountable" in low:
        match = re.search(
            r"(?:the\s+)?([A-Z][A-Za-z &/-]{2,50}?)\s+(?:is|will be)\s+accountable",
            message,
        )
        if match:
            updates["accountable_role"] = match.group(1).strip()
    if "responsible" in low:
        match = re.search(
            r"(?:the\s+)?([A-Z][A-Za-z &/-]{2,50}?)\s+(?:is|will be)\s+responsible",
            message,
        )
        if match:
            updates["responsible_role"] = match.group(1).strip()
    if "approv" in low:
        updates["approvals"] = message.strip()
    if "validat" in low:
        updates["validation_criteria"] = message.strip()
    if any(word in low for word in ("stored", "retained", "record", "evidence")):
        updates["required_records"] = message.strip()
    if any(word in low for word in ("escalat", "rejected", "blocked")):
        updates["escalation_path"] = message.strip()
    if "process output" in low or "final output" in low:
        updates["process_output"] = message.strip()
    if "in scope" in low or "in-scope" in low:
        updates["in_scope"] = message.strip()
    if "out of scope" in low or "out-of-scope" in low:
        updates["out_of_scope"] = message.strip()
    author = re.search(
        r"(?:written by|sop author is|author is)[:\s]+([^.;]+)", message, re.I
    )
    if author:
        current = (
            process.document_control_information.value
            if isinstance(process.document_control_information.value, dict)
            else {}
        )
        updates["document_control_information"] = {
            **current,
            "written_by": author.group(1).strip(),
        }
    action_sentences = [
        s.strip() for s in re.split(r"[.\n]+", message) if len(s.split()) >= 5
    ]
    steps = []
    verbs = r"receives|checks|verifies|creates|updates|sends|approves|validates|stores|refreshes|informs|reviews|submits|works"
    for sentence in action_sentences:
        match = re.match(
            rf"(?:Then,?\s*)?(?:The\s+)?([A-Z][A-Za-z ]{{1,40}}?)\s+({verbs})\b",
            sentence,
        )
        if match:
            steps.append({"role": match.group(1).strip(), "action": sentence})
    if steps:
        updates["process_steps"] = steps
        if not process.process_trigger.present():
            updates["process_trigger"] = steps[0]["action"]
        updates["process_output"] = steps[-1]["action"]
        if not process.responsible_role.present():
            updates["responsible_role"] = steps[0]["role"]
        if not process.purpose.present() and process.sop_title.present():
            updates["purpose"] = (
                f"The purpose of this SOP is to standardize {str(process.sop_title.value).lower()}."
            )
            updates["in_scope"] = (
                f"Activities required to complete {str(process.sop_title.value).lower()}."
            )
    return updates


def next_question(process: ProcessDefinition) -> str:
    gaps = {gap.code: gap for gap in governance_gaps(process)}
    for code in QUESTION_PRIORITY:
        if code in gaps:
            return gaps[code].question
    if not process.process_steps:
        return "What happens from the moment this process starts until its final output is delivered?"
    for field, question in (
        (
            process.process_output,
            "What is the final process output, and who receives it?",
        ),
        (process.in_scope, "What activities are explicitly in scope?"),
        (process.out_of_scope, "What is explicitly out of scope? You may answer None."),
    ):
        if not field.present():
            return question
    document_control = (
        process.document_control_information.value
        if isinstance(process.document_control_information.value, dict)
        else {}
    )
    if not document_control.get("written_by"):
        return "Who is the SOP author? Please provide the name and function title."
    return "The essential information is captured. You can add more detail or generate the reviewed SOP draft."


def handle_turn(
    message: str,
    process: ProcessDefinition,
    history: list[dict[str, str]],
    ai: OpenAIService,
) -> tuple[str, str]:
    """Return assistant text and mode, always preserving a local fallback."""
    first_turn = not history
    if first_turn and is_topic_only(message):
        merge_updates(process, deterministic_updates(message, process))
        return first_response(message), "guard"
    had_steps = bool(process.process_steps)
    if ai.enabled:
        try:
            result = ai.structured_turn(
                history + [{"role": "user", "content": message}], process.to_dict()
            )
            merge_updates(process, result.get("updates", {}))
            question = str(result["assistant_message"])
            return (
                assessment_message(process, question)
                if not had_steps and process.process_steps
                else f"✅ **Information updated.**\n\n{question}"
            ), "ai"
        except (RuntimeError, ValueError):
            pass
    merge_updates(process, deterministic_updates(message, process))
    question = next_question(process)
    return (
        assessment_message(process, question)
        if not had_steps and process.process_steps
        else f"✅ **Information updated.**\n\n**Next question:** {question}"
    ), "local"
