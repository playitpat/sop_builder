# Danone SOP Builder — Future Version

> A conversational process-excellence MVP that turns operational knowledge into governed, review-ready SOPs while preserving Danone's official TMP-10031 Word template.

## Executive summary

Creating an SOP is rarely just a writing task. Process knowledge is distributed across subject-matter experts, governance decisions are often implicit, and authors may not know the structure or language expected in a controlled document. A generic chatbot can produce polished prose, but it can also lose conversational state, invent missing controls, overlook approval gaps, or create a Word document that does not match the official template.

This project explores a safer product pattern. **Danone SOP Builder** conducts a short, stateful process-discovery conversation; converts the answers into a provenance-aware process model; identifies ownership, approval, validation, evidence, and escalation gaps; applies an independent automated quality gate; and populates the supplied TMP-10031 DOCX package in place. Completed documents enter a human internal-review workflow before appearing in the validated SOP Library.

The result is a working local MVP—not a production compliance system—that demonstrates how generative AI, deterministic controls, document engineering, and human governance can work together.

## Business value

The product is designed around four potential business outcomes:

1. **Reduce authoring effort** — employees describe a process in natural language instead of completing a long template questionnaire or manually formatting Word tables.
2. **Improve process quality before documentation** — the assistant identifies missing ownership, scope, approval, validation, records, and escalation decisions while the process owner can still resolve them.
3. **Increase document consistency** — professional global-English rewriting, explicit readiness rules, and deterministic section checks reduce variation between authors.
4. **Strengthen governance and auditability** — source provenance, persistent conversations, automated review results, generated versions, controller comments, and validation decisions are stored as separate records.

These are product hypotheses for an MVP. A production pilot should measure time to first review-ready draft, number of controller change requests, percentage of mandatory fields complete at first submission, and author/controller satisfaction.

## What this project demonstrates

For product, engineering, data, and transformation teams, the repository demonstrates:

- Translating an existing Copilot prototype and business presentation into a testable application.
- Designing a low-effort, one-question-at-a-time conversational workflow rather than an AI-themed form.
- Combining OpenAI-assisted extraction with deterministic fallbacks and publishing gates.
- Persisting complex conversational state in SQLite so an SOP can be resumed after restart.
- Separating AI quality review from accountable human validation.
- Implementing a corrections loop between internal controllers and SOP authors.
- Retrieving local governance guidance without blindly copying existing documents.
- Manipulating OOXML content controls, relationships, media, headers, tables, and revision metadata while preserving an official template.
- Rendering a user-approved Mermaid-derived process chart in the UI and embedding it as a PNG in Word.
- Testing domain validation, workflow persistence, document integrity, template immutability, and an end-to-end business fixture.

## User journey

```text
Process idea
  → SOP recommendation
  → Natural-language process description
  → Initial maturity and governance assessment
  → One targeted follow-up at a time
  → Completeness gate
  → Optional user-approved process chart
  → Automated quality review
  → DOCX generation and internal-review submission
  → Validate or return corrections
  → Validated SOP Library
```

### Author experience

The author starts with a topic such as “Create an SOP for customer complaint resolution.” The first-message guard does not generate a document from the title alone. Once a meaningful description is supplied, the assistant extracts available facts, shows a concise assessment, and asks only the next relevant question. A readiness score cannot reach 100 while mandatory questions remain.

No Word file is offered while discovery is incomplete or automated quality review is failing. After automated checks pass, one action generates the document and submits it for human review.

### Internal-controller experience

Submitted SOPs appear in the **Internal Review Queue**. A controller can download the submission, identify themselves, record comments, validate the SOP, or send corrections to the author. Correction comments are inserted into the author's persisted conversation for response and resubmission. Only human-validated SOPs appear in the **SOP Library**.

## Key capabilities

### Conversational process discovery

- Guarded first message and concise SOP recommendation
- Incremental extraction without overwriting confirmed user information
- Field-level provenance: user provided, uploaded-document extraction, inferred, or missing/TBD
- One targeted question per response
- Human-readable maturity and governance summaries rather than raw JSON
- OpenAI Responses API mode with a conservative local fallback

### Governance and quality controls

- Explicit 0–100 readiness calculation across all mandatory discovery fields
- Governance checks for scope, Responsible, Accountable, approval, validation, records, output, escalation, and executable steps
- Independent deterministic draft review
- Safe automatic writing corrections without inventing business controls
- Clear separation between automated quality checks and human validation

### Controlled Word generation

- Uses `reference_documents/templates/TMP-10031_SOP_TemplateCC.docx` as the document foundation
- Replaces tagged content controls and targeted metadata instead of recreating the document
- Preserves template styles, branding, tables, header/footer, relationships, and section properties
- Produces real Word line breaks and separated content rather than dense newline text
- Removes authoring placeholders and validates the final DOCX package
- Adds version `1.0`, `New SOP`, and controlled TBD values where publication data is unavailable

### Process visualization

The application derives Mermaid source only from confirmed ordered steps. The author previews a rendered flowchart and must explicitly approve it; otherwise Process Flow remains TBD. Approved flowcharts are rendered locally to PNG and embedded in the existing Word Process Flow content control. The current renderer supports a linear Mermaid subset; decision diamonds and complex branching are a future enhancement.

### Persistence and SOP lifecycle

- SQLite-backed projects, messages, structured process state, artifacts, reviews, and files
- Resume after application restart
- Submitted, changes-requested, and validated workflow states
- Controller identity, comments, and decision history
- Validated-only SOP Library

## Reference documents and product constraints

The implementation treats three supplied files as its source of truth:

| Reference | Role |
|---|---|
| `reference_documents/prompt/Prompt SOP.docx` | Defines the guarded conversation, maturity review, governance checks, writing rules, and required output behavior |
| `reference_documents/presentation/SOP Builder.pptx` | Defines the business problem, existing experience, demo journey, limitations, and future vision |
| `reference_documents/templates/TMP-10031_SOP_TemplateCC.docx` | Defines the official section structure, content controls, tables, styles, header/footer, branding, and document layout |

Template inspection found 39 OOXML parts, 17 structured document tags, three body tables, one bookmark, and separate branded header/footer parts. The official template remains immutable; generated files are written only to `generated/`.

## Architecture

| Component | Responsibility | Enterprise evolution |
|---|---|---|
| `app.py` | Streamlit author, library, and controller experiences | Teams or Copilot Studio front end |
| `src/models.py` | Process model, ordered steps, provenance, review structures | Dataverse entities |
| `src/conversation.py` | Turn orchestration, state merging, fallback extraction, question sequencing | Copilot orchestration |
| `src/openai_service.py` | Schema-constrained Responses API adapter | Approved enterprise model gateway |
| `src/agents.py` | Readiness, governance, generation, consolidation, and review | Agent services / Power Automate |
| `src/repository.py` | SQLite projects, messages, versions, and review workflow | Dataverse |
| `src/knowledge.py` | Transparent local TF-IDF retrieval | Permission-trimmed SharePoint / Graph search |
| `src/process_flow.py` | Local visual process-chart rendering | Visio, Mermaid service, or approved diagram tooling |
| `src/document.py` | In-place OOXML population and structural validation | Microsoft Graph / controlled Word automation |

The service boundaries are intentionally small so local MVP components can later be replaced without redesigning the full workflow.

## Readiness method

The score is a whole-number weighted sum and reaches 100 only when no mandatory discovery question remains:

| Item | Weight |
|---|---:|
| Purpose | 5 |
| In-scope | 5 |
| Out-of-scope | 5 |
| Accountable owner | 10 |
| Responsible role | 10 |
| Trigger | 10 |
| Output | 10 |
| Approval | 10 |
| Validation criteria | 8 |
| Required records and storage | 7 |
| Escalation | 5 |
| Ordered steps | 10 |
| SOP author | 5 |

## Run locally

Python 3.12 is the target runtime.

```bash
python -m venv .venv
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

### Enable OpenAI-assisted conversation

The core demo also has a conservative local mode. For richer natural-language extraction, copy the example configuration and add a key to the gitignored `.env` file:

```bash
cp .env.example .env
```

```dotenv
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-5-mini
SOP_BUILDER_EXPERIMENTAL_MULTIMODAL=false
```

Never put a secret in `.env.example`, source code, screenshots, or Git history.

## Demo and tests

Run the synthetic Power BI fixture:

```bash
python scripts/run_demo.py
```

Expected output:

```text
generated/SOP – Power BI Sales Dashboard Product Creation Process – v1.0.docx
```

Run the automated suite:

```bash
pytest -q
```

The suite covers model validation, persistence and restoration, first-message behavior, governance rules, readiness scoring, review behavior, knowledge retrieval, template population, placeholder removal, Word integrity, line breaks, revision history, process-chart embedding, internal-review decisions, correction feedback, and the end-to-end fixture.

## Data handling and security

- Secrets are environment variables; `.env` is gitignored.
- Conversation and process state remain in local SQLite for the MVP.
- Knowledge documents remain local; raw source files are not uploaded by the current OpenAI adapter.
- Only conversation text and structured process state are sent when OpenAI mode is configured.
- Generated documents and local databases are gitignored.
- Production use requires authentication, authorization, encryption, retention rules, permission-trimmed retrieval, approved model endpoints, and formal validation with process, Quality, Privacy, Security, and Legal stakeholders.

## Current limitations

- The deterministic fallback is intentionally conservative; complex prose benefits from OpenAI-assisted extraction.
- The automated reviewer is primarily deterministic. A separately configured semantic reviewer is a future enhancement.
- The process-chart renderer currently supports a linear sequence rather than complex decision diamonds and parallel branches.
- PDF visual understanding and image/process-map analysis remain experimental.
- Word owns final pagination and field refresh; production certification should include desktop Word rendering and controlled-document testing.
- SQLite and local files are suitable for an MVP, not multi-user enterprise deployment.

## Recommended Microsoft 365 path

1. Move projects, process definitions, provenance, versions, and review decisions to Dataverse.
2. Use Copilot Studio or Teams for the conversational author experience.
3. Replace local retrieval with permission-trimmed SharePoint and Microsoft Graph search.
4. Use Entra ID groups for author, controller, approver, and administrator permissions.
5. Use Power Automate for controller validation, accountable-owner approval, publication, notifications, and supersession.
6. Use Microsoft Graph or an approved Word automation service for controlled storage and publication.
7. Add operational analytics for cycle time, first-pass completeness, correction volume, and adoption.

## Why this is an MVP rather than a production compliance system

The repository intentionally proves the end-to-end product concept with lightweight local components. It does not claim regulatory approval, replace accountable process owners, or make autonomous publication decisions. The design keeps AI assistance bounded by deterministic checks, explicit provenance, human validation, and the official document foundation—providing a credible path from prototype to governed enterprise implementation.
