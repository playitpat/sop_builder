from pathlib import Path

import streamlit as st

from src.agents import completeness, readiness, review_loop
from src.conversation import handle_turn
from src.document import populate_template, validate_docx
from src.models import ProcessDefinition
from src.openai_service import OpenAIService
from src.repository import ProjectRepository

TEMPLATE = Path("reference_documents/templates/TMP-10031_SOP_TemplateCC.docx")

st.set_page_config(page_title="Danone SOP Builder Future Version", layout="wide")
st.markdown(
    """<style>
    :root{--navy:#102a43;--blue:#1769c2;--purple:#7253a6}
    .stApp{background:#f7f9fc}.block-container{max-width:1050px;padding-top:1.4rem}
    .hero{padding:1rem 1.3rem;border-left:6px solid var(--purple);background:white;border-radius:12px;margin-bottom:1rem}
    [data-testid="stChatMessage"]{background:white;border:1px solid #e4eaf2;border-radius:12px;padding:.45rem .8rem}
    [data-testid="stSidebar"]{background:#eef2f8}
    </style>""",
    unsafe_allow_html=True,
)

repo = ProjectRepository()
ai = OpenAIService()
st.sidebar.title("SOP Builder")
page = st.sidebar.radio(
    "Workspace", ["Create SOP", "SOP Library", "Internal Review Queue"]
)
st.sidebar.caption(f"AI: {'OpenAI' if ai.enabled else 'Local fallback'}")


def load_project(project_id: str) -> None:
    loaded = repo.load(project_id)
    if loaded:
        st.session_state.project_id = project_id
        st.session_state.process = loaded["process"]
        for key in ("reviews", "validation", "output"):
            st.session_state.pop(key, None)


def status_summary(process: ProcessDefinition) -> None:
    score = readiness(process)["documentation_readiness_score"]
    state = completeness(process)
    with st.expander("Current SOP readiness", expanded=False):
        st.progress(score / 100, text=f"Documentation readiness: {score}%")
        if state["blocking"]:
            st.warning(
                "Still needed before internal review: " + ", ".join(state["blocking"])
            )
        else:
            st.success("All mandatory process information is captured.")
        if state["draft_warnings"]:
            st.info(
                "Draft publication fields still open: "
                + ", ".join(state["draft_warnings"])
            )


def render_review_result(project_id: str, process: ProcessDefinition) -> None:
    if "reviews" not in st.session_state:
        return
    with st.chat_message("assistant"):
        st.markdown("### Automated SOP quality review")
        for review in st.session_state.reviews:
            icon = "✅" if not review.blocking_issues and review.score >= 90 else "❌"
            st.markdown(
                f"{icon} **Draft {review.cycle} → Review {review.cycle}: {review.score}/100**"
            )
            for issue in review.blocking_issues:
                st.markdown(f"- ❌ {issue}")
            for recommendation in review.recommendations:
                st.markdown(f"- ⚠️ {recommendation}")
        validation = st.session_state.validation
        if validation["valid"]:
            st.success("Word document validation passed.")
            output = Path(st.session_state.output)
            st.download_button(
                "Download working SOP draft", output.read_bytes(), file_name=output.name
            )
            state = completeness(process)
            if state["ready_for_review"]:
                if st.button("Submit this SOP for internal review", type="primary"):
                    repo.submit_for_review(project_id)
                    st.success("Submitted to the Internal Review Queue.")
            else:
                st.warning(
                    "Internal review submission is blocked until mandatory fields are resolved: "
                    + ", ".join(state["blocking"])
                )
        else:
            st.error("Word validation failed: " + "; ".join(validation["errors"]))


def render_conversation() -> None:
    st.markdown(
        '<div class="hero"><h1>Danone SOP Builder</h1><p>Describe the process naturally. The agent will assess it once, then ask one targeted question at a time.</p></div>',
        unsafe_allow_html=True,
    )
    if st.button("＋ Start a new SOP"):
        for key in ("project_id", "process", "reviews", "validation", "output"):
            st.session_state.pop(key, None)
        st.rerun()
    project_id = st.session_state.get("project_id")
    process = st.session_state.get("process", ProcessDefinition())
    history = repo.messages(project_id) if project_id else []
    if not history:
        with st.chat_message("assistant"):
            st.markdown("**Hello — what process would you like to document?**")
    for message in history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    render_review_result(project_id, process) if project_id else None
    if project_id:
        status_summary(process)
        state = completeness(process)
        if process.process_steps:
            label = (
                "Generate reviewed working draft"
                if state["blocking"]
                else "Generate reviewed SOP"
            )
            if st.button(label, type="primary"):
                draft, reviews = review_loop(process)
                repo.artifact(project_id, "draft", draft)
                for review in reviews:
                    repo.artifact(project_id, "review", review.__dict__)
                output = populate_template(TEMPLATE, draft)
                validation = validate_docx(output)
                repo.generated_file(project_id, output, validation)
                repo.save_process(project_id, process, "generated")
                st.session_state.reviews = reviews
                st.session_state.validation = validation
                st.session_state.output = str(output)
                st.rerun()
    prompt = st.chat_input("Describe the process or answer the latest question…")
    if prompt:
        if not project_id:
            project_id = repo.create(prompt[:80].strip() or "Untitled SOP")
            st.session_state.project_id = project_id
        conversation = [
            {"role": item["role"], "content": item["content"]} for item in history
        ]
        assistant, mode = handle_turn(prompt, process, conversation, ai)
        repo.message(project_id, "user", prompt)
        repo.message(project_id, "assistant", assistant)
        repo.save_process(project_id, process, "discovery")
        st.session_state.process = process
        st.session_state.last_mode = mode
        st.rerun()


def render_library() -> None:
    st.title("SOP Library")
    st.caption(
        "Working drafts, submissions, validated SOPs, and their complete review history."
    )
    projects = repo.list_projects()
    if not projects:
        st.info("No SOPs have been created yet.")
        return
    filters = st.multiselect(
        "Status",
        ["discovery", "generated", "submitted", "changes_requested", "validated"],
        default=["generated", "submitted", "changes_requested", "validated"],
    )
    for project in projects:
        if filters and project["status"] not in filters:
            continue
        icon = {
            "validated": "✅",
            "submitted": "🕐",
            "changes_requested": "⚠️",
            "generated": "📝",
        }.get(project["status"], "💬")
        with st.expander(
            f"{icon} {project['title']} · {project['status'].replace('_', ' ').title()}"
        ):
            st.caption(f"Last updated: {project['updated_at']}")
            history = repo.review_history(project["id"])
            for item in history:
                st.markdown(
                    f"- **{item['status'].replace('_', ' ').title()}** by {item['reviewer'] or 'Unassigned'} — {item['comment'] or 'No comment'}"
                )
            for index, item in enumerate(repo.list_generated_files(project["id"])):
                path = Path(item["path"])
                if path.exists():
                    st.download_button(
                        f"Download {path.name}",
                        path.read_bytes(),
                        file_name=path.name,
                        key=f"library-{project['id']}-{index}",
                    )
            if st.button("Resume conversation", key=f"resume-{project['id']}"):
                load_project(project["id"])
                st.success("Loaded. Select Create SOP to continue.")


def render_review_queue() -> None:
    st.title("Internal Review Queue")
    st.caption("Human validation is separate from the automated quality score.")
    queue = repo.projects_by_status(("submitted",))
    if not queue:
        st.info("No SOPs are awaiting internal review.")
        return
    for project in queue:
        with st.expander(f"🕐 {project['title']}", expanded=True):
            files = repo.list_generated_files(project["id"])
            if files:
                path = Path(files[0]["path"])
                if path.exists():
                    st.download_button(
                        "Download submitted SOP",
                        path.read_bytes(),
                        file_name=path.name,
                        key=f"review-file-{project['id']}",
                    )
            reviewer = st.text_input(
                "Internal controller", key=f"reviewer-{project['id']}"
            )
            comment = st.text_area("Review comments", key=f"comment-{project['id']}")
            first, second = st.columns(2)
            with first:
                if st.button(
                    "Request changes",
                    key=f"changes-{project['id']}",
                    disabled=not reviewer.strip(),
                ):
                    repo.record_review(
                        project["id"], "changes_requested", reviewer, comment
                    )
                    st.rerun()
            with second:
                if st.button(
                    "Validate SOP",
                    type="primary",
                    key=f"validate-{project['id']}",
                    disabled=not reviewer.strip(),
                ):
                    repo.record_review(project["id"], "validated", reviewer, comment)
                    st.rerun()


if page == "SOP Library":
    render_library()
elif page == "Internal Review Queue":
    render_review_queue()
else:
    render_conversation()
