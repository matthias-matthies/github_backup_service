# GitHub Organization Backup Service

A comprehensive backup solution for GitHub organizations that preserves all data including repositories, history, pull requests, issues, releases, comments, reviews, discussions, and more.

## Features

- **Complete Repository Backup**: Full git history, branches, and tags
- **Issues & Pull Requests**: All discussions, comments, and metadata
- **Releases & Assets**: Download all release artifacts
- **Code Reviews**: Preserve review comments and decisions
- **User Data**: Members, teams, permissions, and roles
- **Workflows**: CI/CD configurations and run history
- **Discussions**: Community discussions and threads
- **Labels & Milestones**: Project management metadata
- **Webhooks & Settings**: Organization configuration backup

## Requirements

- Python 3.8+
- GitHub App installed on your organization
- Sufficient storage for backup data

## Installation

```bash
git clone <repository>
cd github_backup_service
pip install -r requirements.txt
```

## Usage

```bash
python backup.py --org <organization_name> --app-id <app_id> --private-key <path_to_key> --output <backup_path>
```

## Configuration

See `config.example.yml` for available options, app credentials, and API rate limit settings.

## Supported Data

- Repositories and git history
- Issues and comments
- Pull requests and reviews
- Releases and assets
- Organizations, teams, and members
- Labels, milestones, and projects
- Workflows and run history

## License

MIT

