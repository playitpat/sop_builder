from pathlib import Path

import streamlit as st

from src.agents import apply_demo_clarification, extract_process, first_response, governance_gaps, is_topic_only, readiness, review_loop
from src.document import populate_template, validate_docx
from src.knowledge import LocalKnowledgeService
from src.repository import ProjectRepository

st.set_page_config(page_title="Danone SOP Builder Future Version",layout="wide")
st.markdown("""<style>:root{--navy:#102a43;--blue:#1261a0;--purple:#7253a6}.stApp{background:#f7f9fc}.hero{padding:1rem 1.3rem;border-left:6px solid var(--purple);background:white;border-radius:8px}.tag{color:#1261a0;font-weight:700}</style>""",unsafe_allow_html=True)
repo=ProjectRepository(); kb=LocalKnowledgeService()
st.sidebar.title("SOP Builder")
page=st.sidebar.radio("Workspace",["New SOP","Existing projects","Knowledge Base","Settings"])

if page=="Knowledge Base":
    st.title("Enterprise SOP Knowledge Base")
    st.caption("Local, transparent retrieval. Synthetic examples only; source content is not sent externally.")
    for path,_ in kb.documents(): st.write("•",path.name)
elif page=="Settings":
    st.title("Settings"); st.info("Deterministic offline mode is active. Set OPENAI_API_KEY to enable an optional future model adapter. Experimental visual artifact analysis is not enabled in this MVP.")
elif page=="Existing projects":
    st.title("Resume an SOP project")
    for p in repo.list_projects():
        if st.button(f"{p['title']} · {p['status']}",key=p["id"]): st.session_state.project_id=p["id"]
else:
    st.markdown('<div class="hero"><h1>Danone SOP Builder <span class="tag">Future Version</span></h1><p>Discover → govern → draft → independently review → publish in TMP-10031</p></div>',unsafe_allow_html=True)
    title=st.text_input("Process topic or SOP title")
    description=st.text_area("Describe the process from start to finish",height=150)
    if st.button("Assess process",type="primary",disabled=not title):
        pid=repo.create(title); st.session_state.project_id=pid; repo.message(pid,"user",title if not description else title+"\n"+description)
        if not description or is_topic_only(description):
            response=first_response(title); repo.message(pid,"assistant",response); st.info(response)
        else:
            p=extract_process(title,description); repo.save_process(pid,p); st.session_state.process=p
    pid=st.session_state.get("project_id")
    if pid and "process" not in st.session_state:
        loaded=repo.load(pid)
        if loaded: st.session_state.process=loaded["process"]
    if "process" in st.session_state:
        p=st.session_state.process
        left,right=st.columns(2)
        with left:
            st.subheader("Structured Process Information")
            st.json(p.to_dict(),expanded=False)
            st.subheader("Process Maturity Assessment"); st.json(readiness(p))
        with right:
            gaps=governance_gaps(p); st.subheader("Governance Gaps")
            for g in gaps: st.warning(f"**{g.label}** — {g.reason}\n\n{g.question}")
            clarification=st.text_area("Targeted clarification (or explicitly state TBD)")
            if st.button("Save clarification"):
                apply_demo_clarification(p,clarification); repo.message(pid,"user",clarification); repo.save_process(pid,p); st.rerun()
            sources=kb.retrieve(p.sop_title.value+" "+" ".join(x.action for x in p.process_steps)); st.subheader("Knowledge Used")
            for source in sources: st.caption(f"{source['source']} · relevance {source['score']}")
        if st.button("Generate, review, and validate official SOP",type="primary"):
            draft,reviews=review_loop(p); repo.artifact(pid,"draft",draft)
            for r in reviews: repo.artifact(pid,"review",r.__dict__)
            out=populate_template("TMP-10031_SOP_TemplateCC.docx",draft); validation=validate_docx(out); repo.generated_file(pid,out,validation); repo.save_process(pid,p,"generated")
            st.session_state.output=str(out); st.session_state.reviews=reviews; st.session_state.validation=validation
        if "reviews" in st.session_state:
            st.subheader("Agent Review Loop")
            for r in st.session_state.reviews: st.write(f"Draft {r.cycle} → Review {r.cycle}: **{r.score}**" + (" → Approved" if not r.blocking_issues and r.score>=90 else " → Revision"))
            st.subheader("Final Document Status"); st.json(st.session_state.validation)
            if st.session_state.validation["valid"]:
                with open(st.session_state.output,"rb") as fh: st.download_button("Download Final SOP",fh,file_name=Path(st.session_state.output).name)
