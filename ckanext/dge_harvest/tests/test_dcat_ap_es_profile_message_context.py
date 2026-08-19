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

"""Unit tests for structured DCAT-AP-ES profile message side context."""

from ckanext.dge_harvest.constants.constants import CommonPackageConstants
from ckanext.dge_harvest.profiles.dge_dcat_ap_es_profile import DGEDCATAPESProfile


def _build_profile_stub():
    profile = DGEDCATAPESProfile.__new__(DGEDCATAPESProfile)
    profile._current_resource_uri = "https://example.test/resource/1"
    return profile


def test_add_structured_message_keeps_parallel_dataset_detail():
    profile = _build_profile_stub()
    dataset_dict = {
        "errors": [],
        CommonPackageConstants.KEY_ERROR_DETAILS: [],
    }

    profile._add_structured_message(
        data_dict=dataset_dict,
        message_key="errors",
        detail_key=CommonPackageConstants.KEY_ERROR_DETAILS,
        message="Falta titulo",
        level="error",
        scope="dataset",
        prefix="Distribucion",
    )

    assert dataset_dict["errors"] == ["[Distribucion] Falta titulo"]
    assert dataset_dict[CommonPackageConstants.KEY_ERROR_DETAILS] == [
        {
            "level": "error",
            "scope": "dataset",
            "message": "[Distribucion] Falta titulo",
            "resource_uri": "https://example.test/resource/1",
            "prefix": "Distribucion",
        }
    ]


def test_initialize_message_detail_lists_creates_missing_keys():
    profile = _build_profile_stub()
    dataset_dict = {}

    profile._initialize_message_detail_lists(dataset_dict)

    assert dataset_dict == {
        CommonPackageConstants.KEY_ERROR_DETAILS: [],
        CommonPackageConstants.KEY_WARNING_DETAILS: [],
    }
