from dataclasses import dataclass


@dataclass
class ConfigEntry:
    domain: str
    key: str
    value: str
    editable: bool
