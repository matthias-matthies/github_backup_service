"""OrgSettingsRestorer — restores organisation-level hooks and Actions permissions."""

from __future__ import annotations

from typing import Any

import requests

from .base_restorer import BaseRestorer


class OrgSettingsRestorer(BaseRestorer):
    """Restores organisation-level settings from backup."""

    def restore(self) -> dict:
        """Run restore_hooks() then restore_actions_permissions().

        Returns:
            ``{"hooks_created": N, "actions_permissions_restored": bool}``
        """
        summary: dict[str, Any] = {
            "hooks_created": 0,
            "actions_permissions_restored": False,
        }

        try:
            summary["hooks_created"] = self.restore_hooks()
        except Exception as exc:  # noqa: BLE001
            self.logger.error("restore_hooks failed: %s", exc)

        try:
            summary["actions_permissions_restored"] = self.restore_actions_permissions()
        except Exception as exc:  # noqa: BLE001
            self.logger.error("restore_actions_permissions failed: %s", exc)

        return summary

    def restore_hooks(self) -> int:
        """Restore organisation webhooks from org_settings.json.

        Secrets are stripped because they were redacted at backup time.  After
        restoring, a WARNING is logged listing every hook URL so the operator
        knows which hooks need their secrets re-added manually.

        Returns:
            Number of hooks created.
        """
        settings = self.load_json("org_settings.json")
        hooks: list[dict] = settings.get("hooks", [])
        created = 0
        restored_urls: list[str] = []

        for hook in hooks:
            config: dict = dict(hook.get("config", {}))
            # Remove the secret — it was redacted at backup time.
            config.pop("secret", None)

            payload: dict[str, Any] = {
                "name": hook.get("name", "web"),
                "config": {
                    "url": config.get("url", ""),
                    "content_type": config.get("content_type", "json"),
                },
                "events": hook.get("events", ["push"]),
                "active": hook.get("active", True),
            }

            hook_url: str = config.get("url", "<unknown>")

            try:
                if self.dry_run:
                    self.logger.info(
                        "[dry-run] Would create org hook: %s", hook_url
                    )
                    created += 1
                    restored_urls.append(hook_url)
                    continue

                self.api_client.post(f"/orgs/{self.org_name}/hooks", payload)
                self.logger.debug("Created org hook: %s", hook_url)
                created += 1
                restored_urls.append(hook_url)

            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "Failed to create org hook '%s': %s", hook_url, exc
                )

        if restored_urls:
            self.logger.warning(
                "The following org hooks were restored WITHOUT secrets "
                "(secrets must be re-added manually): %s",
                ", ".join(restored_urls),
            )

        return created

    def restore_actions_permissions(self) -> bool:
        """Restore organisation-level Actions permissions from org_settings.json.

        If the ``actions_permissions`` key is non-empty, a PUT request is made
        to ``/orgs/{org}/actions/permissions``.  403 responses (insufficient
        permissions) are caught and logged as a warning.

        Returns:
            ``True`` if permissions were successfully applied, ``False`` otherwise.
        """
        settings = self.load_json("org_settings.json")
        permissions: dict = settings.get("actions_permissions", {})

        if not permissions:
            self.logger.debug(
                "No actions_permissions data in backup, skipping."
            )
            return False

        if self.dry_run:
            self.logger.info(
                "[dry-run] Would restore Actions permissions for '%s'.",
                self.org_name,
            )
            return True

        try:
            self.api_client.put(
                f"/orgs/{self.org_name}/actions/permissions", permissions
            )
            self.logger.debug(
                "Restored Actions permissions for '%s'.", self.org_name
            )
            return True
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 403:
                self.logger.warning(
                    "No permission to restore Actions permissions for '%s': %s",
                    self.org_name,
                    exc,
                )
            else:
                self.logger.error(
                    "Failed to restore Actions permissions for '%s': %s",
                    self.org_name,
                    exc,
                )
            return False
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "Failed to restore Actions permissions for '%s': %s",
                self.org_name,
                exc,
            )
            return False
