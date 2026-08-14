from pathlib import Path
import hashlib
from zipfile import ZipFile

import pytest

from scripts.run_demo import CLARIFICATION, DESCRIPTION, TITLE
from src.agents import (
    SECTION_ORDER,
    apply_demo_clarification,
    completeness,
    consolidate_steps,
    extract_process,
    first_response,
    generate_draft,
    governance_gaps,
    is_topic_only,
    readiness,
    review_draft,
)
from src.document import PLACEHOLDER, inspect_template, populate_template, validate_docx
from src.conversation import handle_turn, merge_updates
from src.knowledge import LocalKnowledgeService
from src.models import ProcessDefinition, ProcessStep, Provenance, Value
from src.openai_service import OpenAIService
from src.repository import ProjectRepository


@pytest.fixture
def complete_process():
    p = extract_process(TITLE, DESCRIPTION)
    apply_demo_clarification(p, CLARIFICATION)
    return p


def test_process_definition_validation():
    p = ProcessDefinition(sop_title=Value("X", Provenance.USER))
    with pytest.raises(ValueError):
        p.validate()
    p.sop_title.value = "Valid"
    p.process_steps = [ProcessStep(2, "Role", "Act")]
    with pytest.raises(ValueError):
        p.validate()


def test_persistence_and_session_restoration(tmp_path, complete_process):
    repo = ProjectRepository(tmp_path / "state.db")
    pid = repo.create(TITLE)
    repo.message(pid, "user", "hello")
    repo.save_process(pid, complete_process, "ready")
    repo.artifact(pid, "gap", {"x": 1})
    restored = ProjectRepository(tmp_path / "state.db").load(pid)
    assert restored["process"].accountable_role.value == "Analytics Manager"
    assert repo.messages(pid)[0]["content"] == "hello" and repo.artifacts(pid, "gap")[
        0
    ]["payload"] == {"x": 1}


def test_generated_file_history_and_compatibility_alias(tmp_path):
    repo = ProjectRepository(tmp_path / "state.db")
    pid = repo.create(TITLE)
    repo.generated_file(pid, "generated/example.docx", {"valid": True, "errors": []})
    expected = repo.list_generated_files(pid)
    assert expected[0]["path"] == "generated/example.docx"
    assert expected[0]["validation"] == {"valid": True, "errors": []}
    assert repo.files(pid) == expected


def test_internal_review_workflow_persists_decisions(tmp_path):
    repo = ProjectRepository(tmp_path / "state.db")
    pid = repo.create(TITLE)
    repo.submit_for_review(pid, "Controller One")
    assert repo.load(pid)["status"] == "submitted"
    assert repo.projects_by_status(("submitted",))[0]["id"] == pid
    repo.record_review(pid, "changes_requested", "Controller One", "Clarify scope")
    assert repo.load(pid)["status"] == "changes_requested"
    assert repo.review_history(pid)[-1]["comment"] == "Clarify scope"
    with pytest.raises(ValueError, match="controller name"):
        repo.record_review(pid, "validated", "", "")


def test_first_message_generation_guard():
    msg = "Create an SOP for product hierarchy maintenance."
    assert is_topic_only(msg) and "Please describe the process" in first_response(msg)
    assert "document" not in first_response(msg).lower()


def test_governance_rules_and_targeted_questions():
    p = extract_process(TITLE, DESCRIPTION)
    gaps = {x.label: x for x in governance_gaps(p)}
    for expected in (
        "Accountable role missing",
        "Approval not defined",
        "Validation criteria not defined",
        "Required records not specified",
    ):
        assert expected in gaps
    assert all(g.question.endswith("?") for g in gaps.values())


def test_readiness_explicit_weighting(complete_process):
    result = readiness(complete_process)
    assert result["documentation_readiness_score"] == 100
    complete_process.required_records = Value()
    assert readiness(complete_process)["documentation_readiness_score"] == 90


def test_required_section_order_and_generation(complete_process):
    draft = generate_draft(complete_process)
    assert list(draft["sections"]) == SECTION_ORDER
    assert draft["sections"]["Purpose"].startswith("The purpose of this SOP is to")
    assert draft["sections"]["Record of revisions"][0]["Version"] == "1.0"


def test_completeness_blocks_missing_mandatory_fields(complete_process):
    assert completeness(complete_process)["ready_for_review"]
    complete_process.validation_criteria = Value()
    result = completeness(complete_process)
    assert not result["ready_for_review"]
    assert "Validation criteria" in result["blocking"]


def test_consolidates_overlapping_conversational_steps():
    steps = [
        ProcessStep(
            1, "Agent", "The Agent updates the ticket and informs the customer."
        ),
        ProcessStep(
            2, "Agent", "The Agent updates the ticket and informs the customer."
        ),
        ProcessStep(3, "Manager", "The Manager approves the final resolution."),
    ]
    result = consolidate_steps(steps)
    assert [step.order for step in result] == [1, 2]
    assert len(result) == 2


def test_reviewer_does_not_treat_tbd_as_complete(complete_process):
    complete_process.out_of_scope = Value("TBD", Provenance.MISSING)
    review = review_draft(generate_draft(complete_process), 1)
    assert "Scope includes in-scope and out-of-scope" in review.blocking_issues
    assert review.score < 100


def test_reviewer_blocking_checks(complete_process):
    draft = generate_draft(complete_process)
    draft["sections"].pop("Purpose")
    review = review_draft(draft, 1)
    assert review.blocking_issues and review.score < 90


def test_review_loop_maximum_iterations(complete_process, monkeypatch):
    import src.agents as agents

    original = agents.review_draft

    def always_fail(d, c):
        r = original(d, c)
        r.blocking_issues = ["forced"]
        r.score = 10
        return r

    monkeypatch.setattr(agents, "review_draft", always_fail)
    _, reviews = agents.review_loop(complete_process, max_cycles=10)
    assert len(reviews) == 3


def test_knowledge_retrieval(tmp_path):
    (tmp_path / "guide.md").write_text(
        "Power BI governance requires validation evidence and accountable ownership."
    )
    hits = LocalKnowledgeService(tmp_path).retrieve("Power BI validation governance")
    assert hits[0]["source"] == "guide.md" and hits[0]["score"] > 0


def test_template_inspection():
    info = inspect_template(
        "reference_documents/templates/TMP-10031_SOP_TemplateCC.docx"
    )
    assert info == {
        "parts": 39,
        "content_controls": 17,
        "tables": 3,
        "bookmarks": 1,
        "has_header": True,
        "has_footer": True,
    }


def test_template_population_placeholders_integrity_and_revision(
    tmp_path, complete_process
):
    template = Path("reference_documents/templates/TMP-10031_SOP_TemplateCC.docx")
    before = hashlib.sha256(template.read_bytes()).hexdigest()
    out = populate_template(template, generate_draft(complete_process), tmp_path)
    result = validate_docx(out)
    assert result["valid"], result["errors"]
    with ZipFile(out) as z:
        assert z.testzip() is None
        body = z.read("word/document.xml").decode("utf-8")
        assert PLACEHOLDER not in body and "New SOP" in body and "1.0" in body
        assert "word/styles.xml" in z.namelist() and "word/footer1.xml" in z.namelist()
    assert hashlib.sha256(template.read_bytes()).hexdigest() == before


def test_source_documents_are_organized():
    assert Path("reference_documents/prompt/Prompt SOP.docx").is_file()
    assert Path("reference_documents/presentation/SOP Builder.pptx").is_file()
    assert Path("reference_documents/templates/TMP-10031_SOP_TemplateCC.docx").is_file()


def test_end_to_end_demo(tmp_path, monkeypatch):
    from scripts.run_demo import run

    for name in ("reference_documents", "knowledge_base"):
        src = Path(name)
        dst = tmp_path / name
        if src.is_dir():
            import shutil

            shutil.copytree(src, dst)
        else:
            dst.write_bytes(src.read_bytes())
    result = run(tmp_path)
    assert result["validation"]["valid"]
    assert all(
        x in result["initial_gaps"]
        for x in (
            "Accountable role missing",
            "Approval not defined",
            "Validation criteria not defined",
            "Required records not specified",
        )
    )
    assert Path(result["file"]).exists() and result["review_scores"][-1] >= 90


def test_multi_turn_conversation_preserves_guard_and_asks_targeted_question():
    process = ProcessDefinition()
    ai = OpenAIService(api_key="")
    response, mode = handle_turn(
        "Create an SOP for customer complaint handling", process, [], ai
    )
    assert mode == "guard" and "describe the process" in response.lower()
    history = [
        {"role": "user", "content": "Create an SOP for customer complaint handling"},
        {"role": "assistant", "content": response},
    ]
    response, mode = handle_turn(
        "The Service Agent receives the complaint. The Service Agent reviews the details and informs the customer.",
        process,
        history,
        ai,
    )
    assert mode == "local" and process.process_steps
    assert "Who is accountable for this process?" in response
    assert "Process Maturity Assessment" in response


def test_merge_does_not_overwrite_user_governance():
    process = ProcessDefinition(
        accountable_role=Value("Process Owner", Provenance.USER)
    )
    merge_updates(
        process,
        {"accountable_role": "Invented Owner", "unknown": "ignored"},
        Provenance.INFERRED,
    )
    assert process.accountable_role.value == "Process Owner"
    assert not hasattr(process, "unknown")


def test_merge_accepts_ai_process_steps_as_strings_or_objects():
    process = ProcessDefinition(sop_title=Value("Complaint handling", Provenance.USER))
    merge_updates(
        process,
        {
            "process_steps": [
                "The Service Agent receives the complaint.",
                {
                    "role": "Service Agent",
                    "action": "The Service Agent reviews the complaint.",
                },
                42,
                {"role": "Service Agent"},
            ]
        },
    )
    assert [(step.role, step.action) for step in process.process_steps] == [
        ("TBD", "The Service Agent receives the complaint."),
        ("Service Agent", "The Service Agent reviews the complaint."),
    ]


def test_merge_ignores_non_mapping_ai_updates():
    process = ProcessDefinition(sop_title=Value("Complaint handling", Provenance.USER))
    merge_updates(process, "invalid updates")
    assert process.process_steps == []


def test_knowledge_upload_preview_download_and_delete(tmp_path):
    service = LocalKnowledgeService(tmp_path)
    source = service.add(
        "approval guide.md", b"Approval evidence is retained in SharePoint."
    )
    assert service.sources()[0]["preview"].startswith("Approval evidence")
    assert (
        service.retrieve("approval evidence SharePoint")[0]["source"]
        == "approval guide.md"
    )
    service.delete(source)
    assert service.sources() == []


def test_openai_conversational_turn_parses_structured_response(monkeypatch):
    import io
    import urllib.request

    class Response:
        def __enter__(self):
            return io.BytesIO(
                b'{"output_text":"{\\"assistant_message\\":\\"Who approves release?\\",\\"updates\\":{\\"responsible_role\\":\\"Analyst\\"},\\"ready_to_generate\\":false}"}'
            )

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: Response())
    result = OpenAIService(api_key="test-key").structured_turn(
        [], ProcessDefinition().to_dict()
    )
    assert result["assistant_message"] == "Who approves release?"
    assert result["updates"] == {"responsible_role": "Analyst"}
