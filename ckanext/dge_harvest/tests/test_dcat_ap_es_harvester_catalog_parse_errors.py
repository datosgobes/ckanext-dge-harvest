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

"""Unit tests for catalog parse error normalization in DCAT-AP-ES harvester."""

from ckanext.dge_harvest.constants import (
    CatalogConstants,
    CommonPackageConstants,
    HarvestMessageDetailConstants,
    HarvesterConstants,
)
from ckanext.dge_harvest.harvesters.dge_dcat_ap_es_harvester import (
    DGEDCATAPESRDFHarvester,
)


class _ExplodingCatalogParser:
    def __init__(self):
        self.g = None

    def catalogs(self, catalog_dict):
        raise Exception("boom")
        yield catalog_dict


def test_parse_catalog_normalizes_unexpected_exception_format():
    harvester = DGEDCATAPESRDFHarvester()
    parser = _ExplodingCatalogParser()
    catalog_uri = "https://example.test/catalog"

    conforms, parse_errors, parse_error_details, catalog = harvester._parse_catalog(
        parser=parser,
        catalog_graph=object(),
        catalog_uri=catalog_uri,
        catalog_dict={},
    )

    assert conforms is False
    assert parse_errors == [
        HarvesterConstants.VALIDATION_UNEXPECTED_CATALOG_ERROR_MESSAGE.format(
            catalog_uri
        )
    ]
    assert parse_error_details == catalog[CommonPackageConstants.KEY_ERROR_DETAILS]
    assert catalog[CatalogConstants.KEY_CATALOG_ERRORS] == parse_errors
    assert len(catalog[CommonPackageConstants.KEY_ERROR_DETAILS]) == 1
    error_detail = catalog[CommonPackageConstants.KEY_ERROR_DETAILS][0]
    assert error_detail[HarvestMessageDetailConstants.KEY_LEVEL] == "error"
    assert error_detail[HarvestMessageDetailConstants.KEY_SCOPE] == "catalog"
    assert error_detail[HarvestMessageDetailConstants.KEY_MESSAGE] == parse_errors[0]
    assert error_detail[HarvestMessageDetailConstants.KEY_RESOURCE_URI] == catalog_uri
    assert isinstance(error_detail[HarvestMessageDetailConstants.KEY_EXCEPTION], Exception)
    assert str(error_detail[HarvestMessageDetailConstants.KEY_EXCEPTION]) == "boom"
