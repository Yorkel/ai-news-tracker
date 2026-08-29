# Security Policy

This template is designed for public source code, not public credentials or private data.

## Do not commit

- API keys or personal access tokens.
- Supabase service-role keys.
- `.env` files.
- Raw private emails, exported inboxes, or proprietary source lists.
- Labelled training data unless the dataset is cleared for publication.
- Trained model artefacts unless they are intentionally public.

## Runtime configuration

Store runtime secrets in the deployment platform and in GitHub Actions secrets.
Use `.env.example` only as a checklist of variable names.

## Public deployments

If the classifier API is reachable from the public internet, set `CLASSIFIER_API_KEY`
so `/predict` and `/metrics` require a bearer token. Keep `/health` lightweight and
free of sensitive details.

## Reporting a vulnerability

Open a private advisory or contact the repository owner directly. Include the affected
file, the behaviour observed, and the minimal steps needed to reproduce it.
