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

from ckanext.harvest.model import HarvestJob, HarvestGatherError

from ...constants.dcat_ap_es_constants import DCATAPESHarvesterConstants, DcatClassNameEnum
from ...rdf_store  import RDFStoreComplete, RDFStoreDelete, RDFStoreException
from ...decorators import log_debug

log = logging.getLogger(__name__)

_save_gather_error = HarvestGatherError.create

@log_debug
def _preprocess_source_rdf_repetitive_actions(rdf_store:RDFStoreDelete, graph_uri:str,  harvest_job: HarvestJob) -> None:
    ''' 
    Prepares the source RDF so that it can be validated with actions that must to be repeated until nothing is deleted. 

    :param rdf_store: RDF store
    :type rdf_store: RDFStoreDelete

    :param graph: graph uri
    :type graph: str

    :param harvest_job: harvest job
    :type harvest_job: HarvestJob
                
    '''
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    repeat_block = True
    MAX_NUM_OF_ITERATIONS = 20
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
            _save_gather_error(DCATAPESHarvesterConstants.DELETE_UNREFERENCED_DATASET_IN_CATALOG.format(deleted_dataset_reference), harvest_job)

        # Remove dataservices references of dataservices that are not referenced in a catalog
        # RDF contains a distribution that access a dataservice, but this dataservice is not referenced in a catalog
        for deleted_dataservice_reference in rdf_store.remove_references_of_unreferenced_datasets_or_dataservices_in_a_catalog(DcatClassNameEnum.DATASERVICE) or []:
            repeat_block = True
            actions.append('unreferenced dataservices')
            _save_gather_error(DCATAPESHarvesterConstants.DELETE_UNREFERENCED_DATASERVICE_IN_CATALOG.format(deleted_dataservice_reference), harvest_job)
        
        # Remove undescribed datasets
        for deleted_undescribed_dataset in rdf_store.remove_undescribed_datasets_or_dataservices(DcatClassNameEnum.DATASET) or []:
            repeat_block = True
            actions.append('undescribed datasets')
            _save_gather_error(DCATAPESHarvesterConstants.DELETE_UNDESCRIBED_DATASET.format(deleted_undescribed_dataset), harvest_job)

        # Remove unreferenced described datasets 
        for deleted_unreferenced_described_dataset in rdf_store.remove_unreferenced_described_datasets_or_dataservices(DcatClassNameEnum.DATASET) or []:
            repeat_block = True
            actions.append('unrefereced described datasets')
            _save_gather_error(DCATAPESHarvesterConstants.DELETE_UNREFERENCED_DESCRIBED_DATASET.format(deleted_unreferenced_described_dataset), harvest_job)

        # Remove undescribed dataservices
        for deleted_undescribed_dataservice in rdf_store.remove_undescribed_datasets_or_dataservices(DcatClassNameEnum.DATASERVICE) or []:
            repeat_block = True
            actions.append('undescribed dataservices')
            _save_gather_error(DCATAPESHarvesterConstants.DELETE_UNDESCRIBED_DATASERVICE.format(deleted_undescribed_dataservice), harvest_job)

        # Remove unreferenced described dataservices 
        for deleted_unreferenced_described_dataservice in rdf_store.remove_unreferenced_described_datasets_or_dataservices(DcatClassNameEnum.DATASERVICE) or []:
            repeat_block = True
            actions.append('unrefereced described dataservices')
            _save_gather_error(DCATAPESHarvesterConstants.DELETE_UNREFERENCED_DESCRIBED_DATASERVICE.format(deleted_unreferenced_described_dataservice), harvest_job)
    if i == MAX_NUM_OF_ITERATIONS:
        log.error(f'{method_log_prefix} The maximum number of iterations has been reached. Repetitive actions {", ".join(actions)}. The rdf may not have been cleaned properly. It would be necessary to check that the queries are correct.')
        raise RDFStoreException("Error preprocessing RDF. The rdf may not have been cleaned properly.")

@log_debug
def preprocess_source_rdf(rdf_store:RDFStoreComplete, graph_uri:str, harvest_job: HarvestJob) -> None:
    ''' 
    Prepares the source RDF so that it can be validated. 

    :param rdf_store: RDF Store
    :type rdf_store: RDFStoreComplete

    :param graph: graph uri
    :type graph: str

    :param harvest_job: harvest job
    :type harvest_job: HarvestJob
            
    '''
    # Remove paginatation info
    rdf_store.rdf_store_delete.remove_pagination_data()

    # Remove unreferenced nodes
    for unreferenced_node in rdf_store.rdf_store_delete.drop_all_unreferenced_nodes():
        _save_gather_error(DCATAPESHarvesterConstants.DELETE_UNREFERENCED_NODE.format(unreferenced_node), harvest_job)

    # Remove publisher or creators info (only data of datos.gob organism)
    for deleted_agent_data in rdf_store.rdf_store_delete.delete_data_publishers_in_graph() or []:
        _save_gather_error(DCATAPESHarvesterConstants.DELETE_AGENT_DATA.format(deleted_agent_data), harvest_job)

    # Remove undescribed catalogs
    for deleted_catalog in rdf_store.rdf_store_delete.remove_undescribed_catalogs() or []:
        _save_gather_error(DCATAPESHarvesterConstants.DELETE_UNDESCRIBED_CATALOG.format(deleted_catalog), harvest_job)

    # Remove catalogRecord entities. They will not be used in own catalog 
    for deleted_catalog_record in rdf_store.rdf_store_delete.remove_catalog_records() or []:
        _save_gather_error(DCATAPESHarvesterConstants.DELETE_CATALOG_RECORD.format(deleted_catalog_record), harvest_job)

    # A dataset only can be referenced in a single catalog
    multiple_dataset_references = rdf_store.rdf_store_insert_or_update.update_graph_to_fullfil_one_dataset_reference_in_a_single_catalog()
    for multiple_dataset_reference_key in multiple_dataset_references.keys() or []:
        _save_gather_error(DCATAPESHarvesterConstants.DELETE_DATASET_REFERENCE_IN_CATALOG.format(multiple_dataset_reference_key, ", ".join(multiple_dataset_references.get(multiple_dataset_reference_key, []))), harvest_job)
    
    # A dataservice only can be referenced in a single catalog
    multiple_dataservice_references = rdf_store.rdf_store_insert_or_update.update_graph_to_fullfil_one_dataservice_reference_in_a_single_catalog()
    for multiple_dataservice_reference_key in multiple_dataservice_references.keys() or []:
        _save_gather_error(DCATAPESHarvesterConstants.DELETE_DATASERVICE_REFERENCE_IN_CATALOG.format(multiple_dataservice_reference_key, ", ".join(multiple_dataservice_references.get(multiple_dataservice_reference_key, []))), harvest_job)
    
    # Run repetitive actions
    _preprocess_source_rdf_repetitive_actions(rdf_store.rdf_store_delete, graph_uri, harvest_job)