"""
Organisation settings collector — org info, hooks, Actions permissions, Dependabot alerts.
"""

from typing import Any, Dict, List

import requests

from .base_collector import BaseCollector


class OrgSettingsCollector(BaseCollector):
    """Collects organisation-level settings and configuration.

    Sensitive values (e.g. webhook secrets) are stripped before data is
    returned so they are never written to disk.

    Args:
        api_client:      GitHub API client instance.
        storage_manager: Storage manager instance.
        org_name:        GitHub organisation name.
    """

    def collect(self) -> Dict[str, Any]:
        """Collect organisation settings.

        Returns:
            Dict with keys:

            * ``"org_info"``              — organisation profile dict
            * ``"hooks"``                 — list of webhook dicts (secrets redacted)
            * ``"actions_permissions"``   — Actions permissions dict (empty on 403/404)
            * ``"dependabot_alerts"``     — list of Dependabot alert dicts (empty on 403/404)
        """
        self.logger.info("Collecting org settings for: %s", self.org_name)

        # ── Organisation profile ──────────────────────────────────────────
        org_info: Any = self.api_client.get(f"/orgs/{self.org_name}")

        # ── Webhooks — strip secret values ───────────────────────────────
        hooks: List[dict] = self._paginate(f"/orgs/{self.org_name}/hooks")
        for hook in hooks:
            config = hook.get("config", {})
            if "secret" in config:
                config["secret"] = "***REDACTED***"

        # ── Actions permissions — may be 403/404 for non-admin tokens ────
        actions_permissions: Dict[str, Any] = {}
        try:
            actions_permissions = self.api_client.get(
                f"/orgs/{self.org_name}/actions/permissions"
            )
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (403, 404):
                self.logger.debug(
                    "Actions permissions endpoint returned %s — skipping.", status
                )
            else:
                raise

        # ── Dependabot alerts — may be 403/404 ───────────────────────────
        dependabot_alerts: List[dict] = []
        try:
            dependabot_alerts = self._paginate(
                f"/orgs/{self.org_name}/dependabot/alerts"
            )
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (403, 404):
                self.logger.debug(
                    "Dependabot alerts endpoint returned %s — skipping.", status
                )
            else:
                raise

        return {
            "org_info": org_info,
            "hooks": hooks,
            "actions_permissions": actions_permissions,
            "dependabot_alerts": dependabot_alerts,
        }

    def validate(self, data: Any) -> bool:
        """Validate that *data* is a dict containing an ``"org_info"`` key.

        Args:
            data: Value returned by :meth:`collect`.

        Returns:
            ``True`` if *data* is a dict with a truthy ``"org_info"`` key.
        """
        return isinstance(data, dict) and bool(data.get("org_info"))
