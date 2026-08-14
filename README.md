# Danone SOP Builder Future Version

A local MVP that preserves the prototype's conversational journey while adding durable projects, transparent governance analysis, local knowledge retrieval, an independent quality gate, and generation **inside the supplied TMP-10031 Word package**.

## What the reference files establish

### `reference_documents/prompt/Prompt SOP.docx`

The prompt requires a guarded first turn, concise SOP recommendation, natural-language discovery rather than a questionnaire, maturity assessment, relevant governance gaps, targeted follow-ups, explicit acceptance of TBD, professional global-English rewriting, and Word output as the ultimate result. The mandatory purpose opening and section sequence are enforced in code.

### `reference_documents/presentation/SOP Builder.pptx`

The seven-slide presentation frames the current creation problem, the solution and demo, its official-template output, and the limitations/future vision. Its story is preserved as: idea → assessment → extraction → gaps → clarification → draft → review/revision → official output. Some slide content is embedded as visual artwork rather than ordinary presentation text.

### `reference_documents/templates/TMP-10031_SOP_TemplateCC.docx`

Package inspection found 39 OOXML parts, 17 structured document tags (content controls), three body tables, one bookmark, a branded header/footer, styles, relationships, drawings, and section properties. Content controls are tagged (`Purpose`, `InScope`, `RolesR`, `ProcessDetails`, and others); their displayed placeholder is `Click or tap here to enter text.` Header values are split across drawing text runs. The footer's template identity and feedback/confidentiality content are static publishing elements.

## Architecture

| Component | Responsibility | Later enterprise replacement |
|---|---|---|
| `src/models.py` | Validated process model and field provenance | Dataverse entities |
| `src/conversation.py` / `src/openai_service.py` | Incremental chat orchestration, conservative fallback, Responses API adapter | Copilot Studio agents |
| `src/agents.py` | Readiness, governance, generator, deterministic reviewer, loop | Copilot Studio / OpenAI review agents |
| `src/repository.py` | SQLite projects, messages, process snapshots, gaps/drafts/reviews, files | Dataverse |
| `src/knowledge.py` | Transparent local TF-IDF retrieval with source names | SharePoint / Microsoft Graph search |
| `src/document.py` | In-place OOXML population and independent validation | Graph/Word automation where appropriate |
| `app.py` | Streamlit conversational workspace and download | Teams/Copilot Studio front end |

The single chat bar saves each turn, merges newly extracted facts without erasing previous answers, presents one initial maturity/governance assessment in the conversation, and then asks one relevant follow-up at a time. Raw JSON is not shown in the main author experience. When `OPENAI_API_KEY` is configured, conversation text and the structured process state are sent to the OpenAI Responses API for incremental extraction and targeted questioning. Without a key—or if an API call fails—the conservative local fallback remains usable. Raw knowledge files are never uploaded by this adapter.

The primary navigation is intentionally task-based: **Create SOP**, **SOP Library**, and **Internal Review Queue**. The library separates working drafts, submitted SOPs, change requests, and validated SOPs. Automated quality approval remains distinct from human internal-controller validation; controller decisions and comments are retained in SQLite.

## Word approach and rationale

The generator copies the original DOCX ZIP package and edits only `word/document.xml` content-control payloads, targeted revision cells, and target header text in `word/header1.xml`. It does **not** reconstruct the document. This retains styles, drawings, table definitions, relationships, footer, branding, page setup, and unsupported Word features. A `python-docx` round-trip was deliberately avoided because unsupported Office constructs can be changed or discarded; `docxtpl` was rejected because the source contains content controls, not Jinja tags.

Validation reopens the ZIP/XML and checks section presence/order, three tables, cleaned placeholders, header metadata, RACI, revision 1.0/New SOP, and retained styles/footer. Word owns final pagination; opening the file in desktop Word may refresh page fields.

## Quality review loop

The generator consolidates repeated conversational steps and builds a normalized draft from the process definition and provenance snapshot. The logically separate reviewer checks mandatory section order, purpose wording, explicit scope, RACI, actionable ordered steps and actors, trigger/output, approvals, validation, records, escalation, non-invention of flow, vague wording, revision history, and appendices. `TBD` no longer passes mandatory completeness checks. Working drafts may still be downloaded with disclosed warnings, but internal-review submission is blocked until mandatory information and the SOP author are captured. The controller stops when blocking checks pass and score is at least 90, or after three cycles; all draft and review records are persisted.

## Readiness score

The score is a whole-number weighted sum, not arbitrary precision: accountable owner 20, responsible role 15, trigger 15, output 15, approval 15, records 10, and ordered steps 10. Missing items receive zero for their weight.

## Run

Python 3.12 is the target (the test container currently uses a newer compatible interpreter).

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

To enable AI conversation, copy `.env.example` to the gitignored `.env` and add your key, or set it in the launch environment (never commit it):

```bash
export OPENAI_API_KEY="your-key"
export OPENAI_MODEL="gpt-5-mini"
streamlit run app.py
```

Run the synthetic demonstration and tests:

```bash
python scripts/run_demo.py
pytest -q
```

The demo output is `generated/SOP – Power BI Sales Dashboard Product Creation Process – v1.0.docx`. Runtime databases and generated SOPs are gitignored.

## Data handling and security

- Secrets are environment variables; `.env` is ignored.
- Conversation/process data and artifact metadata remain in local SQLite.
- Knowledge documents and retrieval remain local backend capabilities rather than primary author navigation. The service indexes TXT, Markdown, and DOCX; PDF extraction uses the declared `pypdf` dependency. A future administrator-only surface can manage these sources.
- Do not place confidential production material in a development checkout. Define retention/access controls before enterprise use.
- Uploaded image, process-map, and visual-PDF understanding is an experimental future capability and is currently disabled rather than silently sending artifacts externally.

## Known limitations and recommended Microsoft 365 path

- AI extraction requires a valid OpenAI API key and network access; local fallback handles straightforward English but is intentionally conservative.
- Model-based semantic review remains a subsequent enhancement; deterministic independent publishing checks are functional.
- Local retrieval indexes TXT, Markdown, and DOCX text. Implement the same service interface using Graph Search over permission-trimmed SharePoint content, with citations and document version metadata.
- Final pagination and visual fidelity should be certified in desktop Word. A conversion/rendering tool was unavailable in the build environment, so validation is structural rather than pixel-based.
- Next, expose the domain services behind authenticated APIs, map projects to Dataverse, use Copilot Studio for conversation, SharePoint/Graph for knowledge and controlled documents, and Power Automate for approval/publication. Preserve this service separation so no workflow rewrite is required.
