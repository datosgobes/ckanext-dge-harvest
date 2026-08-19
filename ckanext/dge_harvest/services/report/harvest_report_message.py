# Copyright (C) 2026 Entidad Pública Empresarial Red.es
#
# This file is part of "dge-harvest (datos.gob.es)".
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Common in-memory message contract for the harvest report.

This module validates the normalized message structure before persistence so
adapters and harvesters share the same vocabulary and sanitization rules.
"""

from dataclasses import dataclass
from typing import Optional

from ckanext.dge_harvest.services.report.harvest_report_code import parse_message_code
from ckanext.dge_harvest.services.report.harvest_report_dimensions import (
    REPORT_ALLOWED_PHASES,
)
from ckanext.dge_harvest.services.report.harvest_report_severity import (
    MESSAGE_ALLOWED_LEVELS,
)
from ckanext.dge_harvest.services.report.harvest_report_text import (
    normalize_preserved_text,
    normalize_optional_text,
    normalize_required_text
)


@dataclass(frozen=True)
class HarvestReportMessage(object):
    """Validated structured message contract for the harvest report."""

    level: str
    phase: str
    origin: str
    category: str
    display_message: Optional[str] = None
    message_code: Optional[str] = None
    context: Optional[dict] = None

    def __post_init__(self):
        """Normalize and validate the contract fields after construction."""
        object.__setattr__(self, "message_code", normalize_optional_text(self.message_code))
        parsed_code = parse_message_code(self.message_code)
        object.__setattr__(self, "level", normalize_required_text("level", self.level))
        object.__setattr__(self, "phase", normalize_required_text("phase", self.phase))
        object.__setattr__(self, "origin", normalize_required_text("origin", self.origin))
        object.__setattr__(self, "category",normalize_required_text("category", self.category))
        object.__setattr__(self, "display_message", normalize_preserved_text(self.display_message))
        object.__setattr__(self, "context", _normalize_context(self.context))

        if parsed_code is not None:
            if self.level != parsed_code["level"]:
                raise ValueError(
                    "level does not match message_code {} (message level = {},  parsed level ={})".format(self.message_code, self.level, parsed_code["level"])
                )
            if self.phase != parsed_code["phase"]:
                raise ValueError(
                    "phase does not match message_code {} (message phase = {},  parsed phase ={})".format(self.message_code, self.phase, parsed_code["phase"])
                )
            if self.category != parsed_code["category"]:
                raise ValueError(
                    "category does not match message_code {} (message category = {},  parsed category ={})".format(self.message_code, self.category, parsed_code["category"])
                )

        if self.level not in MESSAGE_ALLOWED_LEVELS:
            raise ValueError("level must be one of {}. Current level: {}".format(MESSAGE_ALLOWED_LEVELS, self.level))

        if self.phase not in REPORT_ALLOWED_PHASES:
            raise ValueError("phase must be one of {}. Current phase {}.".format(REPORT_ALLOWED_PHASES, self.phase))

    def as_dict(self):
        """Return the normalized common fields as a plain dictionary."""
        result = {
            "level": self.level,
            "phase": self.phase,
            "origin": self.origin,
            "category": self.category,
            "message_code": self.message_code,
            "display_message": self.display_message
        }
        if self.context is not None:
            result["context"] = self.context
        return result


def _normalize_context(value):
    """Normalize optional structured context for stable serialization."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("context must be a dict")
    normalized = {}
    for key, item in value.items():
        normalized[str(key)] = item
    return normalized or None
