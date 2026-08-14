# Repository guidance

- Keep the official TMP-10031 file immutable; generated documents belong in `generated/`.
- Preserve the first-message guard and never infer missing governance ownership.
- New document fields require deterministic validation and an end-to-end test.
- Do not commit secrets, local databases, generated confidential documents, or `.env`.
