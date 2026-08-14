from pathlib import Path

import streamlit as st

from src.agents import governance_gaps, readiness, review_loop
from src.conversation import handle_turn
from src.document import populate_template, validate_docx
from src.knowledge import LocalKnowledgeService
from src.models import ProcessDefinition
from src.openai_service import OpenAIService
from src.repository import ProjectRepository

TEMPLATE = Path("reference_documents/templates/TMP-10031_SOP_TemplateCC.docx")

st.set_page_config(page_title="Danone SOP Builder Future Version", layout="wide")
st.markdown(
    """<style>
:root{--navy:#102a43;--blue:#1261a0;--purple:#7253a6}.stApp{background:#f7f9fc}
.hero{padding:1rem 1.3rem;border-left:6px solid var(--purple);background:white;border-radius:8px}
.status{padding:.55rem .8rem;background:#edf5ff;border-radius:8px;color:#102a43}
</style>""",
    unsafe_allow_html=True,
)

repo = ProjectRepository()
kb = LocalKnowledgeService()
ai = OpenAIService()
st.sidebar.title("SOP Builder")
page = st.sidebar.radio(
    "Workspace", ["Conversation", "Existing projects", "Knowledge Base", "Settings"]
)


def select_project(project_id: str) -> None:
    loaded = repo.load(project_id)
    if loaded:
        st.session_state.project_id = project_id
        st.session_state.process = loaded["process"]


def render_conversation() -> None:
    st.markdown(
        '<div class="hero"><h1>Danone SOP Builder <span style="color:#7253a6">Future Version</span></h1>'
        "<p>Describe your process naturally. I will remember it and ask only the next relevant questions.</p></div>",
        unsafe_allow_html=True,
    )
    if st.button("＋ Start a new SOP conversation"):
        for key in ("project_id", "process", "reviews", "validation", "output"):
            st.session_state.pop(key, None)
        st.rerun()
    project_id = st.session_state.get("project_id")
    process = st.session_state.get("process", ProcessDefinition())
    history = repo.messages(project_id) if project_id else []
    if not history:
        with st.chat_message("assistant"):
            st.write("What process would you like to document?")
    for message in history:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    prompt = st.chat_input("Describe the process or answer the latest question…")
    if prompt:
        if not project_id:
            provisional = prompt[:80].strip() or "Untitled SOP"
            project_id = repo.create(provisional)
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
    if project_id:
        st.caption(
            f"Conversation mode: **{'OpenAI' if ai.enabled else 'local fallback'}** · Project saved automatically"
        )
        with st.expander(
            "Process information, maturity, and governance", expanded=True
        ):
            left, right = st.columns(2)
            with left:
                st.subheader("Structured Process Information")
                st.json(process.to_dict(), expanded=False)
                st.subheader("Maturity")
                st.json(readiness(process))
            with right:
                st.subheader("Outstanding Governance Gaps")
                gaps = governance_gaps(process)
                if gaps:
                    for gap in gaps:
                        st.warning(f"**{gap.label}** — {gap.reason}")
                else:
                    st.success("No deterministic governance gaps remain.")
                sources = kb.retrieve(
                    str(process.sop_title.value)
                    + " "
                    + " ".join(step.action for step in process.process_steps)
                )
                st.subheader("Knowledge Used")
                for source in sources:
                    st.write(f"• {source['source']} · relevance {source['score']}")
        if process.process_steps and st.button(
            "Generate, independently review, and validate SOP", type="primary"
        ):
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
        if "reviews" in st.session_state:
            st.subheader("Agent Review Loop")
            for review in st.session_state.reviews:
                state = (
                    "Approved"
                    if not review.blocking_issues and review.score >= 90
                    else "Revision"
                )
                st.write(
                    f"Draft {review.cycle} → Review {review.cycle}: **{review.score}** → {state}"
                )
            st.json(st.session_state.validation)
            if st.session_state.validation["valid"]:
                with open(st.session_state.output, "rb") as document:
                    st.download_button(
                        "Download Final SOP",
                        document,
                        file_name=Path(st.session_state.output).name,
                    )
        previous_files = repo.files(project_id)
        if previous_files:
            with st.expander("Previously generated documents"):
                for index, item in enumerate(previous_files):
                    path = Path(item["path"])
                    if path.exists():
                        st.download_button(
                            f"Download {path.name}",
                            path.read_bytes(),
                            file_name=path.name,
                            key=f"previous-{project_id}-{index}",
                        )


if page == "Knowledge Base":
    st.title("Enterprise SOP Knowledge Base")
    st.caption(
        "Upload, inspect, download, and remove local reference sources. Files remain on this machine."
    )
    upload = st.file_uploader(
        "Add a reference document", type=["txt", "md", "docx", "pdf"]
    )
    if upload and st.button("Add to knowledge base"):
        kb.add(upload.name, upload.getvalue())
        st.rerun()
    for source in kb.sources():
        with st.expander(f"{source['name']} · {source['status']}"):
            st.caption(f"{source['type']} · {source['size']} bytes")
            st.text_area(
                "Extracted-text preview",
                source["preview"] or "No text preview available.",
                disabled=True,
                key=f"preview-{source['path']}",
            )
            first, second = st.columns(2)
            with first:
                st.download_button(
                    "Download source",
                    source["path"].read_bytes(),
                    file_name=source["name"],
                    key=f"download-{source['path']}",
                )
            with second:
                if st.button("Remove source", key=f"delete-{source['path']}"):
                    kb.delete(source["path"])
                    st.rerun()
elif page == "Existing projects":
    st.title("Resume an SOP conversation")
    projects = repo.list_projects()
    if not projects:
        st.info("No saved projects yet. Start in Conversation.")
    for project in projects:
        if st.button(
            f"{project['title']} · {project['status']} · {project['updated_at']}",
            key=project["id"],
        ):
            select_project(project["id"])
            st.session_state.page_hint = "Conversation"
            st.success(
                "Project loaded. Select Conversation to continue where you stopped."
            )
elif page == "Settings":
    st.title("Settings")
    st.metric("Conversation mode", "OpenAI" if ai.enabled else "Local fallback")
    st.write(
        "Set `OPENAI_API_KEY` in the environment to enable AI extraction and targeted follow-up questions."
    )
    st.write(f"Configured model: `{ai.model}`")
    st.info(
        "Knowledge documents are local. In AI mode, only conversation text and structured process state are sent to OpenAI; source files are not uploaded."
    )
else:
    render_conversation()
