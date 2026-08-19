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

"""Unit tests for structured parse error extraction in DCAT-AP-ES harvester."""

from ckanext.dge_harvest.constants import (
    CommonPackageConstants,
    HarvestMessageDetailConstants,
)
from ckanext.dge_harvest.harvesters.dge_dcat_ap_es_harvester import (
    DGEDCATAPESRDFHarvester,
)


def test_extract_parse_errors_prefers_structured_detail_messages():
    harvester = DGEDCATAPESRDFHarvester()

    entity_dict = {
        "errors": ["plain fallback"],
        CommonPackageConstants.KEY_ERROR_DETAILS: [
            {
                HarvestMessageDetailConstants.KEY_MESSAGE: "detalle 1",
                HarvestMessageDetailConstants.KEY_RESOURCE_URI: "https://example.test/dataset/1",
            },
            {
                HarvestMessageDetailConstants.KEY_MESSAGE: "detalle 2",
            },
        ],
    }

    result = harvester._extract_parse_errors(entity_dict, "errors")

    assert result == ["detalle 1", "detalle 2"]


def test_extract_parse_errors_falls_back_to_plain_errors():
    harvester = DGEDCATAPESRDFHarvester()

    entity_dict = {"errors": ["plain 1", "plain 2"]}

    result = harvester._extract_parse_errors(entity_dict, "errors")

    assert result == ["plain 1", "plain 2"]
