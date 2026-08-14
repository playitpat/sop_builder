from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.run_demo import CLARIFICATION, DESCRIPTION, TITLE
from src.agents import (SECTION_ORDER, apply_demo_clarification, extract_process,
                        first_response, generate_draft, governance_gaps,
                        is_topic_only, readiness, review_draft)
from src.document import PLACEHOLDER, inspect_template, populate_template, validate_docx
from src.knowledge import LocalKnowledgeService
from src.models import ProcessDefinition, ProcessStep, Provenance, Value
from src.repository import ProjectRepository


@pytest.fixture
def complete_process():
    p=extract_process(TITLE,DESCRIPTION); apply_demo_clarification(p,CLARIFICATION); return p


def test_process_definition_validation():
    p=ProcessDefinition(sop_title=Value("X",Provenance.USER))
    with pytest.raises(ValueError): p.validate()
    p.sop_title.value="Valid"; p.process_steps=[ProcessStep(2,"Role","Act")]
    with pytest.raises(ValueError): p.validate()


def test_persistence_and_session_restoration(tmp_path,complete_process):
    repo=ProjectRepository(tmp_path/"state.db"); pid=repo.create(TITLE); repo.message(pid,"user","hello")
    repo.save_process(pid,complete_process,"ready"); repo.artifact(pid,"gap",{"x":1})
    restored=ProjectRepository(tmp_path/"state.db").load(pid)
    assert restored["process"].accountable_role.value=="Analytics Manager"
    assert repo.messages(pid)[0]["content"]=="hello" and repo.artifacts(pid,"gap")[0]["payload"]=={"x":1}


def test_first_message_generation_guard():
    msg="Create an SOP for product hierarchy maintenance."
    assert is_topic_only(msg) and "Please describe the process" in first_response(msg)
    assert "document" not in first_response(msg).lower()


def test_governance_rules_and_targeted_questions():
    p=extract_process(TITLE,DESCRIPTION); gaps={x.label:x for x in governance_gaps(p)}
    for expected in ("Accountable role missing","Approval not defined","Validation criteria not defined","Required records not specified"): assert expected in gaps
    assert all(g.question.endswith("?") for g in gaps.values())


def test_readiness_explicit_weighting(complete_process):
    result=readiness(complete_process)
    assert result["documentation_readiness_score"]==100
    complete_process.required_records=Value(); assert readiness(complete_process)["documentation_readiness_score"]==90


def test_required_section_order_and_generation(complete_process):
    draft=generate_draft(complete_process)
    assert list(draft["sections"])==SECTION_ORDER
    assert draft["sections"]["Purpose"].startswith("The purpose of this SOP is to")
    assert draft["sections"]["Record of revisions"][0]["Version"]=="1.0"


def test_reviewer_blocking_checks(complete_process):
    draft=generate_draft(complete_process); draft["sections"].pop("Purpose")
    review=review_draft(draft,1)
    assert review.blocking_issues and review.score<90


def test_review_loop_maximum_iterations(complete_process,monkeypatch):
    import src.agents as agents
    original=agents.review_draft
    def always_fail(d,c):
        r=original(d,c); r.blocking_issues=["forced"]; r.score=10; return r
    monkeypatch.setattr(agents,"review_draft",always_fail)
    _,reviews=agents.review_loop(complete_process,max_cycles=10)
    assert len(reviews)==3


def test_knowledge_retrieval(tmp_path):
    (tmp_path/"guide.md").write_text("Power BI governance requires validation evidence and accountable ownership.")
    hits=LocalKnowledgeService(tmp_path).retrieve("Power BI validation governance")
    assert hits[0]["source"]=="guide.md" and hits[0]["score"]>0


def test_template_inspection():
    info=inspect_template("TMP-10031_SOP_TemplateCC.docx")
    assert info=={"parts":39,"content_controls":17,"tables":3,"bookmarks":1,"has_header":True,"has_footer":True}


def test_template_population_placeholders_integrity_and_revision(tmp_path,complete_process):
    out=populate_template("TMP-10031_SOP_TemplateCC.docx",generate_draft(complete_process),tmp_path)
    result=validate_docx(out)
    assert result["valid"],result["errors"]
    with ZipFile(out) as z:
        assert z.testzip() is None
        body=z.read("word/document.xml").decode("utf-8")
        assert PLACEHOLDER not in body and "New SOP" in body and "1.0" in body
        assert "word/styles.xml" in z.namelist() and "word/footer1.xml" in z.namelist()


def test_end_to_end_demo(tmp_path,monkeypatch):
    from scripts.run_demo import run
    for name in ("TMP-10031_SOP_TemplateCC.docx","knowledge_base"):
        src=Path(name); dst=tmp_path/name
        if src.is_dir():
            import shutil; shutil.copytree(src,dst)
        else: dst.write_bytes(src.read_bytes())
    result=run(tmp_path)
    assert result["validation"]["valid"]
    assert all(x in result["initial_gaps"] for x in ("Accountable role missing","Approval not defined","Validation criteria not defined","Required records not specified"))
    assert Path(result["file"]).exists() and result["review_scores"][-1]>=90
