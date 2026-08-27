# Career-fit interview

Sprucer can run an AI-guided **career-fit interview** that confirms existing prefs or inquires when the vault is thin, then drafts **ranked industries** (required) and **titles / role families** (preferred). Nothing is written to the knowledge bank until you explicitly accept.

This is separate from the Applications **Interview prep** artifact (JD practice cheat-sheet).

## Requirements

- Live OpenAI-compatible LLM via `SPRUCER_LLM_*`, or demo **BYOK** headers (`X-LLM-Base-Url` / `X-LLM-Api-Key` / `X-LLM-Model`).
- The offline `DemoLlm` generator cannot run fit turns or recommendations.

## API

| Method | Path | Notes |
|--------|------|-------|
| GET | `/v1/fit/sessions` | Recent sessions for the vault owner |
| POST | `/v1/fit/start` | Opens session; confirm vs inquire from vault |
| GET | `/v1/fit/sessions/{id}` | Full session (messages + draft) |
| POST | `/v1/fit/turn` | `{session_id, message}` — needs live LLM |
| POST | `/v1/fit/recommend` | `{session_id}` — draft industries + titles |
| POST | `/v1/fit/accept` | `{session_id, confirm: true}` — writes `truth.careerFit` |

BYOK headers are accepted on `/v1/fit/*` the same way as `/v1/generate`.

## Truth field

Accepted output lives under top-level `careerFit` (see [TRUTH_SCHEMA.md](TRUTH_SCHEMA.md)). `roleSpectrum` remains the short generation dial; accept may refresh `roleSpectrum.summary` from the accepted draft.

## Real job descriptions (stretch / follow-up)

This flow **never invents employers or postings**. To attach real JDs that match a profile, use existing SSRF-guarded **JD ingest** on Applications (paste, URL fetch when enabled, or upload). A future slice may deep-link from fit recommendations into ingest; do not scrape job boards without an explicit operator OK.

## UI

Web desk: `/fit` (Career fit in the nav). Knowledge shows accepted `careerFit` read-only.
