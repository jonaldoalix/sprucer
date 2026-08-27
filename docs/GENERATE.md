# Generate contract

Sprucer calls an OpenAI-compatible `POST {SPRUCER_LLM_URL}/chat/completions`.

## System message (fixed intent)

- Write materials grounded **only** in provided career truth + job description
- Never invent employers, dates, degrees, or metrics
- Keyboard punctuation preferred (no em dashes / fancy unicode)
- Respect `neverClaim`
- Return Markdown with one `##` heading per requested artifact (e.g. `## Cover Letter`, `## Email`)
- Write only sendable draft text under those headings — no Emphasis / meta commentary in the body

The server still computes an `emphasisPlanHint` for the model (and stores it on the generation sidecar). It is **not** prepended into the saved draft body; the web preview treats any leftover Emphasis sections as collapsed grounding notes.

## User message

JSON object:

```json
{
  "application": { "id": "", "company": "", "title": "", "location": "", "url": "" },
  "artifactTypes": ["cover", "email"],
  "emphasisPlanHint": [{ "id": "", "reason": "", "text": "" }],
  "careerTruth": {},
  "jobDescription": "..."
}
```

## Artifact types

Built-in: `cover`, `resume`, `email`, `interview`, `linkedin`. Custom types are allowed as `custom:<slug>`.

### Interview prep

Intended use: a practice cheat-sheet for **this** JD.

- `### Likely questions` — realistic interview questions
- After each: `Answer with: … Cite: \`real-id\`` grounded in `interviewCiteCatalog` (derived from career truth metrics/projects/experience/stories)
- `### Refresh from your knowledge bank` — re-read list of **real** vault entries (no invented ticket IDs)
- `### Watch-outs` — neverClaim traps that matter for the role

Do not invent Epic/HIPAA/employer claims absent from the vault; bridge transferable experience honestly instead.

## Career-fit interview (not this artifact)

Discovering industries / titles is a separate flow: [FIT_INTERVIEW.md](FIT_INTERVIEW.md) (`/v1/fit/*`, UI `/fit`). Do not confuse it with the `interview` artifact type above.

## Persistence

Generations save with `approval=draft`. Approve requires `confirm=true`.
