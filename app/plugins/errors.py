"""Plugin Hub domain errors (Part 14)."""
from __future__ import annotations

from app.models.errors import NexaError


class PluginError(NexaError):
    default_message = "Plugin error."


class PluginNotFoundError(PluginError):
    default_message = "Plugin not found."

    def __init__(self, plugin_id: str) -> None:
        super().__init__(f"Unknown plugin '{plugin_id}'.")
        self.plugin_id = plugin_id


class PluginPermissionDeniedError(PluginError):
    default_message = "Plugin permission is not granted."

    def __init__(self, plugin_id: str, permission: str) -> None:
        super().__init__(
            f"Plugin '{plugin_id}' requires permission '{permission}' which is not granted."
        )
        self.plugin_id = plugin_id
        self.permission = permission


class PluginNotConnectedError(PluginError):
    default_message = "Plugin is not connected."

    def __init__(self, plugin_id: str) -> None:
        super().__init__(f"Plugin '{plugin_id}' is not connected.")
        self.plugin_id = plugin_id


class PluginConfirmationRequiredError(PluginError):
    default_message = "This action requires explicit confirmation."

    def __init__(self, plugin_id: str, action: str) -> None:
        super().__init__(
            f"Plugin '{plugin_id}' action '{action}' requires confirm=true."
        )
        self.plugin_id = plugin_id
        self.action = action


class PluginUnavailableError(PluginError):
    default_message = "Plugin is not available."


class PluginTimeoutError(PluginError):
    default_message = "Plugin action timed out."


class PluginValidationError(PluginError):
    default_message = "Invalid plugin input."
