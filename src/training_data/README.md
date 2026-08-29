# Training Data Builders

The original project-specific newsletter extraction scripts have been removed.

For a new tracker, add scripts here if you need to transform historical newsletters,
spreadsheets, exported labels, or annotation-tool output into the expected modelling
files:

- `data/modelling/train.csv`
- `data/modelling/val.csv`

Required columns are `text_clean` and `target`.
