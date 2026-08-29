# Publication Checklist

Use this before making a tracker repository public.

- [ ] `git log --oneline` shows only the intended public history.
- [ ] No `.env`, tokens, credentials, or service-role keys are tracked.
- [ ] No raw private source material is tracked under `data/`.
- [ ] No trained model artefacts are tracked unless intentionally public.
- [ ] Source config has been reviewed for private feed URLs or personal names.
- [ ] `config/domain.yml` matches the new tracker domain and labels.
- [ ] Governance docs are project-specific, not copied from a previous client.
- [ ] GitHub Actions schedules are enabled only after secrets are configured.
- [ ] `python -m pytest tests/ -q` passes.
- [ ] README accurately describes the deployed tracker.
