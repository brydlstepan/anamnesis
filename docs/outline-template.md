# Outline template — medical record

How to use Outline as a source for Anamnesis.

## Setup
1. Admin sets the Outline base URL in Anamnesis Admin → Settings.
2. In Outline, create a collection or a parent document per person, e.g. `Health / Stepan`.
3. In Anamnesis → Sources → *Add source → Outline*: paste your **own** Outline API token (Outline → Settings → API), then pick the collection/document subtree. Everything under it belongs to your profile.
4. Optional: create the template below in Outline (*Templates → New template*) so new records start pre-filled.

## Rules
- **One page = one record.**
- The **first** fenced code block with language `medrecord` contains the structured fields (YAML, see `medrecord-schema.md`).
- Everything else on the page is shown as the record's description (Markdown).
- Files attached to the page are imported as attachments (cached locally).
- Sub-pages are separate records; folder structure is up to you.
- Pages without a `medrecord` block are ignored (listed as *unparsed* in Sources → Issues if enabled).
- **To show on the 3D body, fill `regions`.** Records are read-only in Anamnesis — edit them in Outline.

## Template

````markdown
```medrecord
type: exam            # condition | procedure | exam | observation | medication | allergy | vaccination | document
title: 
date:                 # YYYY-MM-DD (or YYYY-MM / YYYY)
regions: []           # e.g. [knee:left], [lungs], [systemic]  → see Anamnesis "Regions" list
# --- type-specific (delete what you don't need) ---
kind:                 # exam: imaging | specialist | preventive | emergency | other
status:               # condition: active | resolved | remission; medication: active | stopped
facility: 
practitioner: 
codes: []             # e.g. [{system: icd10, code: J45}]
tags: []
```

## Summary

## Findings / notes

## Attachments
_Drag the report PDF / photos here._
````

## Example page

````markdown
```medrecord
type: procedure
title: Meniscus repair
date: 2021-03-18
regions: [knee:left]
facility: Nemocnice Na Bulovce
practitioner: MUDr. Novák
outcome: successful
```

## Summary
Arthroscopic repair of the medial meniscus after a ski injury.

## Recovery
Crutches 4 weeks, physiotherapy 3 months.
````
