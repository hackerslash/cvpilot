<div align="center">

# CVPilot

A Claude Code skill that tailors your resume to a job posting, using only facts you've already recorded.

![Claude Code](https://img.shields.io/badge/Claude_Code-skill-D97757?style=flat-square)
![Python](https://img.shields.io/badge/Python-3-3776AB?style=flat-square&logo=python&logoColor=white)
![LaTeX](https://img.shields.io/badge/LaTeX-tectonic-008080?style=flat-square&logo=latex&logoColor=white)

</div>

CVPilot keeps your full career history in one structured file (`db.json`) and a LaTeX layout shell (`base_template.tex`). Give it a job URL and it researches the role, picks the relevant material, and renders a one-page PDF. All edits happen in a temporary git worktree, so your tracked files never change.

## Features

- Strict-truth tailoring: selects, reorders and lightly rewrites `db.json` entries, never invents claims, metrics or skills
- Short research pass on the job posting and company before selecting content
- One-page, ATS-friendly PDF rendered with the bundled `tectonic` binary
- Isolated git worktree per job; output lands in `output/` (gitignored)
- Page-count check that warns when a resume runs over one page
- Browser editor for `db.json` with validation
- Works in Claude Code (`.claude/skills/`) and Codex (`.agents/skills/`)

## Usage

1. Open the repo in Claude Code (or Codex).
2. Seed your career history once:

   ```
   Refresh the base resume from /path/to/resume.txt
   ```

   This rebuilds `db.json` and `base_template.tex` from your source material and stops for your review.

3. Tailor for a job by pasting the posting URL:

   ```
   Tailor my resume for this job: https://company.com/job/backend-engineer
   ```

4. Pick up the PDF from `output/`. If the posting asks for a cover letter, the skill also drafts one.

Requirements: `git` and Python 3. The committed `tectonic` binary is a macOS arm64 build; on other platforms, replace it with the matching [Tectonic](https://tectonic-typesetting.github.io/) release.

## Scripts

The skill drives these itself; you can also run them directly.

| Command | Purpose |
| --- | --- |
| `scripts/config-db` | Serve a local browser editor for `db.json` (prints the URL) |
| `scripts/refresh-base --stage prepare --source <file>` | Start rebuilding the base resume from source files |
| `scripts/tailor-job --stage prepare --job-url <url>` | Create the temporary worktree for a job |
| `scripts/tailor-job --stage finalize --state-file <file> --json` | Render the PDF and report `page_count` / `over_page_limit` |
| `scripts/check-page-count --pdf <file> --max-pages 1 --json` | Dependency-free page counter |

## Candidate database

`db.json` is the inventory of candidate facts: contact details, summaries, education, experience, projects, skills, awards, tags, keywords, priorities and reusable bullets. Add as many entries as you like; tailoring only uses enabled material that fits the job. The schema is documented in `.claude/skills/cvpilot/references/db-schema.md`.
