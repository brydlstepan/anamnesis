# `medrecord` schema (v1)

One record = one YAML (or JSON) object. Used by:
- Outline pages (fenced block with language `medrecord`),
- Folder source files (`*.yaml`, `*.yml`, `*.json`),
- REST API / MCP `create_record` payloads (JSON).

The in-app form produces the same structure. Field semantics: see `SPEC.md` §4.

## Conventions
- `schema: 1` — schema version (optional, defaults to latest).
- `id` — optional stable external ID. If absent, Outline uses the page ID and Folder uses the relative file path.
- Dates: ISO 8601, partial allowed: `2019`, `2019-05`, `2019-05-14`, or with time `2019-05-14T09:30`.
- Regions: `region_id` or `region_id:left|right|both` (see `regions.md`), or object form with offset:
  `{region: "knee:left", offset: [0.2, -0.1, 0.8]}` (region-local, -1..1).
- Codes: `{system, code, display?}` where `system` ∈ `icd10 | snomed | loinc | atc | custom`.
- Attachments: paths relative to the record file (Folder), Outline attachments are picked up automatically.
- Unknown fields are kept in `extra` and shown in the detail view (forward compatibility).
- The code examples below are illustrative; verify codes before relying on them.

## Common fields

```yaml
schema: 1
type: procedure            # required: condition|procedure|exam|observation|medication|allergy|vaccination|document
title: Arthroscopy of left knee   # required
date: 2021-03-18           # required
end_date:                  # optional
regions: [knee:left]       # required for procedure; otherwise optional (defaults to systemic where needed)
status:                    # type-dependent
codes: []
facility: Nemocnice Na Bulovce
practitioner: MUDr. Novák
tags: [sport-injury]
links: []                  # ids of related records
attachments: [discharge-report.pdf]
model_overlay:             # optional custom GLB rendered inside the body
  file: knee-mri-segmentation.glb
  anchor_region: knee:left
  offset: [0, 0, 0]
  rotation: [0, 0, 0]      # degrees
  scale: 1.0
```

## Per type

### condition
Required: `status` (`active` | `resolved` | `remission`).

```yaml
type: condition
title: Bronchial asthma
date: 2012
status: active
severity: mild             # mild|moderate|severe
regions: [lungs]
codes:
  - {system: icd10, code: J45, display: Asthma}
```

### procedure
Required: `regions`.

```yaml
type: procedure
title: Meniscus repair
date: 2021-03-18
regions: [knee:left]
outcome: successful
implants:
  - {name: Meniscal anchor, material: PEEK, count: 2}
links: [cond-meniscus-tear-2021]
facility: Nemocnice Na Bulovce
attachments: [operation-report.pdf]
```

### exam
Required: `kind` (`imaging` | `specialist` | `preventive` | `emergency` | `other`).

```yaml
type: exam
title: MRI left knee
date: 2021-02-02
kind: imaging
regions: [knee:left]
findings: Tear of medial meniscus, posterior horn.
attachments: [mri-report.pdf]
```

### observation
Required: `name`, `value`, `unit`. Grouped into trend charts by `name` (or LOINC code if present).

```yaml
type: observation
title: Total cholesterol
date: 2025-11-04
name: Total cholesterol
value: 5.4
unit: mmol/L
reference_range: {low: 2.9, high: 5.0}
interpretation: high       # low|normal|high|critical (optional; computed from range if absent)
regions: [systemic]
codes:
  - {system: loinc, code: 2093-3}
```

Multiple results from one lab report → one record each (the MCP agent creates them in a batch, sharing the same attachment).

### medication
Required: `name`, `status` (`active` | `stopped`).

```yaml
type: medication
title: Salbutamol inhaler
date: 2012-06
name: Salbutamol
status: active
dose: 100 µg
frequency: as needed
reason: cond-asthma-2012
codes:
  - {system: atc, code: R03AC02}
```

### allergy
Required: `substance`, `criticality` (`low` | `high` | `unknown`).

```yaml
type: allergy
title: Penicillin allergy
date: 2004
substance: Penicillin
criticality: high
reaction: Urticaria, facial swelling
regions: [skin]
```

### vaccination
Required: `vaccine`.

```yaml
type: vaccination
title: Tick-borne encephalitis — booster
date: 2024-04-10
vaccine: TBE vaccine
dose_number: 4
batch: AB1234
regions: [upper_arm:left]
```

### document
Required: `file`.

```yaml
type: document
title: Discharge summary 2021
date: 2021-03-20
file: discharge-summary.pdf
links: [proc-meniscus-repair-2021]
```

## Fields set by the app (never in source files)
`person_id`, `origin`, `review_state`, `provenance`, `deleted_at`, version history.

## Validation behaviour
- Missing required field → record listed under *Source → Issues* (imports) or rejected with 422 (API/MCP).
- Unknown region id → issue/422 with suggestions (closest region ids).
- Lateral region without side → issue/422.
