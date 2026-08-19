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

"""Catalog resolver for structured harvest report message codes."""

from ckanext.dge_harvest.services.report.harvest_report_catalog_entries import (
    CatalogEntry,
    build_catalog_entry_map,
)
from ckanext.dge_harvest.services.report.harvest_report_code import (
    normalize_message_code
)
from ckanext.dge_harvest.services.report.harvest_report_text import (
    normalize_optional_text,
    normalize_preserved_text,
)

class HarvestReportCatalog(object):
    """Validated lookup for controlled report catalog entries."""

    def __init__(self, entry_map=None):
        self._entries = entry_map or build_catalog_entry_map()

    def get(self, message_code):
        """Return the catalog entry for one normalized message code.

        Args:
            message_code: Candidate LFTNN code or any value coercible to text.

        Returns:
            HarvestReportCatalogEntry | None: The registered entry or ``None``
            when the code is empty or not present in the catalog.
        """
        normalized_code = normalize_message_code(message_code)
        if normalized_code is None:
            return None
        return self._entries.get(normalized_code)

    def require(self, message_code):
        """Return the catalog entry for one normalized message code.

        Args:
            message_code: Candidate LFTNN code or any value coercible to text.

        Returns:
            HarvestReportCatalogEntry | ValueError: The registered entry or ValueError
            when the code is empty or not present in the catalog.
        """
        entry = self.get(message_code)
        if entry is None:
            raise ValueError("Unknown harvest report message_code: {}".format(message_code))
        return entry

    def resolve(self, message_code=None, level=None, display_message=None):
        """Resolve visible semantics from the catalog when possible.

        The helper allows callers to provide raw ``level`` or ``display_message``
        values during migration to the structured model. When the code exists in
        the catalog, the catalog only supplies defaults: explicit ``display_message``
        wins, while ``level`` still must agree with the code family.
        """
        normalized_level = normalize_optional_text(level)
        normalized_display_message = normalize_preserved_text(display_message)
        normalized_code = normalize_message_code(message_code)

        if normalized_code is None:
            return normalized_level, normalized_display_message

        entry = self.require(normalized_code)

        if normalized_level not in (None, entry.level):
            raise ValueError("Conflicting level for message_code {}".format(normalized_code))

        return entry.level, normalized_display_message or entry.default_message


HARVEST_REPORT_CATALOG = HarvestReportCatalog()
#HARVEST_REPORT_MESSAGE_CATALOG = HARVEST_REPORT_CATALOG._entries


def get_message_catalog_entry(message_code):
    return HARVEST_REPORT_CATALOG.get(message_code)


def resolve_catalog_message(message_code=None, level=None, display_message=None):
    return HARVEST_REPORT_CATALOG.resolve(
        message_code=message_code,
        level=level,
        display_message=display_message,
    )
