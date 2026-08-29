# Data Guidance

This template does not include the original project dataset. Each new tracker should
document its own data sources, lawful basis, update cadence, retention policy, and
publication boundary.

## Expected local-only paths

- `data/raw/`: raw scraped exports or imported source material.
- `data/interim/`: cleaned intermediate files.
- `data/modelling/`: train/validation CSVs and prediction outputs.
- `data/archive/`: audit files such as rejected scrape rows.

These paths are ignored by Git by default unless a placeholder file is explicitly
committed.

## Before publishing a derived tracker

- Confirm the source roster can be public.
- Confirm labelled examples can be public, or keep them out of the repo.
- Confirm trained artefacts do not memorise or expose private text.
- Record the dataset decision in the datasheet template.
