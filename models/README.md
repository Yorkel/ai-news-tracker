# Model Artefacts

Trained model files are intentionally not committed to this template.

After adding labelled data, run:

```bash
python src/pipeline.py --training
```

A deployed tracker should store only the artefacts needed by the classifier API,
plus metadata that explains the training data, labels, metrics, and intended use.
