import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents import apply_demo_clarification, extract_process, governance_gaps, readiness, review_loop
from src.document import populate_template, validate_docx
from src.knowledge import LocalKnowledgeService
from src.repository import ProjectRepository

TITLE="Power BI Sales Dashboard Product Creation Process"
DESCRIPTION="""Marketing launches a new product and sends a request to the BI team.
The BI Analyst verifies whether the product exists in master data.
If it is missing, the BI Analyst works with Data Engineering to make the product available in the reporting model.
The BI Analyst updates the product hierarchy in Power BI.
The BI Analyst refreshes the dashboard and informs the stakeholder."""
CLARIFICATION="""Analytics Manager is accountable. Business requester validates the dashboard update.
Analytics Manager approves release. Request ticket and validation email are stored in SharePoint."""


def run(base=Path(".")):
    repo=ProjectRepository(base/"data"/"demo.db"); pid=repo.create(TITLE)
    p=extract_process(TITLE,DESCRIPTION); initial=[g.label for g in governance_gaps(p)]
    apply_demo_clarification(p,CLARIFICATION); repo.save_process(pid,p,"ready")
    knowledge=LocalKnowledgeService(base/"knowledge_base").retrieve(TITLE+" "+DESCRIPTION)
    draft,reviews=review_loop(p); out=populate_template(base/"TMP-10031_SOP_TemplateCC.docx",draft,base/"generated")
    validation=validate_docx(out)
    for kind,payload in (("gaps",initial),("maturity",readiness(p)),("knowledge",knowledge),("draft",draft),("reviews",[r.__dict__ for r in reviews])): repo.artifact(pid,kind,payload)
    repo.generated_file(pid,out,validation)
    return {"project_id":pid,"initial_gaps":initial,"review_scores":[r.score for r in reviews],"file":str(out),"validation":validation}


if __name__=="__main__": print(run())
