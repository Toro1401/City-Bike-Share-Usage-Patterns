# Project workflow

Read README.md and PRD.md for scope, supported commands and known limits. Keep their claims aligned with code and evidence. Preserve original data and unrelated staged work. Review ai-toolkit.json before executing its command arrays.

Run `python scripts/verify.py` from the project root using the project environment. Local reports go to ignored `.verification/latest.json`. They do not establish live-service, actual-browser or model-quality acceptance. Do not publish private/raw data. Any GitHub About update is a separate external operation within the user's authorized scope.

Authoritative pipeline: analysis/ingest.py + analysis/build_portfolio.py. Preserve raw databases; account for quarantines and missing periods. Station observations are not verified physical station identities.
