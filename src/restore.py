"""CLI entry point for the GitHub Organisation Backup Restore Service."""

from __future__ import annotations

import argparse
import logging
import sys

from .utils.logger import setup_logger
from .config.config_manager import ConfigManager
from .auth.authenticator import Authenticator
from .api.github_api_client import GitHubAPIClient
from .api.rate_limiter import RateLimiter
from .api.error_handler import ErrorHandler
from .storage.storage_manager import StorageManager
from .restore.restore_manager import RestoreManager


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the restore service.

    Returns:
        Parsed :class:`argparse.Namespace` instance.
    """
    parser = argparse.ArgumentParser(
        description="GitHub Organisation Backup Restore Service",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Path to YAML configuration file.",
    )
    parser.add_argument(
        "--org",
        metavar="NAME",
        help="GitHub organisation name to restore into.",
    )
    parser.add_argument(
        "--backup-path",
        metavar="PATH",
        default="./backup",
        help="Root directory of the backup snapshot to restore from.",
    )
    parser.add_argument(
        "--only",
        metavar="DOMAINS",
        help=(
            "Comma-separated list of domains to restore "
            "(e.g. repositories,metadata,issues_prs)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate restore without making any API calls.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Abort immediately on conflicts without prompting.",
    )
    parser.add_argument(
        "--log-level",
        metavar="LEVEL",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity level.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the restore service and return an exit code.

    Returns:
        ``0`` on success, ``1`` on error, ``2`` on unresolved conflict.
    """
    args = parse_args()

    # ── Logging setup ──────────────────────────────────────────────────────
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logger = setup_logger("github_restore", log_file="logs/restore.log", level=log_level)
    logger.info("GitHub Restore Service starting.")

    try:
        # ── Configuration ──────────────────────────────────────────────────
        if args.config:
            config_manager = ConfigManager(args.config)
            config_manager.load()
            config_manager.validate()
            org_name: str = config_manager.get("github.org_name")
            app_id: str = config_manager.get("github.app_id")
            private_key_path: str = config_manager.get("github.private_key_path")
            backup_path: str = config_manager.get(
                "restore.backup_path", args.backup_path
            )
        else:
            if not args.org:
                logger.error(
                    "Provide --config or at least --org to identify the target organisation."
                )
                return 1
            org_name = args.org
            app_id = ""
            private_key_path = ""
            backup_path = args.backup_path

        if args.dry_run:
            logger.info("Dry-run mode enabled — no API calls will be made.")

        # ── Authentication ─────────────────────────────────────────────────
        logger.info(
            "Authenticating with GitHub App %s for org '%s'.", app_id, org_name
        )
        authenticator = Authenticator(
            app_id=app_id, private_key_path=private_key_path
        )
        token: str = authenticator.get_token_for_org(org_name)

        # ── API client ─────────────────────────────────────────────────────
        api_client = GitHubAPIClient(
            token=token,
            rate_limiter=RateLimiter(),
            error_handler=ErrorHandler(),
        )

        # ── Storage ────────────────────────────────────────────────────────
        storage = StorageManager(backup_path)

        # ── Domain filter ──────────────────────────────────────────────────
        only_list: list[str] | None = (
            [d.strip() for d in args.only.split(",") if d.strip()]
            if args.only
            else None
        )

        # ── Run restore ────────────────────────────────────────────────────
        exit_code: int = RestoreManager(
            api_client=api_client,
            storage_manager=storage,
            org_name=org_name,
            backup_path=backup_path,
            dry_run=args.dry_run,
            non_interactive=args.non_interactive,
            only=only_list,
        ).run()

        if exit_code == 0:
            logger.info("Restore completed successfully.")
        elif exit_code == 2:
            logger.error("Restore aborted due to unresolved conflict.")
        else:
            logger.error("Restore finished with errors.")

        return exit_code

    except Exception as exc:  # noqa: BLE001
        logging.getLogger("github_restore").error(
            "Restore failed: %s", exc, exc_info=True
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())