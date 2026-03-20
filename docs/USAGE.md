# Usage Guide

## Quick Start

```bash
# Using a config file (recommended)
python -m src.backup --config config.yml

# Using CLI flags
python -m src.backup \
  --org my-organisation \
  --app-id 123456 \
  --private-key ./github-app.private-key.pem \
  --output ./backup
```

---

## CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--config PATH` | Path to YAML config file | — |
| `--org NAME` | GitHub organisation name | — |
| `--app-id ID` | GitHub App ID | — |
| `--private-key PATH` | Path to RSA private key PEM | — |
| `--output PATH` | Backup output directory | `./backup` |
| `--log-level LEVEL` | Logging verbosity | `INFO` |
| `--dry-run` | Simulate without writing | `false` |

---

## Backup Workflows

### Full Backup

```bash
python -m src.backup --config config.yml
```

Backs up everything: repositories (mirror clone), issues, PRs, reviews, releases + assets, workflows, org metadata.

### Dry Run (Preview)

```bash
python -m src.backup --config config.yml --dry-run
```

Authenticates, lists all repositories and data to be collected, but writes nothing.

### Verbose Debug Run

```bash
python -m src.backup --config config.yml --log-level DEBUG
```

### Windows Script

```powershell
.\scripts\run_backup.ps1
.\scripts\run_backup.ps1 -Config "C:\backups\config.yml" -LogLevel DEBUG
.\scripts\run_backup.ps1 -DryRun
```

---

## Backup Output Structure

```
backup/
├── organizations/
│   └── my-org/
│       └── org_settings.json
├── repositories/
│   └── my-org/
│       └── my-repo/
│           ├── git/              ← bare mirror clone
│           ├── repo_metadata.json
│           ├── issues_prs.json
│           ├── reviews.json
│           ├── releases.json
│           └── workflows.json
├── metadata/
│   └── my-org/
│       └── members/
│           └── metadata.json
└── assets/
    └── my-org/
        └── my-repo/
            └── v1.0.0-asset.zip
```

---

## Incremental Backup

Re-running the service on an existing backup is safe:
- Git repositories are **fetched** (not re-cloned) if the local copy already exists.
- JSON files are **overwritten** with the latest data.

---

## Restore Notes

- **Git data**: bare mirrors can be cloned directly: `git clone ./backup/repositories/my-org/my-repo/git`
- **Metadata**: all JSON files are self-contained and human-readable.
- **Assets**: binary release assets are stored as-is in `backup/assets/`.
