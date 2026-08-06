# Generate contract

Sprucer calls an OpenAI-compatible `POST {SPRUCER_LLM_URL}/chat/completions`.

## System message (fixed intent)

- Write materials grounded **only** in provided career truth + job description
- Never invent employers, dates, degrees, or metrics
- Keyboard punctuation preferred (no em dashes / fancy unicode)
- Respect `neverClaim`
- Return Markdown with a clear heading per requested artifact type
- Cite which truth metric/experience ids informed emphasis

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

## Persistence

Generations save with `approval=draft`. Approve requires `confirm=true`.
