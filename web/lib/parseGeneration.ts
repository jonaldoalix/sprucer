/** Parse Sprucer generation markdown into preview-friendly sections. */

export type GenerationSection = {
  key: string;
  title: string;
  body: string;
  kind: "artifact" | "meta" | "other";
};

export type ParsedGeneration = {
  title: string;
  subtitle: string;
  artifacts: GenerationSection[];
  grounding: GenerationSection[];
};

const ARTIFACT_TITLES: Record<string, string> = {
  cover: "Cover Letter",
  "cover letter": "Cover Letter",
  email: "Email",
  resume: "Resume",
  interview: "Interview Prep",
  "interview prep": "Interview Prep",
  linkedin: "LinkedIn DM",
  "linkedin dm": "LinkedIn DM",
  "linkedin message": "LinkedIn DM",
  outreach: "LinkedIn DM",
  "outreach dm": "LinkedIn DM",
};

function normalizeHeading(raw: string): string {
  return raw.replace(/[#*`]/g, "").trim();
}

function headingKey(title: string): string {
  return title.toLowerCase().replace(/\s+/g, " ").trim();
}

/** Collapse hyphens/underscores/spaces so custom slugs match humanized ## titles. */
export function artifactMatchKey(title: string): string {
  return title
    .toLowerCase()
    .replace(/^custom:/, "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** `thank-you-note-after-interview` → `Thank You Note After Interview` */
export function humanizeArtifactLabel(raw: string): string {
  const bare = raw.replace(/^custom:/i, "").trim();
  const keyed = headingKey(bare.replace(/[_-]+/g, " "));
  if (ARTIFACT_TITLES[keyed]) return ARTIFACT_TITLES[keyed];
  for (const [k, label] of Object.entries(ARTIFACT_TITLES)) {
    if (keyed === k || keyed.startsWith(`${k} `)) return label;
  }
  return bare
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b[a-z]/gi, (ch) => ch.toUpperCase());
}

function classifyHeading(title: string): GenerationSection["kind"] {
  const key = headingKey(title);
  if (key.startsWith("generation ")) return "meta";
  if (key.startsWith("application")) return "meta";
  if (key === "emphasis" || key.startsWith("emphasis plan") || key.includes("pre-model")) {
    return "meta";
  }
  if (ARTIFACT_TITLES[key] || Object.keys(ARTIFACT_TITLES).some((k) => key === k || key.startsWith(k))) {
    return "artifact";
  }
  // Unknown ## sections from the model — treat as copyable artifacts
  return "other";
}

function displayTitle(title: string): string {
  const key = headingKey(title);
  if (ARTIFACT_TITLES[key]) return ARTIFACT_TITLES[key];
  for (const [k, label] of Object.entries(ARTIFACT_TITLES)) {
    if (key === k || key.startsWith(`${k} `)) return label;
  }
  // Humanize slug-like headings if the model ever emits them
  if (/[_-]/.test(title) && !/\s/.test(title)) {
    return humanizeArtifactLabel(title);
  }
  return title;
}

function stripComments(markdown: string): string {
  return markdown.replace(/<!--[\s\S]*?-->/g, "").trim();
}

/**
 * Split markdown on ATX headings (# … ######).
 * Returns leading prose (no heading) plus heading sections.
 */
function splitByHeadings(markdown: string): { level: number; title: string; body: string }[] {
  const text = stripComments(markdown);
  const re = /^(#{1,6})\s+(.+?)\s*$/gm;
  const matches = [...text.matchAll(re)];
  if (!matches.length) {
    const body = text.trim();
    return body ? [{ level: 0, title: "", body }] : [];
  }

  const parts: { level: number; title: string; body: string }[] = [];
  const before = text.slice(0, matches[0].index).trim();
  if (before) {
    parts.push({ level: 0, title: "", body: before });
  }

  for (let i = 0; i < matches.length; i++) {
    const m = matches[i];
    const start = (m.index || 0) + m[0].length;
    const end = i + 1 < matches.length ? matches[i + 1].index || text.length : text.length;
    parts.push({
      level: m[1].length,
      title: normalizeHeading(m[2]),
      body: text.slice(start, end).trim(),
    });
  }
  return parts;
}

export function parseGenerationMarkdown(markdown: string): ParsedGeneration {
  const parts = splitByHeadings(markdown);
  let title = "Generation";
  let subtitle = "";
  const artifacts: GenerationSection[] = [];
  const grounding: GenerationSection[] = [];

  for (const part of parts) {
    if (!part.title) {
      // Leading prose — often "Application: …"
      const appLine = part.body.match(/^Application:\s*(.+)$/im);
      if (appLine) {
        subtitle = appLine[1].trim();
        const rest = part.body.replace(appLine[0], "").trim();
        if (rest) {
          artifacts.push({
            key: "intro",
            title: "Notes",
            body: rest,
            kind: "other",
          });
        }
      } else if (part.body) {
        artifacts.push({
          key: "intro",
          title: "Notes",
          body: part.body,
          kind: "other",
        });
      }
      continue;
    }

    const kind = classifyHeading(part.title);
    const key = headingKey(part.title);

    if (key.startsWith("generation")) {
      title = part.title.startsWith("Generation") ? part.title : `Generation ${part.title}`;
      // Body under the H1 is rarely useful; Application line may sit here
      const appLine = part.body.match(/^Application:\s*(.+)$/im);
      if (appLine) subtitle = appLine[1].trim();
      continue;
    }

    if (key.startsWith("application")) {
      subtitle = part.title.replace(/^Application:\s*/i, "").trim() || part.body.split("\n")[0]?.trim() || subtitle;
      continue;
    }

    if (kind === "meta") {
      if (part.body.trim()) {
        grounding.push({
          key,
          title: displayTitle(part.title),
          body: part.body.trim(),
          kind: "meta",
        });
      }
      continue;
    }

    artifacts.push({
      key,
      title: displayTitle(part.title),
      body: part.body.trim(),
      kind: kind === "artifact" ? "artifact" : "other",
    });
  }

  return { title, subtitle, artifacts, grounding };
}

/** Pull requested artifact types from sidecar list and/or HTML comment in the body. */
export function requestedArtifactLabels(
  types: string[] | undefined,
  markdown?: string,
): string[] {
  const fromTypes = (types || []).map((t) => t.trim().toLowerCase()).filter(Boolean);
  let fromComment: string[] = [];
  if (markdown) {
    const m = markdown.match(/types=([a-z0-9_,\-]+)/i);
    if (m) {
      fromComment = m[1]
        .split(",")
        .map((t) => t.trim().toLowerCase())
        .filter(Boolean);
    }
  }
  const keys = fromTypes.length ? fromTypes : fromComment;
  const labels: string[] = [];
  const seen = new Set<string>();
  for (const key of keys) {
    const bare = key.replace(/^custom:/, "");
    const label = ARTIFACT_TITLES[bare] || ARTIFACT_TITLES[headingKey(bare)] || humanizeArtifactLabel(bare);
    const norm = artifactMatchKey(label);
    if (seen.has(norm)) continue;
    seen.add(norm);
    labels.push(label);
  }
  return labels;
}
