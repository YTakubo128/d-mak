"""SwitchBot API v1.1 callable command catalog.

This module provides a centralized list of callable commands per device type.
It currently includes practical definitions for devices used in this project,
with a focus on Bot and Ceiling Light.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


API_BASE_URL = "https://api.switch-bot.com/v1.1"


@dataclass(frozen=True)
class ApiCommand:
    """Definition of a callable command for a device type."""

    command: str
    parameter_format: str
    description: str
    command_type: str = "command"

    def to_request_body(self, parameter: str = "default") -> dict:
        """Build POST /devices/{deviceId}/commands request payload."""
        return {
            "command": self.command,
            "parameter": parameter,
            "commandType": self.command_type,
        }


# Device type names follow SwitchBot API documentation labels.
CALLABLE_API_LIST: Dict[str, List[ApiCommand]] = {
    "Bot": [
        ApiCommand("turnOn", "default", "Set to ON state"),
        ApiCommand("turnOff", "default", "Set to OFF state"),
        ApiCommand("press", "default", "Trigger press action"),
    ],
    "Ceiling Light": [
        ApiCommand("turnOn", "default", "Set to ON state"),
        ApiCommand("turnOff", "default", "Set to OFF state"),
        ApiCommand("toggle", "default", "Toggle ON/OFF state"),
        ApiCommand("setBrightness", "1-100", "Set brightness"),
        ApiCommand("setColorTemperature", "2700-6500", "Set color temperature"),
    ],
    "Ceiling Light Pro": [
        ApiCommand("turnOn", "default", "Set to ON state"),
        ApiCommand("turnOff", "default", "Set to OFF state"),
        ApiCommand("toggle", "default", "Toggle ON/OFF state"),
        ApiCommand("setBrightness", "1-100", "Set brightness"),
        ApiCommand("setColorTemperature", "2700-6500", "Set color temperature"),
    ],
}


def get_supported_device_types() -> List[str]:
    """Return all device types defined in this API list."""
    return sorted(CALLABLE_API_LIST.keys())


def get_callable_commands(device_type: str) -> List[ApiCommand]:
    """Return callable command list for the given device type."""
    return list(CALLABLE_API_LIST.get(device_type, []))


def get_command(device_type: str, command_name: str) -> Optional[ApiCommand]:
    """Return a command definition by device type and command name."""
    for command in CALLABLE_API_LIST.get(device_type, []):
        if command.command == command_name:
            return command
    return None


def build_command_request(
    device_type: str,
    command_name: str,
    parameter: str = "default",
) -> dict:
    """Build command request body with basic validation.

    Raises:
        ValueError: If device type or command is unsupported.
    """
    command = get_command(device_type, command_name)
    if command is None:
        raise ValueError(
            f"Unsupported command '{command_name}' for device type '{device_type}'"
        )
    return command.to_request_body(parameter)
