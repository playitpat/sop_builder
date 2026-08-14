from pathlib import Path

import streamlit as st

from src.agents import completeness, mermaid_from_process, readiness, review_loop
from src.conversation import handle_turn
from src.document import populate_template, validate_docx
from src.models import ProcessDefinition, Provenance, Value
from src.openai_service import OpenAIService
from src.process_flow import render_mermaid_png
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
        for key in ("reviews", "reviewed_draft", "submitted"):
            st.session_state.pop(key, None)


def status_summary(process: ProcessDefinition) -> None:
    score = readiness(process)["documentation_readiness_score"]
    state = completeness(process)
    with st.expander("Process documentation readiness", expanded=False):
        st.progress(
            score / 100, text=f"Compulsory process information: {score}% complete"
        )
        if state["blocking"]:
            st.warning("**Compulsory information still needed before internal review**")
            for item in state["blocking"]:
                st.markdown(f"- ❌ {item}")
        else:
            st.success(
                "All compulsory process information is complete. You can run the automated quality review."
            )
        if state["draft_warnings"]:
            st.info(
                "**Good-to-have additional information**\n\n"
                "These items improve the final controlled document, but they do not reduce the process-readiness score or block internal review."
            )
            for item in state["draft_warnings"]:
                st.markdown(f"- ℹ️ {item}")


def render_review_result(project_id: str, process: ProcessDefinition) -> None:
    if "reviews" not in st.session_state:
        return
    with st.chat_message("assistant"):
        if st.session_state.get("submitted"):
            st.success(
                "SOP generated and submitted for internal review. Track it in the Internal Review Queue."
            )
            return
        st.markdown("### Automated SOP quality review")
        for review in st.session_state.reviews:
            icon = "✅" if not review.blocking_issues and review.score >= 90 else "❌"
            st.markdown(
                f"{icon} **Automated review {review.cycle}: {review.score}/100**"
            )
            for issue in review.blocking_issues:
                st.markdown(f"- ❌ {issue}")
            for recommendation in review.recommendations:
                st.markdown(f"- ⚠️ {recommendation}")
        approved = (
            not st.session_state.reviews[-1].blocking_issues
            and st.session_state.reviews[-1].score >= 90
        )
        if approved:
            st.success(
                "Automated quality checks passed. The SOP is ready for human review."
            )
            if st.button("Generate and submit for internal review", type="primary"):
                output = populate_template(TEMPLATE, st.session_state.reviewed_draft)
                validation = validate_docx(output)
                if validation["valid"]:
                    repo.generated_file(project_id, output, validation)
                    repo.save_process(project_id, process, "generated")
                    repo.submit_for_review(project_id)
                    st.session_state.submitted = True
                    st.rerun()
                else:
                    st.error(
                        "Word validation failed: " + "; ".join(validation["errors"])
                    )
        else:
            st.warning(
                "No document was generated. Continue the conversation to resolve the blocking issue."
            )


def render_conversation() -> None:
    st.markdown(
        '<div class="hero"><h1>Danone SOP Builder</h1><p>Describe the process naturally. The agent will assess it once, then ask one targeted question at a time.</p></div>',
        unsafe_allow_html=True,
    )
    corrections = repo.projects_by_status(("changes_requested",))
    if corrections:
        with st.expander(
            f"⚠️ Corrections requested ({len(corrections)})", expanded=True
        ):
            st.caption(
                "Open an SOP to see the controller's comments in the conversation and provide corrections."
            )
            for item in corrections:
                if st.button(
                    f"Open {item['title']}", key=f"author-correction-{item['id']}"
                ):
                    load_project(item["id"])
                    st.rerun()
    if st.button("＋ Start a new SOP"):
        for key in ("project_id", "process", "reviews", "reviewed_draft", "submitted"):
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
        if state["ready_for_review"] and process.process_flow_reference.value in (
            None,
            "",
        ):
            with st.expander("Optional: review a proposed process flow", expanded=True):
                st.caption(
                    "Built only from confirmed steps and ignored unless you approve it."
                )
                proposed_flow = mermaid_from_process(process)
                st.image(
                    render_mermaid_png(proposed_flow),
                    caption="Proposed process chart",
                    use_container_width=True,
                )
                with st.expander("View Mermaid source"):
                    st.code(proposed_flow, language="mermaid")
                first, second = st.columns(2)
                with first:
                    if st.button("Approve proposed flow"):
                        process.process_flow_reference = Value(
                            proposed_flow, Provenance.USER
                        )
                        repo.save_process(project_id, process, "discovery")
                        st.session_state.process = process
                        st.rerun()
                with second:
                    if st.button("Keep process flow as TBD"):
                        process.process_flow_reference = Value("TBD", Provenance.USER)
                        repo.save_process(project_id, process, "discovery")
                        st.session_state.process = process
                        st.rerun()
        if state["ready_for_review"]:
            if st.button("Run automated quality review", type="primary"):
                draft, reviews = review_loop(process)
                repo.artifact(project_id, "draft", draft)
                for review in reviews:
                    repo.artifact(project_id, "review", review.__dict__)
                st.session_state.reviews = reviews
                st.session_state.reviewed_draft = draft
                st.rerun()
    prompt = st.chat_input("Describe the process or answer the latest question…")
    if prompt:
        st.session_state.pop("reviews", None)
        st.session_state.pop("reviewed_draft", None)
        st.session_state.pop("submitted", None)
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
    st.caption("Only SOPs validated by an internal controller are shown here.")
    projects = repo.projects_by_status(("validated",))
    if not projects:
        st.info("No SOPs have been validated yet.")
        return
    for project in projects:
        with st.expander(f"✅ {project['title']} · Validated"):
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
                    "Send corrections to author",
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
