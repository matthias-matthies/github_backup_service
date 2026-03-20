# Installation Guide

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Python | 3.8 or newer |
| Git | Any recent version |
| GitHub App | Installed on your organisation (see below) |
| Disk space | Proportional to the size of your repositories + metadata |

---

## 1. GitHub App Setup

1. Go to **Settings → Developer settings → GitHub Apps → New GitHub App**.
2. Set a name (e.g. `org-backup-bot`), homepage URL, and **disable** the Webhook.
3. Grant the following **Repository permissions** (read-only):
   - Contents, Issues, Pull requests, Actions, Metadata, Projects, Releases
4. Grant the following **Organisation permissions** (read-only):
   - Members, Administration, Webhooks
5. Install the App on your organisation.
6. Note the **App ID: 3141001** and download the **private key** (`.pem` file).

Client: Iv23licWEKAWY30uBKhI

---

## 2. Clone the Repository

```bash
git clone <repository-url>
cd github_backup_service
```

---

## 3. Linux / macOS Setup

```bash
bash scripts/setup.sh
```

This script:
- Creates a `.venv` virtual environment
- Installs all dependencies from `requirements.txt`
- Creates the `backup/` and `logs/` directory structure
- Copies `config.example.yml` → `config.yml` (if not present)

---

## 4. Windows Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Create runtime directories
New-Item -ItemType Directory -Force backup\organizations, backup\repositories, backup\metadata, backup\assets, logs
Copy-Item config.example.yml config.yml
```

---

## 5. Configuration

Edit `config.yml` with your credentials:

```yaml
github:
  app_id: "123456"
  private_key_path: "/path/to/github-app.private-key.pem"
  org_name: "my-organisation"

output:
  base_path: "./backup"
```

See [`config.example.yml`](../config.example.yml) for all available options.

---

## 6. Verify Installation

```bash
python -m src.backup --help
```
