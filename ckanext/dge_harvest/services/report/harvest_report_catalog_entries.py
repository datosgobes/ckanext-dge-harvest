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

"""Declarative catalog entries for structured harvest report message codes."""

from ckanext.dge_harvest.services.report.harvest_report_code import (
    normalize_message_code,
    parse_message_code
)
from ckanext.dge_harvest.services.report.harvest_report_catalog_entry import (
    CatalogEntry,
    normalize_required_message
)
from ckanext.dge_harvest.services.report.harvest_report_common_classifier import COMMON_ENTRIES
from ckanext.dge_harvest.services.report.harvest_report_shacl_classifier import SHACL_ENTRIES
from ckanext.dge_harvest.services.report.harvest_report_vocabulary_classifier import VOCABULARY_ENTRIES
from ckanext.dge_harvest.services.report.harvest_report_technical_classifier import TECHNICAL_ENTRIES



CATALOG_ENTRIES = (
    COMMON_ENTRIES
    + SHACL_ENTRIES
    + VOCABULARY_ENTRIES
    + TECHNICAL_ENTRIES
)


def validate_catalog_entries(entries=CATALOG_ENTRIES):
    seen_codes = set()
    normalized_entries = []

    for catalog_entry in entries:
        parsed = parse_message_code(catalog_entry.code)
        code = parsed["code"]

        if code in seen_codes:
            raise ValueError("Duplicated harvest report catalog code: {}".format(code))

        seen_codes.add(code)
        normalized_entries.append(
            CatalogEntry(
                code=code,
                default_message=normalize_required_message(
                    code,
                    catalog_entry.default_message,
                ),
                label=catalog_entry.label,
                description=catalog_entry.description,
                requires_support_hint=catalog_entry.requires_support_hint,
            )
        )

    return tuple(normalized_entries)


def build_catalog_entry_map(entries=CATALOG_ENTRIES):
    return {
        catalog_entry.code: catalog_entry
        for catalog_entry in validate_catalog_entries(entries)
    }


def get_catalog_entry_codes(entries=CATALOG_ENTRIES):
    return sorted(
        catalog_entry.code
        for catalog_entry in validate_catalog_entries(entries)
    )


def contains_catalog_code(code, entries=CATALOG_ENTRIES):
    normalized_code = normalize_message_code(code)
    if normalized_code is None:
        return False
    return normalized_code in build_catalog_entry_map(entries)
