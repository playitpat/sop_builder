# Danone SOP Builder Future Version

A local MVP that preserves the prototype's conversational journey while adding durable projects, transparent governance analysis, local knowledge retrieval, an independent quality gate, and generation **inside the supplied TMP-10031 Word package**.

## What the reference files establish

### `Prompt SOP.docx`

The prompt requires a guarded first turn, concise SOP recommendation, natural-language discovery rather than a questionnaire, maturity assessment, relevant governance gaps, targeted follow-ups, explicit acceptance of TBD, professional global-English rewriting, and Word output as the ultimate result. The mandatory purpose opening and section sequence are enforced in code.

### `SOP Builder.pptx`

The seven-slide presentation frames the current creation problem, the solution and demo, its official-template output, and the limitations/future vision. Its story is preserved as: idea → assessment → extraction → gaps → clarification → draft → review/revision → official output. Some slide content is embedded as visual artwork rather than ordinary presentation text.

### `TMP-10031_SOP_TemplateCC.docx`

Package inspection found 39 OOXML parts, 17 structured document tags (content controls), three body tables, one bookmark, a branded header/footer, styles, relationships, drawings, and section properties. Content controls are tagged (`Purpose`, `InScope`, `RolesR`, `ProcessDetails`, and others); their displayed placeholder is `Click or tap here to enter text.` Header values are split across drawing text runs. The footer's template identity and feedback/confidentiality content are static publishing elements.

## Architecture

| Component | Responsibility | Later enterprise replacement |
|---|---|---|
| `src/models.py` | Validated process model and field provenance | Dataverse entities |
| `src/agents.py` | First-turn guard, extraction, readiness, governance, generator, reviewer, loop | Copilot Studio / OpenAI Responses API agents |
| `src/repository.py` | SQLite projects, messages, process snapshots, gaps/drafts/reviews, files | Dataverse |
| `src/knowledge.py` | Transparent local TF-IDF retrieval with source names | SharePoint / Microsoft Graph search |
| `src/document.py` | In-place OOXML population and independent validation | Graph/Word automation where appropriate |
| `app.py` | Streamlit conversational workspace and download | Teams/Copilot Studio front end |

All core behavior is deterministic and works without sending content externally. `OPENAI_API_KEY` is reserved for a future optional Responses API enhancement; the current tested MVP does not transmit files or prompts. The lightweight runtime model uses standard-library validation so the complete core and tests can run in restricted/offline environments; `pydantic` is listed for the production environment and is the intended schema boundary when connecting model-generated structured output.

## Word approach and rationale

The generator copies the original DOCX ZIP package and edits only `word/document.xml` content-control payloads, targeted revision cells, and target header text in `word/header1.xml`. It does **not** reconstruct the document. This retains styles, drawings, table definitions, relationships, footer, branding, page setup, and unsupported Word features. A `python-docx` round-trip was deliberately avoided because unsupported Office constructs can be changed or discarded; `docxtpl` was rejected because the source contains content controls, not Jinja tags.

Validation reopens the ZIP/XML and checks section presence/order, three tables, cleaned placeholders, header metadata, RACI, revision 1.0/New SOP, and retained styles/footer. Word owns final pagination; opening the file in desktop Word may refresh page fields.

## Quality review loop

The generator builds a normalized draft from the process definition and provenance snapshot. The logically separate reviewer checks mandatory section order, purpose wording, scope, explicit RACI/TBD, actionable ordered steps and actors, trigger/output, approvals/records, non-invention of flow, vague wording, revision history, and appendices. Blocking failures return suggested revisions. The controller stops when blocking checks pass and score is at least 90, or after three cycles; all draft and review records are persisted. The offline deterministic reviewer is the tested baseline; model-based semantic review is the primary next enhancement once a configured enterprise model endpoint is available.

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

Run the synthetic demonstration and tests:

```bash
python scripts/run_demo.py
pytest -q
```

The demo output is `generated/SOP – Power BI Sales Dashboard Product Creation Process – v1.0.docx`. Runtime databases and generated SOPs are gitignored.

## Data handling and security

- Secrets are environment variables; `.env` is ignored.
- Conversation/process data and artifact metadata remain in local SQLite.
- Knowledge documents remain local and retrieval returns named sources and short excerpts.
- Do not place confidential production material in a development checkout. Define retention/access controls before enterprise use.
- Uploaded image, process-map, and visual-PDF understanding is an experimental future capability and is currently disabled rather than silently sending artifacts externally.

## Known limitations and recommended Microsoft 365 path

- Deterministic extraction handles the demo and straightforward English, but complex prose benefits from schema-constrained Responses API extraction.
- Model-based semantic review is not enabled without an approved endpoint; deterministic independent checks are functional.
- Local retrieval indexes Markdown/text only. Implement the same service interface using Graph Search over permission-trimmed SharePoint content, with citations and document version metadata.
- Final pagination and visual fidelity should be certified in desktop Word. A conversion/rendering tool was unavailable in the build environment, so validation is structural rather than pixel-based.
- Next, expose the domain services behind authenticated APIs, map projects to Dataverse, use Copilot Studio for conversation, SharePoint/Graph for knowledge and controlled documents, and Power Automate for approval/publication. Preserve this service separation so no workflow rewrite is required.
