# API Reference

Internal module and class documentation for the GitHub Backup Service.

---

## `src.backup`

### `parse_args() → Namespace`
Parses CLI arguments using `argparse`. Returns a `Namespace` with: `config`, `org`, `app_id`, `private_key`, `output`, `log_level`, `dry_run`.

### `main() → int`
Orchestrates the full backup run. Returns `0` on success, `1` on failure.

---

## `src.auth.Authenticator`

```python
Authenticator(app_id: str, private_key_path: str, base_url: str = "https://api.github.com")
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_token_for_org` | `(org_name: str) → str` | Returns a valid installation token; refreshes automatically |
| `get_installation_id` | `(org_name: str) → int` | Finds the App installation ID for the given org |
| `get_installation_token` | `(installation_id: int) → dict` | Exchanges installation ID for an access token dict |

---

## `src.api.GitHubAPIClient`

```python
GitHubAPIClient(token: str, base_url: str = "https://api.github.com",
                rate_limiter=None, error_handler=None)
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `get` | `(endpoint, params=None) → dict\|list` | Single GET request |
| `post` | `(endpoint, data) → dict` | Single POST request |
| `paginate` | `(endpoint, params=None) → list` | Auto-paginate all pages |
| `graphql` | `(query, variables=None) → dict` | Execute GraphQL query |

---

## `src.api.RateLimiter`

```python
RateLimiter(min_remaining: int = 100, sleep_buffer: float = 1.1)
```

| Method | Description |
|--------|-------------|
| `check_and_wait(headers)` | Sleeps if quota is low |
| `record_request()` | Increments request counter |
| `get_status() → dict` | Returns current quota status |

---

## `src.api.ErrorHandler`

```python
ErrorHandler(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0)
```

| Method | Description |
|--------|-------------|
| `execute_with_retry(func, *args, **kwargs)` | Retries with exponential back-off |
| `is_retryable(exception) → bool` | Classifies exception as retryable |
| `classify_error(exception) → str` | Returns `"auth"`, `"rate_limit"`, `"not_found"`, `"server_error"`, or `"unknown"` |

---

## `src.config.ConfigManager`

```python
ConfigManager(config_path: str)
```

| Method | Description |
|--------|-------------|
| `load() → dict` | Load YAML + apply env overrides |
| `get(key, default=None)` | Dot-notation access (e.g. `"github.app_id"`) |
| `validate() → bool` | Raises `ValueError` if required keys are missing |

---

## `src.storage.StorageManager`

```python
StorageManager(base_path: str, compress: bool = False)
```

| Method | Description |
|--------|-------------|
| `write_json(path, data, filename)` | Atomically write JSON |
| `read_json(path, filename) → dict\|list` | Read JSON |
| `write_text(path, filename, content)` | Atomically write text |
| `copy_file(src, dst_path, filename)` | Copy file |
| `ensure_dir(path)` | Create directory |
| `list_files(path, pattern) → list` | Glob file listing |

---

## `src.storage.BackupStructure`

```python
BackupStructure(base_path: str)
```

| Method | Returns | Example |
|--------|---------|---------|
| `org_path(org)` | `str` | `backup/organizations/my-org` |
| `repo_path(org, repo)` | `str` | `backup/repositories/my-org/my-repo` |
| `metadata_path(org, category)` | `str` | `backup/metadata/my-org/members` |
| `assets_path(org, repo)` | `str` | `backup/assets/my-org/my-repo` |
| `ensure_directories(org, repos)` | `None` | Creates all dirs |

---

## Collectors

All collectors extend `BaseCollector(api_client, storage_manager, org_name)`.

| Class | Key Methods |
|-------|-------------|
| `RepositoryCollector` | `collect()`, `clone_repository(repo, dest)`, `collect_and_clone(dest)` |
| `MetadataCollector` | `collect()`, `collect_repo_metadata(repo_name)` |
| `IssuesPRsCollector` | `collect(repo_name)`, `collect_issue_comments(repo, num)`, `collect_pr_comments(repo, num)` |
| `ReviewsCollector` | `collect(repo_name, pr_number)`, `collect_all_pr_reviews(repo_name, prs)` |
| `ReleasesCollector` | `collect(repo_name)`, `download_assets(release, dest)`, `collect_and_download(repo, dest)` |
| `WorkflowsCollector` | `collect(repo_name)`, `collect_workflow_file(repo, path)` |
| `OrgSettingsCollector` | `collect()` |
