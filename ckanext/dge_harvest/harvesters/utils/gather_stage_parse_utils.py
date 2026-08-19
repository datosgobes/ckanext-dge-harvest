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

import logging
import json
from functools import partial
from typing import List, Callable
from rdflib import Graph
from ckanext.harvest.model import (HarvestJob, HarvestObject)
from ckanext.harvest.model import HarvestObject, HarvestJob, HarvestObjectExtra

from ckanext.dge_harvest.constants import (DCATAPESDatasetConstants as DatasetConstants,
                          DCATAPESDistributionConstants as DistributionConstants,
                          DCATAPESDataserviceConstants as DataserviceConstants,
                          HarvestMessageDetailConstants,
                          HarvestObjectExtraKeyConstants as HOEKeyConstants, 
                          CommonPackageConstants as PackageConstants)
from ckanext.dge_harvest.utils import check_hvd_entity, generate_graph_uri_from_job, get_value_of_an_extras_key_from_dict
from ckanext.dge_harvest.decorators import log_debug, log_info
from ckanext.dge_harvest.services.report.harvest_report_dimensions import (
    REPORT_PHASE_VALIDATION
)
from ckanext.dge_harvest.harvesters.dge_harvester_exceptions import (
    GatherResourceMissingNameError,
    GatherResourceMissingIdentifierError
)
from ckanext.dge_harvest.services.report.harvest_report_common_classifier import (
    get_common_error_message_code,
    VALIDATION_REASON_INVALID_PARSE_DATASERVICE,
    VALIDATION_REASON_INVALID_PARSE_DATASET
)
log = logging.getLogger(__name__)


def _get_detail_by_index(details, index):
    """Return aligned structured detail entry for one flat parse message."""
    if not details:
        return None
    if index < 0 or index >= len(details):
        return None
    return details[index]

@log_debug
def add_extras_keys_to_dict(data_dict:dict[str, object], data_guid:str, data_graph:Graph, ckan_uri:str, source_uri):
    """
    Add the following extras keys to a dictionary: guid, hvd, application_profile, ckan_uri
    
    :param data_dict: dictionary to add extras
    :type data_dict: dict[str, object]
    
    :param data_guid: guid to add
    :type data_guid: str
    
    :param data_graph: graph with all data
    :type data_graph: Graph
    
    :param ckan_uri: ckan uri
    :type ckan_uri: str

    :param source_uri: uri in RDF source
    :type source_uri: str
    """
    data_dict.setdefault(PackageConstants.KEY_EXTRAS, [])
    data_dict[PackageConstants.KEY_EXTRAS].append({'key': PackageConstants.KEY_EXTRAS_GUID, 'value': data_guid})
    data_dict[PackageConstants.KEY_EXTRAS].append({'key': PackageConstants.KEY_EXTRAS_HVD, 'value': check_hvd_entity(data_graph, source_uri)})
    data_dict[PackageConstants.KEY_EXTRAS].append({'key': PackageConstants.KEY_EXTRAS_APPLICATION_PROFILE, 'value': PackageConstants.KEY_EXTRAS_APPLICATION_PROFILE_DCAT_AP_ES_100_VALUE})
    data_dict[PackageConstants.KEY_EXTRAS].append({'key': PackageConstants.KEY_EXTRAS_CKAN_URI, 'value': ckan_uri})
    data_dict[PackageConstants.KEY_EXTRAS].append({'key': PackageConstants.KEY_EXTRAS_SOURCE_URI, 'value': source_uri})

@log_debug
def process_dataservice_after_parse(dataservice_uri:str, 
                                    dataservice_dict:dict[str, object], 
                                    dataservice_guid:str, conforms:bool, 
                                    error_messages:List[str], 
                                    error_details:List[dict[str, object]],
                                    harvest_job: HarvestJob, 
                                    harvester_type: str, 
                                    object_ids: List[str], 
                                    uri_ho_dict:dict[str, str], 
                                    uri_dataset_ho_id_dict:dict[str, List[str]],
                                    save_structured_object_error_method:Callable):
    """
    Process dataservice after parse process: 
        - create the harvest object
        - create the harvest object errors
        - add harvest_object_id to the list that contains all created harvest objects ids 
        - add guid to guids to the list that contains the guids of all created harvest objects ids 
        - update the diccionary used to relate dataservice_uri with its entity_harves_object_id
        - update the dictionary used to relate the dataset_uri served by this dataservice with the dataservice harvest object id
    
    :param dataservice_uri: dataservice uri
    :type dataservice_uri: str
    
    :param dataservice_dict: dictionary with dataservice data
    :type dataservice_dict: dict[str, object]
    
    :param dataservice_guid: dataservice guid
    :type dataservice_guid: str
    
    :param harvester_type: harvester type
    :type harvester_type: str
    
    :param conforms: True in parse is right, False in other case
    :type conforms: bool
    
    :param error_messages: dataservice parse errores
    :type error_messages: List[str]

    :param error_details: dataservice structured parse errors
    :type error_details: List[dict[str, object]]
    
    :param harvest_job: Harvest job
    :type harvest_job: HarvestJob
    
    :param object_ids: List of havest objects id of harvest job
    :type object_ids: List[str]

    :param uri_ho_dict: Dictionary than contains the relation between dataset_uri and its harvest object id
    :type uri_ho_dict: dict[str, str]
    
    :param uri_dataset_ho_id_dict: Dictionary that contais the relation between dataset_uri and the dataservice harvest object id that serves the dataset
    :type uri_dataset_ho_id_dict: dict[str, List[str]]
    """
    if not dataservice_dict.get(DatasetConstants.KEY_NAME, None):
        log.error(f'Could not get a name for dataservice: {dataservice_dict}')
        raise GatherResourceMissingNameError()
    if not dataservice_guid:
        log.error(f'Could not get a unique identifier for dataservice: {dataservice_dict}')
        raise GatherResourceMissingIdentifierError()
    # clean dictionary
    del dataservice_dict[DataserviceConstants.KEY_ERRORS]
    del dataservice_dict[DataserviceConstants.KEY_WARNINGS]
    dataservice_dict.pop(PackageConstants.KEY_ERROR_DETAILS, None)
    dataservice_dict.pop(PackageConstants.KEY_WARNING_DETAILS, None)
    # create Harvest Object
    obj = HarvestObject(guid=dataservice_guid, job=harvest_job, content=json.dumps(dataservice_dict),
                        extras=[HarvestObjectExtra(key=HOEKeyConstants.HOE_PACKAGE_TYPE_KEY, value=HOEKeyConstants.HOE_PACKAGE_TYPE_DATASERVICE_VALUE),
                                HarvestObjectExtra(key=HOEKeyConstants.HOE_GRAPH_NAME_KEY, value=generate_graph_uri_from_job(harvest_job)), 
                                HarvestObjectExtra(key=HOEKeyConstants.HOE_SOURCE_URI_KEY, value=dataservice_uri),
                                HarvestObjectExtra(key=HOEKeyConstants.HOE_CKAN_URI_KEY, value=get_value_of_an_extras_key_from_dict(dataservice_dict, PackageConstants.KEY_EXTRAS_CKAN_URI)),
                                HarvestObjectExtra(key=HOEKeyConstants.HOE_CKAN_NAME_KEY, value=dataservice_dict.get(PackageConstants.KEY_NAME, None)),
                                HarvestObjectExtra(key=HOEKeyConstants.HOE_HARVESTER_TYPE, value=harvester_type)])
    if not conforms:
        obj.state = 'ERROR'
    obj.save()
    # Create error messages
    entity_type = "dataservice"
    phase = REPORT_PHASE_VALIDATION
    reason = VALIDATION_REASON_INVALID_PARSE_DATASERVICE 
    for index, message in enumerate(error_messages or []):
        #_save_object_error(message, obj, 'Gather')
        error_detail = _get_detail_by_index(error_details, index)
        error_entity_type = (error_detail or {}).get(HarvestMessageDetailConstants.KEY_SCOPE) or entity_type
        save_structured_object_error_method(
            exception = (error_detail or {}).get(HarvestMessageDetailConstants.KEY_EXCEPTION),
            harvest_object=obj,
            raw_message=(error_detail or {}).get(HarvestMessageDetailConstants.KEY_MESSAGE) or message, 
            display_message = (error_detail or {}).get(HarvestMessageDetailConstants.KEY_MESSAGE) or message,
            phase=phase,
            kind=f"parse_{error_entity_type}",
            reason=reason,
            resource_uri=(error_detail or {}).get(HarvestMessageDetailConstants.KEY_RESOURCE_URI) or dataservice_uri,
            message_code=get_common_error_message_code(phase=phase, reason=reason),
            payload={"entity_type": error_entity_type},
        )

    if not conforms:
        return False
    # Append id to list
    object_ids.append(obj.id)
    # Add uri-guid to dict 
    if (dataservice_uri 
        and uri_ho_dict.get(dataservice_uri) is None):
        uri_ho_dict[dataservice_uri] = obj.id
    # datasets that are served by the dataservice
    if dataservice_dict.get(DataserviceConstants.KEY_DATASERVICE_SERVES_DATASET) is not None:
        for dataset_href in dataservice_dict.get(DataserviceConstants.KEY_DATASERVICE_SERVES_DATASET, []):
            if uri_dataset_ho_id_dict.get(dataset_href) is None:
                uri_dataset_ho_id_dict[dataset_href] = [obj.id]
            else:                                            
                uri_dataset_ho_id_dict[dataset_href].append(obj.id)
    else:
        log.debug(f'{dataservice_uri} dataservice does not serve any dataset')
    return True

@log_debug
def process_dataset_after_parse(dataset_uri:str, 
                                dataset_dict:dict[str, object], 
                                dataset_guid:str, 
                                harvester_type:str, 
                                conforms:bool, 
                                error_messages:List[str], 
                                error_details:List[dict[str, object]],
                                harvest_job: HarvestJob, 
                                object_ids: List[str], 
                                uri_ho_dict:dict[str, str], 
                                uri_dataset_ho_id_dict:dict[str, List[str]],
                                save_structured_object_error_method:Callable):
    """
    Process dataservice after parse process: 
        - create the harvest object
        - create the harvest object errors
        - add harvest_object_id to the list that contains all created harvest objects ids 
        - add guid to guids to the list that contains the guids of all created harvest objects ids 
        - update the diccionary used to relate dataservice_uri with its entity_harves_object_id
        - update the dictionary used to relate the dataset_uri served by this dataservice with the dataservice harvest object id
    
    :param dataset_uri: dataservice uri
    :type dataset_uri: str
    
    :param dataset_dict: dictionary with dataset data
    :type dataset_dict: dict[str, object]
    
    :param dataset_guid: dataservice guid
    :type dataset_guid: str
    
    :param harvester_type: harvester type
    :type harvester_type: str
    
    :param conforms: True in parse is right, False in other case
    :type conforms: bool
    
    :param error_messages: dataset parse errores
    :type error_messages: List[str]

    :param error_details: dataset structured parse errors
    :type error_details: List[dict[str, object]]
        
    :param harvest_job: Harvest job
    :type harvest_job: HarvestJob
    
    :param object_ids: List of havest objects id of harvest job
    :type object_ids: List[str]
    
    :param uri_ho_dict: Dictionary than contains the relation between dataset_uri and its harvest object id
    :type uri_ho_dict: dict[str, str]
    
    :param uri_dataset_ho_id_dict: Dictionary that contais the relation between dataset_uri and the dataservice harvest object id that serves the dataset
    :type uri_dataset_ho_id_dict: dict[str, List[str]]
    """
    if not dataset_dict.get(DatasetConstants.KEY_NAME, None):
        log.error(f'Could not get a name for dataset: {dataset_dict}')
        raise GatherResourceMissingNameError()
    if not dataset_guid:
        log.error(f'Could not get a unique identifier for dataset: {dataset_dict}')
        raise GatherResourceMissingIdentifierError()
    # clean dictionary
    del dataset_dict[DatasetConstants.KEY_ERRORS]
    del dataset_dict[DatasetConstants.KEY_WARNINGS]
    dataset_dict.pop(PackageConstants.KEY_ERROR_DETAILS, None)
    dataset_dict.pop(PackageConstants.KEY_WARNING_DETAILS, None)

    # create Harvest Object
    obj = HarvestObject(guid=dataset_guid, job=harvest_job,content=json.dumps(dataset_dict),
                         extras=[HarvestObjectExtra(key=HOEKeyConstants.HOE_PACKAGE_TYPE_KEY, value=HOEKeyConstants.HOE_PACKAGE_TYPE_DATASET_VALUE),
                                HarvestObjectExtra(key=HOEKeyConstants.HOE_GRAPH_NAME_KEY, value=generate_graph_uri_from_job(harvest_job)), 
                                HarvestObjectExtra(key=HOEKeyConstants.HOE_SOURCE_URI_KEY, value=dataset_uri),
                                HarvestObjectExtra(key=HOEKeyConstants.HOE_CKAN_URI_KEY, value=get_value_of_an_extras_key_from_dict(dataset_dict, PackageConstants.KEY_EXTRAS_CKAN_URI)),
                                HarvestObjectExtra(key=HOEKeyConstants.HOE_CKAN_NAME_KEY, value=dataset_dict.get(PackageConstants.KEY_NAME, None)),
                                HarvestObjectExtra(key=HOEKeyConstants.HOE_HARVESTER_TYPE, value=harvester_type)])
    if not conforms:
        obj.state = 'ERROR'
    obj.save()
    # Create error messages
    entity_type = "dataset"
    phase=REPORT_PHASE_VALIDATION
    reason = VALIDATION_REASON_INVALID_PARSE_DATASET
    for index, message in enumerate(error_messages or []):
        #_save_object_error(message, obj, 'Gather')
        error_detail = _get_detail_by_index(error_details, index)
        error_entity_type = (error_detail or {}).get(HarvestMessageDetailConstants.KEY_SCOPE) or entity_type
        save_structured_object_error_method(
            exception = (error_detail or {}).get(HarvestMessageDetailConstants.KEY_EXCEPTION),
            harvest_object=obj,
            raw_message=(error_detail or {}).get(HarvestMessageDetailConstants.KEY_MESSAGE) or message, 
            display_message = (error_detail or {}).get(HarvestMessageDetailConstants.KEY_MESSAGE) or message,
            phase=phase,
            kind=f"parse_{error_entity_type}",
            reason=reason,
            resource_uri=(error_detail or {}).get(HarvestMessageDetailConstants.KEY_RESOURCE_URI) or dataset_uri,
            message_code=get_common_error_message_code(phase=phase, reason=reason),
            payload={"entity_type": error_entity_type},
        )
    if not conforms:
        return False
    # Append id to list
    object_ids.append(obj.id)
    
    # update data of package related to dataservices (access_service in distribution and served_by_dataservie in dataset): 
    # replace datservice_uri in RDF by harves_object_id that contains that datservice
    _process_access_services(dataset_dict, uri_ho_dict)
    # add servedByDataservice property with ho_id
    dataset_uri = dataset_dict.get(DatasetConstants.KEY_URI, None)
    if dataset_uri is not None:
        dataset_dict[DatasetConstants.KEY_DATASET_SERVED_BY_DATASERVICE] = uri_dataset_ho_id_dict.get(dataset_uri, [])
    obj.content=json.dumps(dataset_dict)

    obj.save()
    # Add uri-guid to dict 
    if dataset_uri is not None:
        uri_ho_dict[dataset_uri] = obj.id
    return True

def _process_access_services(dataset_dict, uri_ho_dict):
    resources = dataset_dict.get(DatasetConstants.KEY_RESOURCES, [])
    for resource in resources:
        access_services = resource.get(DistributionConstants.KEY_DISTRIBUTION_ACCESS_SERVICE, [])
        access_services_ho = []
        for access_service in access_services:
            access_services_ho.append(uri_ho_dict.get(access_service, ''))
            resource[DistributionConstants.KEY_DISTRIBUTION_ACCESS_SERVICE] = access_services_ho
