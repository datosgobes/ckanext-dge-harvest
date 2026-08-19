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

"""Unit tests for structured NTI profile message side context."""

from ckanext.dge_harvest.profiles.dge_nti_profile import DGENTIProfile


def _build_profile_stub():
    profile = DGENTIProfile.__new__(DGENTIProfile)
    profile.catalog_errors = []
    profile.dataset_errors = []
    profile.catalog_warnings = []
    profile.dataset_warnings = []
    profile.catalog_error_details = []
    profile.dataset_error_details = []
    profile.catalog_warning_details = []
    profile.dataset_warning_details = []
    profile._current_resource_uri = "https://example.test/resource/1"
    return profile


def test_add_errormsg_keeps_parallel_dataset_detail():
    profile = _build_profile_stub()

    profile._add_errormsg("Falta título", isCatalog=False, prefix="Distribución")

    assert profile.dataset_errors == ["[Distribución]Falta título"]
    assert profile.dataset_error_details == [
        {
            "level": "error",
            "scope": "dataset",
            "message": "[Distribución]Falta título",
            "resource_uri": "https://example.test/resource/1",
            "prefix": "Distribución",
        }
    ]


def test_add_warningmsg_keeps_parallel_catalog_detail():
    profile = _build_profile_stub()

    profile._add_warningmsg("Idioma no soportado", isCatalog=True)

    assert profile.catalog_warnings == ["Idioma no soportado"]
    assert profile.catalog_warning_details == [
        {
            "level": "warning",
            "scope": "catalog",
            "message": "Idioma no soportado",
            "resource_uri": "https://example.test/resource/1",
        }
    ]


def test_add_errormsg_accepts_explicit_resource_uri():
    profile = _build_profile_stub()
    profile._current_message_scope = "dataset"

    profile._add_errormsg(
        "Formato no soportado",
        prefix="Distribución",
        resource_uri="https://example.test/distribution/9",
        scope="distribution",
    )

    assert profile.dataset_error_details == [
        {
            "level": "error",
            "scope": "distribution",
            "message": "[Distribución]Formato no soportado",
            "resource_uri": "https://example.test/distribution/9",
            "prefix": "Distribución",
        }
    ]
