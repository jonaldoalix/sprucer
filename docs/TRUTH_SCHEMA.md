# Career truth schema

Versioned JSON document stored by the storage adapter. Fixtures ship a synthetic example under `fixtures/synthetic/career-truth.json`.

## Top-level fields

| Field | Type | Notes |
|-------|------|-------|
| `version` | int | Bumped on writes |
| `updatedAt` | ISO-8601 | UTC |
| `profile` | object | name, contact, links |
| `headline` | string | Short accurate headline |
| `voice` | object | person, tone, punctuation prefs |
| `roleSpectrum` | object | What work you want (not rigid titles) |
| `education` | object | Degree facts you will defend |
| `experience` | list | org, role, dates, points |
| `projects` | list | Optional project entries |
| `skills` | object | Grouped string lists |
| `metrics` | list | `{id, text, tags?}` — countable facts |
| `neverClaim` | list[string] | Forbidden claims in generations |
| `signatureStories` | list | Longer narratives with optional tags |
| `blurbs` | list | Reusable one-liners / paragraphs |
| `resumePaths` | object | Optional paths to source resumes |

## Knowledge bank ops

API `PATCH /v1/truth` supports:

| op | Purpose |
|----|---------|
| `add` | Append item to a list section |
| `update` | Merge fields by `item_id` or `index` |
| `remove` | Delete one item (`confirm=true`) |
| `set` | Replace a whole section |

List sections: `signatureStories`, `blurbs`, `metrics`, `experience`, `projects`, `neverClaim`.
