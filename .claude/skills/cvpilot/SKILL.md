---
name: cvpilot
description: >-
  Use this skill whenever the user shares a job URL, job description, or posting
  link — even if they just say "apply to this", "tailor my resume", "update my
  CV", "prep for this role", or "am I a good fit". Also trigger when the user
  wants to refresh, rebuild, or update their canonical resume from local files.
  This skill owns the full resume-tailoring pipeline for this repo: strict-truth
  selection from db.json, LaTeX rendering via the repo-local tectonic binary,
  isolated git-worktree editing so the main branch is never touched, and
  ATS-optimised PDF output. Activate for any job application, resume tailoring,
  resume refresh, or candidate-database update request in this repo — do not try
  to handle these workflows without the skill.
compatibility:
  tools: [Read, Edit, Write, MultiEdit, Glob, Grep, Bash, WebFetch, WebSearch]
---

# CVPilot

Two workflows live in this skill:

- `refresh-base`: rebuild the canonical tracked resume materials from user-provided text files.
- `tailor-job`: tailor the canonical resume for a specific job URL without touching the current branch.

## Rules

- Canonical candidate truth source is `db.json`. The tracked `base_template.tex` is the LaTeX style and layout shell.
- Tailoring is strict truth only: no invented claims, metrics, skills, titles, dates, technologies, or experience.
- The AI may select, reorder, trim, and lightly rewrite `db.json` entries when tailoring, but the meaning and facts must remain unchanged.
- For job tailoring, never edit files in the current worktree. Only edit the prepared temporary worktree.
- `refresh-base --stage prepare` acquires a PID-based lock (`.refresh-base.lock` in the repo root). The lock is released by `--stage validate`. Any `tailor-job --stage prepare` that runs while the lock is held will exit with an error. Do not start a tailor-job while a refresh is in progress.
- Render with the repo-local `tectonic` binary. Generated PDFs go to `output/` (gitignored).
- Keep tailored PDFs to one page. Finalize reports page count as a warning signal; if `over_page_limit` is true, revise the temporary worktree template before accepting the result.
- There is no single public ATS algorithm. Optimize for documented parser behavior, searchable structured fields, and keyword matching used by common ATS platforms.
- Research must be efficient. Follow the budget in [Research Protocol](#research-protocol): one JD fetch, up to three parallel company fetches, optional one WebSearch fallback. Stop there.

## Candidate Database

Use `db.json` as the inventory of all candidate material:

- `candidate`: contact details and profile links.
- `summaries`: reusable summary variants.
- `education`, `experience`, `projects`, `skills`, `awards`: major resume sections.
- Repeatable entries have stable `id`, `enabled`, `priority`, `tags`, `keywords`, and optional `technologies`.
- Experience and project entries contain repeatable `bullets`; each bullet can also have its own `id`, `enabled`, `priority`, `tags`, and `keywords`.

Prefer enabled entries with high relevance to the JD. Tags and keywords are matching aids, not facts by themselves; only render claims supported by entry text and metadata.

To edit the database manually, run:

```bash
scripts/config-db
```

Open the printed localhost URL, edit structured fields, validate, and save.

## Refresh Base

When the user asks to refresh/rebuild the canonical base resume from local files:

1. Run:

```bash
scripts/refresh-base --source /absolute/path/to/file1 --source /absolute/path/to/file2 --stage prepare --json
```

2. Read the emitted `source_bundle_path`.
3. Update `db.json` and, only when needed, `base_template.tex` in the current worktree while preserving the current template's style unless the user asked for a redesign.
4. Validate by running:

```bash
scripts/refresh-base --stage validate --state-file /path/to/state.json --json
```

5. Share the emitted review PDF path with the user and stop for review.

## Tailor Job

When the user provides a job URL or asks to tailor the resume for a role:

1. Detect ATS from the URL hostname (see [ATS Detection](#ats-detection)) and derive a clean `company` slug and `role` slug.
2. Prepare the isolated worktree:

```bash
scripts/tailor-job --job-url <job-url> --company <company-slug> --role <role-slug> --stage prepare --json
```

3. Read the emitted `db_snapshot_path` and `template_path` once. Treat `db_snapshot_path` as the ground-truth inventory of claims, metrics, technologies, dates, and titles you may use; treat `template_path` as the LaTeX style and structure to populate.
4. Run [Research Protocol](#research-protocol) to produce a short internal research brief.
5. Edit only the emitted `template_path` inside the temporary worktree. Select relevant enabled entries from `db_snapshot_path`, then apply [Tailoring Guidance](#tailoring-guidance).
6. Apply the [Font-Size Fill Pass](#font-size-fill-pass): before the first finalize, replace `\small` in the template with `\fontsize{11.5}{13.8}\selectfont` to target the maximum body size.
7. Finalize:

```bash
scripts/tailor-job --stage finalize --state-file /path/to/state.json --json
```

8. On success (`over_page_limit` false): accept the PDF — the fill pass is complete. If `over_page_limit` is true: follow the [Font-Size Fill Pass](#font-size-fill-pass) step-down rules (reduce font by 0.5pt, edit template, re-finalize). If still overflowing at `\fontsize{10.0}{12.0}\selectfont`, switch to trimming bullets per [Tailoring Guidance](#tailoring-guidance) instead. On any non-recoverable failure, report the preserved worktree path for debugging.
9. **Cover letter** — if the JD or application form mentions a cover letter field, include one in the final message. Keep it to 3 short paragraphs: (1) role + why this company specifically, (2) one or two truthful, concrete achievements from `db.json` that directly address the role's core need, (3) a single closing sentence. No more than ~150 words total. Strict-truth rule applies: do not invent claims. Derive company-specific context from the research brief already in memory.

## Research Protocol

The goal is a tight internal research brief, not a deep dive. Budget: **at most 5 fetches total**. Do not exceed it.

### Step 1 — Single JD extraction (1 fetch)

Call `WebFetch` once on the job URL with a structured extraction prompt. Pull everything in one pass:

```
Extract from this job posting and return as labeled sections:
- Exact job title (as posted)
- Title variants / level (e.g. "Senior", "Staff", "II")
- Required years of experience
- Must-have skills (verbatim from "Requirements" / "Qualifications")
- Nice-to-have skills (verbatim from "Preferred" / "Bonus")
- Core technologies, frameworks, platforms (verbatim)
- Domain vocabulary (industry-specific terms, methodologies, certifications)
- Scope and seniority markers (team size, ownership scope, leadership)
- Responsibilities (verbatim bullets)
- Repeated phrases (any term used 2+ times)
- Company name, team name, location, remote policy
- Application URL host (for ATS detection)
```

If the fetch fails (paywall, expired, JS-only render), fall back to one `WebSearch` for the exact job title + company, then try the top non-aggregator result with `WebFetch`. If still empty, ask the user to paste the JD text and stop.

### Step 2 — Parallel company research (up to 3 fetches)

In a **single message with parallel `WebFetch` calls**, fetch in this priority order, stopping once you have enough signal:

1. Company careers page or `about` page (official voice, values, mission)
2. Company engineering blog or product page relevant to the role (technical stack signal)
3. Company press / newsroom for recent direction (only if role is leadership or strategy-adjacent)

Skip Glassdoor, Levels.fyi, Reddit, and forum aggregators unless official sources yielded nothing. Skip news that is older than 12 months.

### Step 3 — Stop and write the brief

Hold the following in memory (do not write to disk):

- `target_title`: exact JD title to mirror where truthful
- `must_match_keywords`: ranked list, deduped, drawn only from JD must-haves that the canonical resume already supports
- `surface_first`: top 5 technologies/domain terms to push earlier in bullets
- `tone`: one-sentence read on company voice (e.g. "engineering-rigor-focused", "growth-stage scrappy", "regulated/compliance-heavy")
- `ats`: detected platform or `unknown`

If `must_match_keywords` is short because the JD asks for skills the canonical resume does not contain, that is the expected outcome. Do **not** invent matches.

## ATS Detection

Map application URL hostname to platform:

| Hostname contains | ATS |
|---|---|
| `greenhouse.io`, `boards.greenhouse.io` | Greenhouse |
| `lever.co`, `jobs.lever.co` | Lever |
| `myworkdayjobs.com`, `workday.com` | Workday |
| `icims.com` | iCIMS |
| `ashbyhq.com`, `jobs.ashbyhq.com` | Ashby |
| `smartrecruiters.com` | SmartRecruiters |
| `eightfold.ai`, `phenom.com`, `hirevue.com` | AI-screening layer (treat as Workday/iCIMS underneath) |

If no match, treat as `unknown` and apply the conservative parsing rules.

## Tailoring Guidance

Apply in this order:

1. **Select from `db.json` first.** Choose entries and bullets whose text, tags, keywords, and technologies truthfully match the JD. The database contains far more material than fits on one page — active curation is required, not optional.
2. **Apply a pre-render selection budget before writing any LaTeX.** Target these hard caps to keep the result one page:
   - Experience bullets: **3–5 per role** (pick by JD relevance, not priority rank alone)
   - Projects: **2–3 total** (pick the most JD-relevant; drop the rest entirely)
   - Skills items: keep all enabled skill rows but drop the `Interests` row unless it adds keyword value
   - Awards: 1–2 maximum; drop if space is tight
3. **Reorder before rewriting.** Move bullets so the most JD-relevant ones rise within each role. Reordering preserves truth at zero risk.
4. **Mirror JD phrasing where already true.** Swap synonyms in the selected database material for the JD's exact wording only when the underlying claim is unchanged.
5. **Expand abbreviations to match JD form.** Prefer explicit spellings like `OpenTelemetry`, `PostgreSQL`, `Redis`, `Kubernetes`, `TypeScript`.
6. **Surface high-signal nouns near relevant bullets** so parser-backed search indexes them.
7. **Trim least relevant bullets first** when residual one-page pressure remains after the selection budget is applied.
8. **Use standard section headings**: `Education`, `Experience`, `Projects`, `Skills`, `Awards`.
9. **Simplify, don't decorate.** Avoid adding icons, text boxes, columns, headers/footers, or graphics to the tailored copy. Keep text selectable.

## Font-Size Fill Pass

After writing the tailored template content, maximize readability by finding the largest body font that still fits on one page. This pass replaces the plain "keep it one page" rule — instead of just preventing overflow, it actively fills available space.

**Starting point:** Before the first finalize, replace the `\small` command that appears immediately after `\begin{document}` with:

```latex
\fontsize{11.5}{13.8}\selectfont
```

(11.5pt body, 13.8pt baseline skip — 1.2× leading ratio. This is the maximum target.)

**Iterative finalize loop:**

1. Run finalize with the current font set.
2. If `over_page_limit` is **false**: accept the PDF — fill pass is done.
3. If `over_page_limit` is **true**: reduce `X` by 0.5pt and `Y` by 0.6pt (maintaining 1.2× ratio), edit the template font line, and repeat from step 1.

Step-down sequence: `11.5/13.8` → `11.0/13.2` → `10.5/12.6` → `10.0/12.0`.

**Escape hatch:** If the resume still overflows at `\fontsize{10.0}{12.0}\selectfont` (equivalent to the original `\small`), the page is at capacity. Stop the fill pass and instead trim the least-relevant bullets per [Tailoring Guidance](#tailoring-guidance) until it fits, then finalize.

**Cap:** Never exceed `\fontsize{11.5}{13.8}\selectfont`. The section headings (`\large\bfseries`), `\resumeentry` tabular rows, and margins are calibrated for the 10–11.5pt body range.

**Skip the fill pass** only if tailoring already required trimming below the minimum content budget at 10pt — in that case the page is at capacity and there is nothing to fill.

## ATS Match Assumptions

Use these when reasoning about tailoring tradeoffs. They reflect documented behavior, not internal algorithms.

- **Greenhouse**: full-text and Boolean search across resumes. Complex layouts, multi-column, graphics, headers/footers, and text boxes raise parse failure risk.
- **Lever**: candidate search indexes parseable resume content with Boolean operators and a `Resume` filter. Image-based or non-selectable PDFs are not indexed.
- **iCIMS**: recruiters search by job title, keyword, skill, location pulled from structured profile fields. Completeness of structured fields drives findability.
- **Workday**: heavily structured profile import. Keyword retrieval is common; complete title and skill fields matter more than prose.
- **Ashby**: modern parser, generally more tolerant of layout, but still keyword-driven on the recruiter side.
- **AI-screening layers (Eightfold, Phenom, HireVue)**: rank against JD embeddings. Explicit keyword presence and standard section headings still outperform compressed shorthand.

Practical implications:

- Match the exact target title and must-have skill language where it is already true.
- Push the most relevant technologies, platforms, and domain vocabulary earlier in bullets and earlier in sections.
- Preserve selectable text in the rendered PDF.
- Prefer conventional, explicit wording over novelty or visual flourish when there is a tradeoff.

## Reference Files

- `references/db-schema.md` — Full field-by-field schema for `db.json`, including the `bullets` sub-schema and all optional fields. Read this when you need to add, edit, or validate entries in the candidate database.
