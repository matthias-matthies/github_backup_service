# Troubleshooting Guide

## Authentication Errors

### `RuntimeError: No installation found for organisation 'my-org'`
- The GitHub App is not installed on the organisation.
- Go to your GitHub App settings → **Install App** → select your org.

### `jwt.exceptions.InvalidKeyError`
- The private key file is corrupted or in the wrong format.
- Re-download the `.pem` file from your GitHub App settings.
- Ensure `private_key_path` in `config.yml` points to the correct file.

### `401 Unauthorized` on API requests
- The installation token has expired (they last 1 hour). The service auto-refreshes tokens; if errors persist, check system clock synchronisation.

---

## Permission Errors

### `403 Forbidden` on `/orgs/{org}/hooks`
- The GitHub App lacks the **Administration** (read) organisation permission.
- Update the App permissions and re-approve the installation.

### `403 Forbidden` on `/orgs/{org}/actions/permissions`
- Normal for organisations where Actions is disabled. The collector handles this gracefully and returns `{}`.

---

## Rate Limit Issues

### `API rate limit exceeded`
- The backup is using too many requests. Increase `rate_limiting.min_remaining` in `config.yml` to be more conservative.
- Reduce `parallelism.repo_workers` to serialise repository processing.
- Schedule backups during off-peak hours.

### `RateLimitExceededException` in logs
- The service will automatically sleep until the rate limit resets. This is normal behaviour for large organisations.

---

## Git Clone Failures

### `git.exc.GitCommandError: Cmd('git') failed`
- Ensure `git` is installed and available on `$PATH`.
- Check that the installation token has **Contents: read** permission.
- For private repositories, verify the App is installed with access to those repos.

### Mirror clone falls back to regular clone
- Some repositories do not support `--mirror`. The service automatically falls back to a regular clone. This is logged at `WARNING` level and is not an error.

---

## Storage / Disk Issues

### `OSError: [Errno 28] No space left on device`
- Free up disk space. Large organisations can require tens or hundreds of GB.
- Point `output.base_path` to a volume with sufficient space.

### Incomplete JSON files
- Atomic writes (write-to-temp + rename) protect against partial writes.
- If you see `.json.tmp` files, a previous run was interrupted. Delete them and re-run.

---

## Common Configuration Mistakes

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `FileNotFoundError: config.yml` | Wrong `--config` path | Verify path with `ls config.yml` |
| `ValueError: Missing required keys` | Incomplete config | Check all `github.*` and `output.*` keys |
| `FileNotFoundError: /path/to/key.pem` | Wrong `private_key_path` | Use absolute path |
| Empty `backup/` after run | `--dry-run` was set | Remove `--dry-run` flag |

---

## Enabling Debug Logging

```bash
python -m src.backup --config config.yml --log-level DEBUG
```

Debug logs include: API request URLs, pagination details, rate-limit header values, retry attempts, and file write operations. Check `logs/backup.log` for the full run history.
