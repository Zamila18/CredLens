"""The connector contract: what every data source must provide to bring evidence into CredLens.

Purpose: one shape for every source, so a new provider is a new connector class and a
    mapping, never a change to the merchant, evidence or scoring code.
Owner role: D (full-stack).
Implements: product reassessment, workstream C (source registry and connector framework).

A connector describes itself (category, the kinds of records it carries, how it
authenticates, what settings it needs) and does three things against a connection:
`test` (can we reach it with these settings?), `discover` (which fields does it send?) and
`fetch` (the rows, as the source sends them). Everything after that is shared and lives in
src/connectors/service.py: field mapping, normalisation, merchant matching, validation,
duplicate handling, saving with provenance and lineage, and the sync history.

A connector raises `ConnectorError(code, message)` for anything that goes wrong; the
service records it on the run and saves nothing from that run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Availability = Literal["builtin", "available", "planned"]
Auth = Literal["none", "api_key", "oauth2"]


class ConnectorError(Exception):
    """A connector could not do what was asked. `code` is for the screen's wording."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class SettingField:
    """One setting a connection needs. A `secret_ref` names where a credential is kept."""

    key: str
    label: str
    label_bn: str
    kind: Literal["text", "choice", "secret_ref"]
    required: bool = False
    choices: tuple[str, ...] = ()
    help: str = ""
    help_bn: str = ""


@dataclass(frozen=True)
class FetchContext:
    """What a connector may know about the deployment when it reads (never another org)."""

    organization_id: str
    calendar_end: str  # the business calendar's last day (ISO date)
    secret: str | None = None  # the credential, read from where `secret_ref` points


@dataclass
class Connector:
    """Describes a source. Subclasses implement test, discover and fetch."""

    key: str
    name: str
    name_bn: str
    category: str
    description: str
    description_bn: str
    record_kinds: tuple[str, ...]
    auth: Auth = "none"
    availability: Availability = "planned"
    sandbox_only: bool = False
    settings: tuple[SettingField, ...] = field(default_factory=tuple)
    example: str | None = None  # an example of who provides this kind of source; no partnership

    def test(self, settings: dict[str, Any], context: FetchContext) -> None:
        raise ConnectorError("not_available", f"{self.name} cannot be connected in this build.")

    def discover(self, settings: dict[str, Any], context: FetchContext) -> list[str]:
        raise ConnectorError("not_available", f"{self.name} cannot be connected in this build.")

    def fetch(self, settings: dict[str, Any], context: FetchContext) -> list[dict[str, Any]]:
        raise ConnectorError("not_available", f"{self.name} cannot be connected in this build.")

    def describe(self) -> dict[str, Any]:
        """What the API sends about this connector (no behaviour, no secrets)."""
        return {
            "key": self.key,
            "name": self.name,
            "name_bn": self.name_bn,
            "category": self.category,
            "description": self.description,
            "description_bn": self.description_bn,
            "record_kinds": list(self.record_kinds),
            "auth": self.auth,
            "availability": self.availability,
            "sandbox_only": self.sandbox_only,
            "example": self.example,
            "settings": [
                {
                    "key": f.key,
                    "label": f.label,
                    "label_bn": f.label_bn,
                    "kind": f.kind,
                    "required": f.required,
                    "choices": list(f.choices),
                    "help": f.help,
                    "help_bn": f.help_bn,
                }
                for f in self.settings
            ],
        }
