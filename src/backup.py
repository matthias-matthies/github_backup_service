"""Main CLI entry point for the GitHub Backup Service."""

import logging
import sys
import argparse
import os

from .utils.logger import setup_logger
from .config.config_manager import ConfigManager
from .auth.authenticator import Authenticator
from .api.github_api_client import GitHubAPIClient
from .api.rate_limiter import RateLimiter
from .api.error_handler import ErrorHandler
from .storage.storage_manager import StorageManager
from .storage.backup_structure import BackupStructure
from .collectors.org_settings_collector import OrgSettingsCollector
from .collectors.metadata_collector import MetadataCollector
from .collectors.repository_collector import RepositoryCollector
from .collectors.issues_prs_collector import IssuesPRsCollector
from .collectors.reviews_collector import ReviewsCollector
from .collectors.releases_collector import ReleasesCollector
from .collectors.workflows_collector import WorkflowsCollector


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="GitHub Organisation Backup Service",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Path to YAML configuration file.",
    )
    parser.add_argument("--org", metavar="NAME", help="GitHub organisation name.")
    parser.add_argument("--app-id", metavar="ID", help="GitHub App ID.")
    parser.add_argument(
        "--private-key",
        metavar="PATH",
        help="Path to the GitHub App RSA private key PEM file.",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default="backup",
        help="Output directory for backup data.",
    )
    parser.add_argument(
        "--log-level",
        metavar="LEVEL",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity level.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate backup without writing data.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the backup service and return an exit code."""
    args = parse_args()

    # ── Logging setup ─────────────────────────────────────────────────────
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logger = setup_logger("github_backup", log_file="logs/backup.log", level=log_level)
    logger.info("GitHub Backup Service starting.")

    try:
        # ── Configuration ─────────────────────────────────────────────────
        if args.config:
            config_manager = ConfigManager(args.config)
            config_manager.load()
            config_manager.validate()
            org_name: str = config_manager.get("github.org_name")
            app_id: str = config_manager.get("github.app_id")
            private_key_path: str = config_manager.get("github.private_key_path")
            output_path: str = config_manager.get("output.base_path", args.output)
        else:
            if not args.org or not args.app_id or not args.private_key:
                logger.error(
                    "Provide --config or all of --org, --app-id, --private-key."
                )
                return 1
            org_name = args.org
            app_id = args.app_id
            private_key_path = args.private_key
            output_path = args.output

        if args.dry_run:
            logger.info("Dry-run mode enabled — no data will be written.")

        # ── Authentication ────────────────────────────────────────────────
        logger.info("Authenticating with GitHub App %s for org '%s'.", app_id, org_name)
        authenticator = Authenticator(app_id=app_id, private_key_path=private_key_path)
        token: str = authenticator.get_token_for_org(org_name)

        # ── API client ────────────────────────────────────────────────────
        api_client = GitHubAPIClient(
            token=token,
            rate_limiter=RateLimiter(),
            error_handler=ErrorHandler(),
        )

        # ── Storage ───────────────────────────────────────────────────────
        storage = StorageManager(output_path)
        structure = BackupStructure(output_path)
        structure.ensure_directories(org_name, [])

        # ── Org settings ──────────────────────────────────────────────────
        logger.info("Collecting organisation settings …")
        org_collector = OrgSettingsCollector(api_client, storage, org_name)
        org_data = org_collector.collect()
        if not args.dry_run:
            org_path = structure.org_path(org_name)
            storage.write_json(org_path, org_data, "org_settings.json")

        # ── Org metadata (members, teams …) ──────────────────────────────
        logger.info("Collecting organisation metadata …")
        meta_collector = MetadataCollector(api_client, storage, org_name)
        meta_data = meta_collector.collect()
        if not args.dry_run:
            metadata_path = structure.metadata_path(org_name, "members")
            storage.write_json(metadata_path, meta_data, "metadata.json")

        # ── Repositories ──────────────────────────────────────────────────
        logger.info("Collecting repositories …")
        repo_collector = RepositoryCollector(api_client, storage, org_name)
        repos = repo_collector.collect()

        issues_collector = IssuesPRsCollector(api_client, storage, org_name)
        reviews_collector = ReviewsCollector(api_client, storage, org_name)
        releases_collector = ReleasesCollector(api_client, storage, org_name)
        workflows_collector = WorkflowsCollector(api_client, storage, org_name)

        for repo in repos:
            repo_name: str = repo["name"]
            logger.info("Processing repository: %s", repo_name)
            repo_path = structure.repo_path(org_name, repo_name)

            if not args.dry_run:
                # Clone / mirror the repository
                repo_collector.clone_repository(repo, os.path.join(repo_path, "git"))

                # Per-repo metadata
                repo_meta = meta_collector.collect_repo_metadata(repo_name)
                storage.write_json(repo_path, repo_meta, "repo_metadata.json")

                # Issues & PRs
                issues_prs = issues_collector.collect(repo_name)
                storage.write_json(repo_path, issues_prs, "issues_prs.json")

                # Reviews
                prs = issues_prs.get("pull_requests", [])
                reviews = reviews_collector.collect_all_pr_reviews(repo_name, prs)
                storage.write_json(repo_path, reviews, "reviews.json")

                # Releases & assets
                assets_path = structure.assets_path(org_name, repo_name)
                releases_data = releases_collector.collect_and_download(
                    repo_name, assets_path
                )
                storage.write_json(repo_path, releases_data, "releases.json")

                # Workflows
                workflows_data = workflows_collector.collect(repo_name)
                storage.write_json(repo_path, workflows_data, "workflows.json")

        logger.info("Backup completed successfully.")
        return 0

    except Exception as exc:  # noqa: BLE001
        logging.getLogger("github_backup").error("Backup failed: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
