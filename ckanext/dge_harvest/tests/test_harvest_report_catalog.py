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

import pytest

from ckanext.dge_harvest.services.report.harvest_report_catalog import (
    HARVEST_REPORT_CATALOG,
    HarvestReportCatalog,
    get_message_catalog_entry,
    resolve_catalog_message,
)
from ckanext.dge_harvest.services.report.harvest_report_catalog_entries import (
    build_catalog_entry_map,
    contains_catalog_code,
    get_catalog_entry_codes,
)
from ckanext.dge_harvest.services.report.harvest_report_catalog_entry import (
    CatalogEntry,
)



@pytest.fixture
def custom_catalog():
    return HarvestReportCatalog(
        entry_map={
            "E4201": CatalogEntry(
                code="E4201",
                default_message="Mensaje visible catalogado",
                label="Etiqueta",
                description="Descripcion",
            )
        }
    )


def test_catalog_get_returns_registered_entry(custom_catalog):
    entry = custom_catalog.get(" E4201 ")

    assert entry == CatalogEntry(
        code="E4201",
        default_message="Mensaje visible catalogado",
        label="Etiqueta",
        description="Descripcion",
    )


def test_resolve_catalog_message_fills_missing_values(monkeypatch):
    monkeypatch.setattr(
        "ckanext.dge_harvest.services.report.harvest_report_catalog.HARVEST_REPORT_CATALOG",
        HarvestReportCatalog(
            entry_map={
                "E4201": CatalogEntry(
                    code="E4201",
                    default_message="Mensaje visible catalogado",
                )
            }
        ),
    )

    level, display_message = resolve_catalog_message(message_code="E4201")

    assert level == "error"
    assert display_message == "Mensaje visible catalogado"


def test_catalog_resolve_rejects_conflicting_level(custom_catalog):
    with pytest.raises(ValueError):
        custom_catalog.resolve(
            message_code="E4201",
            level="warning",
        )


def test_catalog_resolve_keeps_explicit_display_message(custom_catalog):
    level, display_message = custom_catalog.resolve(
        message_code="E4201",
        display_message="Mensaje visible adaptado",
    )

    assert level == "error"
    assert display_message == "Mensaje visible adaptado"


def test_catalog_entry_map_contains_expected_codes():
    entry_map = build_catalog_entry_map()

    assert "E4201" in entry_map
    assert "W4201" in entry_map
    assert "E4302" in entry_map
    assert "E1501" in entry_map
    assert HARVEST_REPORT_CATALOG.get("E4201").level == "error"
    assert HARVEST_REPORT_CATALOG.get("W4201").level == "warning"


def test_catalog_entry_code_helpers_use_current_catalog():
    codes = get_catalog_entry_codes()

    assert "E4201" in codes
    assert contains_catalog_code(" E4201 ") is True
    assert contains_catalog_code("invalid") is False


def test_get_message_catalog_entry_uses_global_catalog():
    entry = get_message_catalog_entry("E4201")

    assert entry is not None
    assert entry.code == "E4201"


def test_catalog_entry_map_preserves_requires_support_hint():
    entry = get_message_catalog_entry("E4501")

    assert entry is not None
    assert entry.requires_support_hint is True
