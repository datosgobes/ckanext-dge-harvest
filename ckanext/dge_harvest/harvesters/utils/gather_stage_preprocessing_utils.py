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
import inspect

from ckanext.harvest.model import HarvestJob

from ckanext.dge_harvest.constants.dcat_ap_es_constants import DCATAPESHarvesterConstants, DcatClassNameEnum
from ckanext.dge_harvest.rdf_store  import RDFStoreComplete, RDFStoreDelete, RDFStoreException
from ckanext.dge_harvest.decorators import log_debug
from ckanext.dge_harvest.services.report.harvest_report_common_classifier import(
    PREPROCESSING_REASON_PORTAL_ORGANIZATION_DATA,
    PREPROCESSING_REASON_UNREFERENCED_DATASET,
    PREPROCESSING_REASON_UNREFERENCED_DATASERVICE,
    PREPROCESSING_REASON_UNDESCRIBED_DATASET,
    PREPROCESSING_REASON_UNDESCRIBED_DATASERVICE,
    PREPROCESSING_REASON_UNREFERENCED_DESCRIBED_DATASET,
    PREPROCESSING_REASON_UNREFERENCED_DESCRIBED_DATASERVICE,
    PREPROCESSING_REASON_UNREFERENCED_NODE,
    PREPROCESSING_REASON_UNDESCRIBED_CATALOG,
    PREPROCESSING_REASON_CATALOG_RECORD,
    PREPROCESSING_REASON_DATASET_REFERENCE_IN_MULTIPLE_CATALOGS,
    PREPROCESSING_REASON_DATASERVICE_REFERENCE_IN_MULTIPLE_CATALOGS,
)
from ...utils import get_int_value_from_ckan_property
log = logging.getLogger(__name__)

_MAX_PREPROCESS_ITERATIONS = 'ckanext.dge_harvest.preprocess.max_num_of_iterations'

@log_debug
def _preprocess_source_rdf_repetitive_actions(rdf_store:RDFStoreDelete, 
                                              graph_uri:str,  
                                              harvest_job: HarvestJob, 
                                              save_preprocessing_structured_gather_report_info_message) -> None:
    ''' 
    Prepares the source RDF so that it can be validated with actions that must to be repeated until nothing is deleted. 

    :param rdf_store: RDF store
    :type rdf_store: RDFStoreDelete

    :param graph: graph uri
    :type graph: str

    :param harvest_job: harvest job
    :type harvest_job: HarvestJob

    :param save_preprocessing_structured_gather_report_info_message: method to save report messages
    :type save_preprocessing_structured_gather_report_info_message: List[str, str, str, str, str, str, str, str, str, Dict[str, str], str]
    '''
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    repeat_block = True
    MAX_NUM_OF_ITERATIONS = get_int_value_from_ckan_property(_MAX_PREPROCESS_ITERATIONS, 20)
    i = 0
    actions = []
    # Repeat until nothing is removed.
    while repeat_block and i < MAX_NUM_OF_ITERATIONS:
        i = i+1
        message = f' due to actions: {", ".join(actions)}' if i > 1 else ''
        log.debug(f'{method_log_prefix} Repetition {i} of the block of repetitive actions {message}')
        actions.clear()
        repeat_block = False
        # Remove dataset references of datasets that are not referenced in a catalog
        # RDF contains a dataservice that serves a dataset, but this datasets is not referenced in a catalog
        for deleted_dataset_reference in rdf_store.remove_references_of_unreferenced_datasets_or_dataservices_in_a_catalog(DcatClassNameEnum.DATASET) or []:
            repeat_block = True
            actions.append('unreferenced datasets')
            save_preprocessing_structured_gather_report_info_message(
                harvest_job=harvest_job,
                display_message=DCATAPESHarvesterConstants.DELETE_UNREFERENCED_DATASET_IN_CATALOG.format(deleted_dataset_reference),
                raw_message=DCATAPESHarvesterConstants.DELETE_UNREFERENCED_DATASET_IN_CATALOG.format(deleted_dataset_reference),
                kind="remove_unreferenced_catalog_dataset_references",
                reason=PREPROCESSING_REASON_UNREFERENCED_DATASET,
                resource_uri=deleted_dataset_reference,
            )

        # Remove dataservices references of dataservices that are not referenced in a catalog
        # RDF contains a distribution that access a dataservice, but this dataservice is not referenced in a catalog
        for deleted_dataservice_reference in rdf_store.remove_references_of_unreferenced_datasets_or_dataservices_in_a_catalog(DcatClassNameEnum.DATASERVICE) or []:
            repeat_block = True
            actions.append('unreferenced dataservices')
            save_preprocessing_structured_gather_report_info_message(
                harvest_job=harvest_job,
                display_message=DCATAPESHarvesterConstants.DELETE_UNREFERENCED_DATASERVICE_IN_CATALOG.format(deleted_dataservice_reference),
                raw_message=DCATAPESHarvesterConstants.DELETE_UNREFERENCED_DATASERVICE_IN_CATALOG.format(deleted_dataservice_reference),
                kind="remove_unreferenced_catalog_dataservice_references",
                reason=PREPROCESSING_REASON_UNREFERENCED_DATASERVICE,
                resource_uri=deleted_dataservice_reference,
            )
        
        # Remove undescribed datasets
        for deleted_undescribed_dataset in rdf_store.remove_undescribed_datasets_or_dataservices(DcatClassNameEnum.DATASET) or []:
            repeat_block = True
            actions.append('undescribed datasets')
            save_preprocessing_structured_gather_report_info_message(
                harvest_job=harvest_job,
                display_message=DCATAPESHarvesterConstants.DELETE_UNDESCRIBED_DATASET.format(deleted_undescribed_dataset),
                raw_message=DCATAPESHarvesterConstants.DELETE_UNDESCRIBED_DATASET.format(deleted_undescribed_dataset),
                kind="remove_undescribed_dataset",
                resource_uri=deleted_undescribed_dataset,
                reason = PREPROCESSING_REASON_UNDESCRIBED_DATASET,
            )

        # Remove unreferenced described datasets 
        for deleted_unreferenced_described_dataset in rdf_store.remove_unreferenced_described_datasets_or_dataservices(DcatClassNameEnum.DATASET) or []:
            repeat_block = True
            actions.append('unrefereced described datasets')
            save_preprocessing_structured_gather_report_info_message(
                harvest_job=harvest_job,
                display_message=DCATAPESHarvesterConstants.DELETE_UNREFERENCED_DESCRIBED_DATASET.format(deleted_unreferenced_described_dataset),
                raw_message=DCATAPESHarvesterConstants.DELETE_UNREFERENCED_DESCRIBED_DATASET.format(deleted_unreferenced_described_dataset),
                kind="remove_unreferenced_described_dataset",
                resource_uri=deleted_unreferenced_described_dataset,
                reason = PREPROCESSING_REASON_UNREFERENCED_DESCRIBED_DATASET
            )

        # Remove undescribed dataservices
        for deleted_undescribed_dataservice in rdf_store.remove_undescribed_datasets_or_dataservices(DcatClassNameEnum.DATASERVICE) or []:
            repeat_block = True
            actions.append('undescribed dataservices')
            save_preprocessing_structured_gather_report_info_message(
                harvest_job=harvest_job,
                display_message=DCATAPESHarvesterConstants.DELETE_UNDESCRIBED_DATASERVICE.format(deleted_undescribed_dataservice),
                raw_message=DCATAPESHarvesterConstants.DELETE_UNDESCRIBED_DATASERVICE.format(deleted_undescribed_dataservice),
                kind="remove_undescribed_dataservice",
                resource_uri=deleted_undescribed_dataservice,
                reason = PREPROCESSING_REASON_UNDESCRIBED_DATASERVICE,
            )

        # Remove unreferenced described dataservices 
        for deleted_unreferenced_described_dataservice in rdf_store.remove_unreferenced_described_datasets_or_dataservices(DcatClassNameEnum.DATASERVICE) or []:
            repeat_block = True
            actions.append('unrefereced described dataservices')
            save_preprocessing_structured_gather_report_info_message(
                harvest_job=harvest_job,
                display_message=DCATAPESHarvesterConstants.DELETE_UNREFERENCED_DESCRIBED_DATASERVICE.format(deleted_unreferenced_described_dataservice),
                raw_message=DCATAPESHarvesterConstants.DELETE_UNREFERENCED_DESCRIBED_DATASERVICE.format(deleted_unreferenced_described_dataservice),
                kind="remove_unreferenced_described_dataservice",
                resource_uri=deleted_unreferenced_described_dataservice,
                reason = PREPROCESSING_REASON_UNREFERENCED_DESCRIBED_DATASERVICE,
            )
        if repeat_block:
            rdf_store.drop_all_unreferenced_nodes()
    if i == MAX_NUM_OF_ITERATIONS:
        log.error(f'{method_log_prefix} The maximum number of iterations has been reached. Repetitive actions {", ".join(actions)}. The rdf may not have been cleaned properly. It would be necessary to check that the queries are correct.')
        raise RDFStoreException("Error preprocessing RDF. The rdf may not have been cleaned properly")


@log_debug
def preprocess_source_rdf(rdf_store:RDFStoreComplete, graph_uri:str, harvest_job: HarvestJob, save_preprocessing_structured_gather_report_info_message_method) -> None:
    ''' 
    Prepares the source RDF so that it can be validated. 

    :param rdf_store: RDF Store
    :type rdf_store: RDFStoreComplete

    :param graph: graph uri
    :type graph: str

    :param harvest_job: harvest job
    :type harvest_job: HarvestJob

    :param save_preprocessing_structured_gather_report_info_message: method to save report messages
    :type save_preprocessing_structured_gather_report_info_message: List[str, str, str, str, str, str, str, str, str, Dict[str, str], str]
    '''
    # Remove paginatation info
    rdf_store.rdf_store_delete.remove_pagination_data()

    # Remove unreferenced nodes
    for unreferenced_node in rdf_store.rdf_store_delete.drop_all_unreferenced_nodes():
        save_preprocessing_structured_gather_report_info_message_method(
            harvest_job=harvest_job,
            display_message=DCATAPESHarvesterConstants.DELETE_UNREFERENCED_NODE.format(unreferenced_node),
            raw_message=DCATAPESHarvesterConstants.DELETE_UNREFERENCED_NODE.format(unreferenced_node),
            kind="remove_unreferenced_node",
            resource_uri=unreferenced_node,
            reason = PREPROCESSING_REASON_UNREFERENCED_NODE,
        )

    # Remove publisher or creators info (only data of datos.gob organism)
    for deleted_agent_data in rdf_store.rdf_store_delete.delete_data_publishers_in_graph() or []:
        save_preprocessing_structured_gather_report_info_message_method(
            harvest_job=harvest_job,
            display_message=DCATAPESHarvesterConstants.DELETE_AGENT_DATA.format(deleted_agent_data),
            raw_message=DCATAPESHarvesterConstants.DELETE_AGENT_DATA.format(deleted_agent_data),
            kind="replace_agent_data",
            reason=PREPROCESSING_REASON_PORTAL_ORGANIZATION_DATA,
            resource_uri=deleted_agent_data,
        )

    # Remove undescribed catalogs
    for deleted_catalog in rdf_store.rdf_store_delete.remove_undescribed_catalogs() or []:
        save_preprocessing_structured_gather_report_info_message_method(
            harvest_job=harvest_job,
            display_message=DCATAPESHarvesterConstants.DELETE_UNDESCRIBED_CATALOG.format(deleted_catalog),
            raw_message=DCATAPESHarvesterConstants.DELETE_UNDESCRIBED_CATALOG.format(deleted_catalog),
            kind="remove_undescribed_catalog",
            resource_uri=deleted_catalog,
            reason = PREPROCESSING_REASON_UNDESCRIBED_CATALOG
        )

    # Remove catalogRecord entities. They will not be used in own catalog 
    for deleted_catalog_record in rdf_store.rdf_store_delete.remove_catalog_records() or []:
        save_preprocessing_structured_gather_report_info_message_method(
            harvest_job=harvest_job,
            display_message=DCATAPESHarvesterConstants.DELETE_CATALOG_RECORD.format(deleted_catalog_record),
            raw_message=DCATAPESHarvesterConstants.DELETE_CATALOG_RECORD.format(deleted_catalog_record),
            kind="remove_catalog_record",
            resource_uri=deleted_catalog_record,
            reason=PREPROCESSING_REASON_CATALOG_RECORD
        )

    # A dataset only can be referenced in a single catalog
    multiple_dataset_references = rdf_store.rdf_store_insert_or_update.update_graph_to_fullfil_one_dataset_reference_in_a_single_catalog()
    for multiple_dataset_reference_key in multiple_dataset_references.keys() or []:
        deleted_catalogs = multiple_dataset_references.get(
            multiple_dataset_reference_key,
            [],
        )
        save_preprocessing_structured_gather_report_info_message_method(
            harvest_job=harvest_job,
            display_message=DCATAPESHarvesterConstants.DELETE_DATASET_REFERENCE_IN_CATALOG.format(multiple_dataset_reference_key, ", ".join(deleted_catalogs)),
            raw_message=DCATAPESHarvesterConstants.DELETE_DATASET_REFERENCE_IN_CATALOG.format(multiple_dataset_reference_key, ", ".join(deleted_catalogs)),
            kind="deduplicate_dataset_catalog_reference",
            reason=PREPROCESSING_REASON_DATASET_REFERENCE_IN_MULTIPLE_CATALOGS,
            resource_uri=multiple_dataset_reference_key,
            payload={"catalog_uris": list(deleted_catalogs)},
        )
    
    # A dataservice only can be referenced in a single catalog
    multiple_dataservice_references = rdf_store.rdf_store_insert_or_update.update_graph_to_fullfil_one_dataservice_reference_in_a_single_catalog()
    for multiple_dataservice_reference_key in multiple_dataservice_references.keys() or []:
        deleted_catalogs = multiple_dataservice_references.get(
            multiple_dataservice_reference_key,
            [],
        )
        save_preprocessing_structured_gather_report_info_message_method(
            harvest_job=harvest_job,
            display_message=DCATAPESHarvesterConstants.DELETE_DATASERVICE_REFERENCE_IN_CATALOG.format(multiple_dataservice_reference_key, ", ".join(deleted_catalogs)),
            raw_message=DCATAPESHarvesterConstants.DELETE_DATASERVICE_REFERENCE_IN_CATALOG.format(multiple_dataservice_reference_key, ", ".join(deleted_catalogs)),
            kind="deduplicate_dataservice_catalog_reference",
            reason=PREPROCESSING_REASON_DATASERVICE_REFERENCE_IN_MULTIPLE_CATALOGS,
            resource_uri=multiple_dataservice_reference_key,
            payload={"catalog_uris": list(deleted_catalogs)}
        )
    
    # Run repetitive actions
    _preprocess_source_rdf_repetitive_actions(rdf_store.rdf_store_delete, graph_uri, harvest_job, save_preprocessing_structured_gather_report_info_message_method)
