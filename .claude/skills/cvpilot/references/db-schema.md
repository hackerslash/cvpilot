# db.json Schema Reference

`db.json` is the single source of truth for all candidate facts. Nothing may appear on the resume unless it originates here.

---

## Top-Level Keys

| Key | Type | Description |
|---|---|---|
| `candidate` | object | Contact details and profile links |
| `summaries` | array | Reusable summary paragraph variants |
| `education` | array | Degree and institution entries |
| `experience` | array | Work experience entries (each with sub-bullets) |
| `projects` | array | Side-project and open-source entries |
| `skills` | array | Skill-row entries (e.g. "Languages", "Frameworks") |
| `awards` | array | Award and recognition entries |

---

## Shared Entry Fields

Every repeatable entry (in `summaries`, `education`, `experience`, `projects`, `skills`, `awards`) supports these fields:

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | ✅ | Stable unique identifier. Never change after creation. |
| `enabled` | boolean | ✅ | `false` entries are excluded from all renders unless explicitly overridden. |
| `priority` | integer | ✅ | 0–100. Higher = preferred when space is tight. Used for selection ordering but not a hard rule — relevance to JD can override. |
| `tags` | string[] | ✅ | Categorical labels (e.g. `"backend"`, `"leadership"`, `"open-source"`). Used for grouping and filtering, not rendered. |
| `keywords` | string[] | ✅ | Exact ATS/JD match terms. Also not rendered directly — they guide selection and bullet-level keyword surfacing. |
| `technologies` | string[] | ❌ | Specific tech stack items this entry relates to. Subset of `keywords`, more granular. |
| `text` | string | context | Plain-text claim for single-text entries (`awards`, `summaries`). Mutually exclusive with `bullets`. |

---

## `candidate`

```jsonc
{
  "candidate": {
    "name": "Full Name",
    "headline": "One-line role title (e.g. Backend Engineer)",
    "email": "email@example.com",
    "phone": "+1-xxx-xxx-xxxx",          // optional
    "location": "City, Country",          // optional
    "links": [
      {
        "id": "github",                   // stable id
        "kind": "github",                 // github | linkedin | portfolio | other
        "label": "Display text",
        "url": "https://..."
      }
    ]
  }
}
```

---

## `experience` Entries

Experience entries extend the shared fields with a `bullets` array:

```jsonc
{
  "id": "company-role-slug",
  "enabled": true,
  "priority": 90,
  "tags": ["backend", "distributed-systems"],
  "keywords": ["Go", "Kubernetes", "observability"],
  "technologies": ["Go", "Kubernetes", "Prometheus"],
  "company": "Acme Corp",
  "role": "Software Engineer",
  "location": "Remote",
  "start": "2022-06",                   // YYYY-MM
  "end": "2024-03",                     // YYYY-MM or "present"
  "bullets": [
    {
      "id": "acme-observability-bullet",  // stable id
      "enabled": true,
      "priority": 85,
      "tags": ["observability", "backend"],
      "keywords": ["OpenTelemetry", "Prometheus", "tracing"],
      "text": "Reduced p99 latency 40% by introducing distributed tracing with OpenTelemetry and Prometheus across 12 microservices."
    }
  ]
}
```

Bullet fields mirror the parent entry's shared fields — each bullet can be individually enabled/disabled, prioritised, tagged, and keyword-matched.

---

## `projects` Entries

Same structure as `experience` entries but without `company`, `role`, `location`, `start`, `end`. Use a `name` field instead:

```jsonc
{
  "id": "project-slug",
  "enabled": true,
  "priority": 75,
  "name": "Project Display Name",
  "url": "https://github.com/...",       // optional
  "tags": ["open-source", "backend"],
  "keywords": ["Rust", "WebAssembly"],
  "technologies": ["Rust", "WASM"],
  "bullets": [ /* same bullet schema as experience */ ]
}
```

---

## `education` Entries

```jsonc
{
  "id": "university-degree-slug",
  "enabled": true,
  "priority": 80,
  "tags": ["cs", "undergraduate"],
  "keywords": ["B.Tech", "Computer Science"],
  "institution": "University Name",
  "degree": "B.Tech in Computer Science and Engineering",
  "location": "City, Country",
  "start": "2019",                       // YYYY or YYYY-MM
  "end": "2023",
  "gpa": "9.1/10",                       // optional
  "bullets": []                          // optional, rarely used
}
```

---

## `skills` Entries

Skills are rendered as label → value rows (e.g. "Languages: Go, Python, TypeScript"):

```jsonc
{
  "id": "skills-languages",
  "enabled": true,
  "priority": 90,
  "tags": ["skills"],
  "keywords": ["Go", "Python", "TypeScript"],
  "label": "Languages",
  "text": "Go, Python, TypeScript, Rust, SQL"
}
```

---

## `summaries` Entries

```jsonc
{
  "id": "summary-backend-senior",
  "enabled": true,
  "priority": 80,
  "tags": ["backend", "senior"],
  "keywords": ["distributed systems", "platform engineering"],
  "text": "Backend engineer with 4+ years building distributed systems at scale..."
}
```

---

## `awards` Entries

```jsonc
{
  "id": "award-slug",
  "enabled": true,
  "priority": 70,
  "tags": ["achievement"],
  "keywords": ["JEE Main", "99th percentile"],
  "text": "Scored 99.10 percentile in JEE Main 2019 among 8.7 lakh candidates."
}
```

---

## Editing Guidelines

- **Never invent** ids, companies, dates, metrics, or technologies. Only add entries that reflect real, verifiable facts.
- **Prefer `enabled: false`** over deletion when retiring an entry — disabling preserves history.
- **Stable ids**: once set, ids must not change. They are referenced by scripts and state files.
- **Priority** is a relative hint (0–100), not a strict rank. Two entries with the same priority are equally preferred; JD relevance breaks the tie.
- To edit interactively: `scripts/config-db` → open the printed localhost URL → edit → validate → save.
