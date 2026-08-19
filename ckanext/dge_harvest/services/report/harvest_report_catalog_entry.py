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

"""Base entry helpers for structured harvest report message codes.

This module owns the immutable catalog entry model and the helper used to
normalize declarative entries before they are assembled into classifier
catalogs. It stays dependency-light so classifiers can import it without
creating circular references through the aggregate catalog module.
"""

from dataclasses import dataclass
from typing import Optional

from ckanext.dge_harvest.services.report.harvest_report_code import (
    parse_message_code,
)
from ckanext.dge_harvest.services.report.harvest_report_text import (
    normalize_optional_text,
)

@dataclass(frozen=True)
class CatalogEntry(object):
    """Declarative entry for one controlled harvest report code."""

    code: str
    default_message: str
    label: Optional[str] = None
    description: Optional[str] = None
    requires_support_hint: bool = False

    @property
    def parsed(self):
        return parse_message_code(self.code)

    @property
    def level(self):
        return self.parsed["level"]

    @property
    def phase(self):
        return self.parsed["phase"]

    @property
    def category(self):
        return self.parsed["category"]


def normalize_required_message(code, value):
    normalized = normalize_optional_text(value)
    if normalized is None:
        raise ValueError("Catalog entry {} requires a default_message".format(code))
    return normalized




def entry(code, default_message, label=None, description=None, requires_support_hint=False):
    parsed = parse_message_code(code)
    return CatalogEntry(
        code=parsed["code"],
        default_message=normalize_required_message(parsed["code"], default_message),
        label=normalize_optional_text(label),
        description=normalize_optional_text(description),
        requires_support_hint=bool(requires_support_hint),
    )
