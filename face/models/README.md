# Face models

Model files go in this folder. They are git-ignored, so they are never committed.

Phase 5 adds `scripts/download_models.py`, which fetches each model and checks its SHA-256 against the list in the repo.

Each embedding stores the model version it was made with, so do not swap a model without planning re-enrollment.
