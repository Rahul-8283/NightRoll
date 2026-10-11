#!/bin/sh
# Check the mounted model files against the recorded checksums, then start the worker.
# A model that is missing or different stops the container here, with the reason in its log,
# instead of letting InsightFace quietly fetch an unverified copy.
set -eu

python scripts/download_models.py --verify-only
exec "$@"
