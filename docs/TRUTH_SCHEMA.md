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
| `roleSpectrum` | object | What work you want (not rigid titles) — short generation dial |
| `careerFit` | object | Accepted career-fit prefs from the interview (draft until accept) |
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

## `careerFit` (accepted interview result)

Written only via `POST /v1/fit/accept` with `confirm=true` (or equivalent `PATCH /v1/truth` `op=set` if you paste a previously accepted block). Draft recommendations stay on the fit session until accept.

| Field | Type | Notes |
|-------|------|-------|
| `industries` | list | `{name, rank, rationale}` — required when accepting |
| `titles` | list | `{name, rank, rationale, industry?}` role families |
| `constraints` | object | `geo`, `remote`, `other` |
| `confidence` | string | `low` \| `medium` \| `high` |
| `notes` | string | Freeform caveats |
| `acceptedAt` | ISO-8601 | Set on accept |
| `sourceSessionId` | string | Fit session id |

See [FIT_INTERVIEW.md](FIT_INTERVIEW.md). Do not store fabricated employers or job URLs here.
