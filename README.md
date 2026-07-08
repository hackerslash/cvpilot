# CVPilot

CVPilot is a Claude Code skill that tailors your resume to a specific job posting — automatically, truthfully, and without ever touching your main branch.

It keeps your full career history in one structured file (`db.json`) and a LaTeX style shell (`base_template.tex`), then for each job you give it a URL to:

- research the role and company,
- select only the truthful, relevant material from `db.json` (no invented claims, metrics, or skills),
- render a one-page, ATS-optimized PDF with the repo-local `tectonic` binary,
- and drop the result in `output/` — all inside an isolated git worktree, so your tracked files never change.

## Steps to use

1. Open this repo in Claude Code (or Codex — an equivalent skill copy lives under `.agents/`).
2. Seed your career history once:

   ```
   Refresh the base resume from /path/to/resume.txt
   ```

   This rebuilds `db.json` and `base_template.tex` from your source material and stops for your review.

3. Tailor for any job by pasting the posting URL in plain language:

   ```
   Tailor my resume for this job: https://company.com/job/backend-engineer
   ```

4. Find the generated PDF in `output/` (not tracked by git). The skill also reports a cover letter draft when the posting calls for one.

That's the whole workflow — everything below is reference detail for editing the underlying data directly.

## Candidate Database

`db.json` is the canonical inventory of candidate facts: contact details, summaries, education, experience, projects, skills, awards, tags, keywords, priorities, and repeatable bullets. Add as many bullets or entries as needed; tailoring selects relevant enabled material from this file and lightly rewrites it only when the facts stay unchanged.

To edit it in a browser:

```bash
scripts/config-db
```

Open the printed localhost URL, edit structured sections, validate, and save.

## Page Count

Use the dependency-free page checker to keep generated resumes tight:

```bash
scripts/check-page-count --pdf output/Resume_2026-05-21.pdf --max-pages 1 --json
```

`scripts/tailor-job --stage finalize --json` also reports `page_count`, `page_limit`, and `over_page_limit`. This is warn-only, so the PDF still gets written while the AI can iterate if the result is over one page.
