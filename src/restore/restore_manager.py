"""
RestoreManager — orchestrates all domain restorers for a full restore run.
"""

from __future__ import annotations

from typing import Any

from ..utils.logger import setup_logger
from .base_restorer import ConflictError
from .repository_restorer import RepositoryRestorer
from .metadata_restorer import MetadataRestorer
from .issues_prs_restorer import IssuesPRsRestorer
from .reviews_restorer import ReviewsRestorer
from .releases_restorer import ReleasesRestorer
from .workflows_restorer import WorkflowsRestorer
from .org_settings_restorer import OrgSettingsRestorer


class RestoreManager:
    """Orchestrates the full restore in dependency order.

    Usage::

        manager = RestoreManager(api_client, storage_manager, org_name,
                                 backup_path, dry_run=False,
                                 non_interactive=True, only=["repositories"])
        exit_code = manager.run()
    """

    def __init__(
        self,
        api_client: Any,
        storage_manager: Any,
        org_name: str,
        backup_path: str,
        dry_run: bool = False,
        non_interactive: bool = False,
        only: list[str] | None = None,
    ) -> None:
        """Initialise the manager.

        Args:
            api_client: Authenticated GitHub API client instance.
            storage_manager: Storage manager used to access backup artefacts.
            org_name: GitHub organisation name that is being restored.
            backup_path: Absolute path to the root of the backup snapshot.
            dry_run: When *True* no mutating API calls are made.
            non_interactive: When *True* conflicts abort immediately with
                exit code 2 without prompting the user.
            only: Optional list of domain names to restore.  When *None*
                all domains are restored.
        """
        self.api_client = api_client
        self.storage_manager = storage_manager
        self.org_name = org_name
        self.backup_path = backup_path
        self.dry_run = dry_run
        self.non_interactive = non_interactive
        self.only = only
        self.logger = setup_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> int:
        """Execute restore in order.

        Domains run in dependency order:
        1. repositories
        2. metadata
        3. issues_prs
        4. reviews
        5. releases
        6. workflows
        7. org_settings

        Each step is guarded by :meth:`_should_run`.  :class:`ConflictError`
        is caught: if *non_interactive* → log and return exit code 2.
        Otherwise the user is prompted: [s]kip / [a]bort / [c]ontinue.

        Returns:
            Exit code: ``0`` = success, ``1`` = unexpected error,
            ``2`` = conflict (non-interactive abort).
        """
        kwargs: dict[str, Any] = dict(
            api_client=self.api_client,
            storage_manager=self.storage_manager,
            org_name=self.org_name,
            backup_path=self.backup_path,
            dry_run=self.dry_run,
        )

        steps: list[tuple[str, Any]] = [
            ("repositories", RepositoryRestorer),
            ("metadata", MetadataRestorer),
            ("issues_prs", IssuesPRsRestorer),
            ("reviews", ReviewsRestorer),
            ("releases", ReleasesRestorer),
            ("workflows", WorkflowsRestorer),
            ("org_settings", OrgSettingsRestorer),
        ]

        report: dict[str, dict] = {}
        self.logger.info("Starting full restore for org '%s'.", self.org_name)

        for domain, restorer_cls in steps:
            if not self._should_run(domain):
                self.logger.debug("Skipping domain '%s' (not in --only list).", domain)
                continue

            self.logger.info("Restoring domain: %s", domain)
            restorer = restorer_cls(**kwargs)

            try:
                report[domain] = restorer.restore()
                self.logger.info("Domain '%s' complete: %s", domain, report[domain])
            except ConflictError as conflict:
                action = self._handle_conflict(conflict)
                if action == "skip":
                    self.logger.info(
                        "Skipping conflicting resource '%s' and continuing.",
                        conflict.name,
                    )
                    continue
                elif action == "abort":
                    self.logger.error(
                        "Aborting restore due to conflict: %s", conflict
                    )
                    return 2
                # "continue" — proceed to next domain
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "Unexpected error in domain '%s': %s", domain, exc, exc_info=True
                )
                return 1

        self.logger.info("Restore complete. Summary: %s", report)
        return 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _should_run(self, domain: str) -> bool:
        """Return *True* if *domain* should be executed.

        Args:
            domain: Domain name string (e.g. ``"repositories"``).

        Returns:
            ``True`` when :attr:`only` is ``None`` or *domain* is in it.
        """
        return self.only is None or domain in self.only

    def _handle_conflict(self, error: ConflictError) -> str:
        """Handle a :class:`ConflictError`.

        In non-interactive mode the conflict is logged and ``'abort'`` is
        returned immediately.  Otherwise the user is prompted interactively.

        Args:
            error: The conflict that was raised.

        Returns:
            One of ``'skip'``, ``'abort'``, or ``'continue'``.
        """
        if self.non_interactive:
            self.logger.error(
                "Conflict (non-interactive): %s '%s' already exists — aborting.",
                error.resource_type,
                error.name,
            )
            return "abort"

        print(
            f"\nConflict: {error.resource_type} '{error.name}' already exists."
        )
        while True:
            choice = input("[s]kip / [a]bort / [c]ontinue: ").strip().lower()
            if choice in ("s", "skip"):
                return "skip"
            if choice in ("a", "abort"):
                return "abort"
            if choice in ("c", "continue"):
                return "continue"
            print("Please enter 's', 'a', or 'c'.")
