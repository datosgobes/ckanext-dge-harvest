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

"""Unit tests for dataset and dataservice structured parse error returns."""

from ckanext.dge_harvest.constants import (
    CommonPackageConstants,
    DatasetConstants,
    DataserviceConstants,
    HarvestMessageDetailConstants,
    HarvesterConstants,
)
from ckanext.dge_harvest.harvesters.dge_dcat_ap_es_harvester import (
    DGEDCATAPESRDFHarvester,
)


class _ExplodingDatasetParser:
    def __init__(self):
        self.g = None

    def datasets(self, dataset_dict):
        raise Exception("dataset boom")
        yield dataset_dict


class _ExplodingDataserviceParser:
    def __init__(self):
        self.g = None

    def dataservices(self, dataservice_dict):
        raise Exception("dataservice boom")
        yield dataservice_dict


def test_parse_dataset_returns_structured_error_details():
    harvester = DGEDCATAPESRDFHarvester()
    parser = _ExplodingDatasetParser()
    dataset_uri = "https://example.test/dataset/1"

    conforms, parse_errors, parse_error_details, dataset, dataset_guid = harvester._parse_dataset(
        parser=parser,
        dataset_graph=object(),
        dataset_uri=dataset_uri,
        dataset_dict={},
        owner_org_id="org-1",
    )

    assert conforms is False
    assert dataset_guid is None
    assert parse_errors == [
        HarvesterConstants.VALIDATION_UNEXPECTED_DATASET_ERROR_MESSAGE.format(
            dataset_uri
        )
    ]
    assert parse_error_details == dataset[CommonPackageConstants.KEY_ERROR_DETAILS]
    assert dataset[DatasetConstants.KEY_ERRORS] == parse_errors
    error_detail = parse_error_details[0]
    assert error_detail[HarvestMessageDetailConstants.KEY_SCOPE] == "dataset"
    assert error_detail[HarvestMessageDetailConstants.KEY_MESSAGE] == parse_errors[0]
    assert error_detail[HarvestMessageDetailConstants.KEY_RESOURCE_URI] == dataset_uri
    assert str(error_detail[HarvestMessageDetailConstants.KEY_EXCEPTION]) == "dataset boom"


def test_parse_dataservice_returns_structured_error_details():
    harvester = DGEDCATAPESRDFHarvester()
    parser = _ExplodingDataserviceParser()
    dataservice_uri = "https://example.test/dataservice/1"

    conforms, parse_errors, parse_error_details, dataservice, dataservice_guid = harvester._parse_dataservice(
        parser=parser,
        dataservice_graph=object(),
        dataservice_uri=dataservice_uri,
        dataservice_dict={},
        owner_org_id="org-1",
    )

    assert conforms is False
    assert dataservice_guid is None
    assert parse_errors == [
        HarvesterConstants.VALIDATION_UNEXPECTED_DATASERVICE_ERROR_MESSAGE.format(
            dataservice_uri
        )
    ]
    assert parse_error_details == dataservice[CommonPackageConstants.KEY_ERROR_DETAILS]
    assert dataservice[DataserviceConstants.KEY_ERRORS] == parse_errors
    error_detail = parse_error_details[0]
    assert error_detail[HarvestMessageDetailConstants.KEY_SCOPE] == "dataservice"
    assert error_detail[HarvestMessageDetailConstants.KEY_MESSAGE] == parse_errors[0]
    assert error_detail[HarvestMessageDetailConstants.KEY_RESOURCE_URI] == dataservice_uri
    assert str(error_detail[HarvestMessageDetailConstants.KEY_EXCEPTION]) == "dataservice boom"
