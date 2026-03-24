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
from typing import List, Tuple
import ckan.model as model
from ckan.plugins import toolkit
from ckanext.harvest.model import (HarvestObject, HarvestObjectExtra, HarvestJob)
from rdflib import URIRef
from ...constants import (CommonPackageConstants as PackageConstants)
from ...constants.dcat_ap_es_constants import DCAT, DCT, RDF_NAMESPACE, FOAF
from ...rdf_store  import RDFStoreDelete, RDFStoreQuery, RDFStoreComplete
from ...utils import generate_graph_uri_from_source_and_job, get_value_of_an_extras_key_from_dict, from_str_to_uriref
from ...decorators import log_debug, log_info

log = logging.getLogger(__name__)

@log_debug
def get_graphs_names_of_a_harvest_source(harvest_source_id:str) -> List[str]:
    '''
    Get graph names of a harvest source_id
    
    :param harvest_source_id: Source id of current harvesting job
    :type harvest_source_id: str
    
    :return a List of possible graph_names related to this harvest source
    :rtype List[str]
    
    '''
    # Get harvest_source graphs in store
    result = []
    if harvest_source_id:
        rdf_store_query = RDFStoreQuery(None)
        suffix = 'job_id'
        aux_graph_uri = generate_graph_uri_from_source_and_job(harvest_source_id, suffix)
        prefix = aux_graph_uri.replace(suffix,  '') if aux_graph_uri else None
        result = rdf_store_query.get_graphs_names_starting_with_a_prefix(prefix)
    return result

@log_debug
def get_last_graph_of_a_harvest_source(harvest_source_id:str, graph_names: List[str]) -> Tuple[str, str]:
    '''
    Get the last graph name associated with a harvest_job from harvest_source_id
    
    :param harvest_source_id: Source id of of current harvesting job
    :type harvest_source_id: str
    
    :param graph_names: List of graph_names related to harvest_source_id
    :type graph_names: List[str]
    
    :return a tuple with the id of last finished harvest job and the graph_name associated with that job
    :rtype Tuple[str,str]
    '''
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    last_job_id = None
    last_graph_name = None
    if harvest_source_id:
        if not graph_names:
            graph_names = get_graphs_names_of_a_harvest_source(harvest_source_id)

        jobs  =  model.Session.query(HarvestJob.id) \
                .filter(HarvestJob.source_id == harvest_source_id) \
                .order_by(HarvestJob.gather_started.desc()) \
                .all()

        log.info(f'{method_log_prefix} jobs = {jobs}')

        for job_id, in jobs or []:    
            graph_name = generate_graph_uri_from_source_and_job(harvest_source_id, job_id)
            if graph_name in graph_names:
                last_job_id = job_id
                last_graph_name = graph_name
                break
    return last_job_id, last_graph_name

@log_info
def remove_graphs_of_previous_harvesting(harvest_job: HarvestJob) -> str:
    '''
    Remove graphs created in previous harvesting, except the graph of the last finished harvest job with complete gather stage
    and the graphs of harvest jobs that contains an harvest_object with current=True
    
    :param harvest_job: Harvest job of current harvesting
    :type harvest_job: Harvest Job
    
    :return graph_name of the last of last finished harvest job, that contains catalog metadata
    :rtype str
    '''
    last_graph_name = None
    if harvest_job and harvest_job.source and harvest_job.source.id:
        harvest_source_id = harvest_job.source.id
        last_graph_name = remove_graphs_of_previous_harvesting_from_source_id(harvest_source_id)
    return last_graph_name

def remove_graphs_of_previous_harvesting_from_source_id(harvest_source_id: str) -> str:
    '''
    Remove graphs created in previous harvesting, except the graph of the last finished harvest job with complete gather stage
    and the graphs of harvest jobs that contains an harvest_object with current=True
    
    :param harvest_source_id: Harvest source identifier
    :type harvest_source_id: str
    
    :return graph_name of the last of last finished harvest job, that contains catalog metadata
    :rtype str
    '''
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    last_graph_name = None
    if harvest_source_id:
        # Get harvest_source graphs in store
        graph_names = get_graphs_names_of_a_harvest_source(harvest_source_id)
        _last_job_id, last_graph_name = get_last_graph_of_a_harvest_source(harvest_source_id, graph_names)

        harvest_job_ids = model.Session.query(HarvestObject.harvest_job_id) \
            .filter(HarvestObject.harvest_source_id == harvest_source_id) \
            .filter(HarvestObject.current == True) \
            .distinct(HarvestObject.harvest_job_id) \
            .all()
        
        log.info(f'{method_log_prefix} harvest_job_ids = {harvest_job_ids}')
        graph_name_jobs = set([generate_graph_uri_from_source_and_job(harvest_source_id, job_id) for job_id, in harvest_job_ids or []])
        if last_graph_name:
            graph_name_jobs.add(last_graph_name)
               
        # Remove from graph_names, needed graphs
        rdf_store = RDFStoreDelete(None)
        for graph_name_job in graph_name_jobs or []:
            if graph_name_job in graph_names:
                graph_names.remove(graph_name_job)

        # Delete graphs
        for graph_to_delete in graph_names:
            rdf_store.update_graph_uri(graph_to_delete)
            rdf_store.drop_graph()
    return last_graph_name

@log_debug
def get_value_of_a_package_extras_key(package:model.Package, key:str) -> str:
    """Get the key value of an extra

    :param package: Package
    :type package: model.Package

    :param key: extras key
    :type key: str

    :returns: key value
    :rtype: str
    """
    return get_value_of_an_extras_key_from_dict(package, key)

@log_debug
def mark_datasets_for_deletion(guids_in_source, harvest_job):
    '''
    Given a list of guids in the remote source, checks which in the DB
    need to be deleted

    To do so it queries all guids in the DB for this source and calculates
    the difference.

    For each of these creates a HarvestObject with the dataset id, marked
    for deletion.

    Returns a list with the ids of the Harvest Objects to delete.

    This method has as a reference rdf.py _mark_datasets_for_deletion of ckanext-dcat extension
    '''

    object_ids = []

    # Get all previous current guids and dataset ids for this source
    query = model.Session.query(HarvestObject.guid, HarvestObject.package_id) \
                            .filter(HarvestObject.current==True) \
                            .filter(HarvestObject.harvest_source_id==harvest_job.source.id)

    guid_to_package_id = {}
    for guid, package_id in query:
        guid_to_package_id[guid] = package_id

    guids_in_db = list(guid_to_package_id.keys())

    # Get objects/datasets to delete (ie in the DB but not in the source)
    guids_to_delete = set(guids_in_db) - set(guids_in_source)

    # Create a harvest object for each of them, flagged for deletion
    for guid in guids_to_delete:
        obj = HarvestObject(guid=guid, job=harvest_job,
                            package_id=guid_to_package_id[guid],
                            extras=[HarvestObjectExtra(key='status',
                                                        value='delete')])
        obj.save()
        object_ids.append(obj.id)

    return object_ids

@log_info
def update_catalog_metadata_in_source_graph(root_catalog, job_graph_name, source_graph_name, source_catalog_uri):
    rdf_store = RDFStoreComplete(job_graph_name)
    # get catalog data from root_catalog in job_graph
    exclude_predicates = [URIRef(DCAT.record), URIRef(DCAT.service), URIRef(DCAT.dataset)]
    root_catalog_graph = rdf_store.rdf_store_query.get_customized_node(root_catalog, exclude_predicates, [], [], normalize_node=True)
    # update subject in triples
    for s,p,o in root_catalog_graph:
        if s == URIRef(root_catalog):
            root_catalog_graph.remove((s,p,o))
            root_catalog_graph.add((URIRef(source_catalog_uri), p, o))

    # insert new catalog data in source_graph
    rdf_store.update_graph_uri(source_graph_name)
    rdf_store.rdf_store_insert_or_update.insert_rdf_data(root_catalog_graph)

@log_debug
def _get_package_info(harvest_object: HarvestObject, return_all_package_data:bool = False) ->  Tuple[str, str, str, dict]:
    '''
    Get data of package_id related to harvest_object
    
    :param harvest_object: Harvest object that contains info of the dataset or dataservice
    :type harvest_object: HarvestObject
    
    :param return_all_package_data: True if the method return dictionary with all package data, False in other case (return None)
    :type return_all_package_data: bool
    
    :return package uri in ckan, package uri in source and package type
    :rtype: Tuple[str, str, str]
    '''
    package_uri_in_ckan = None
    package_uri_in_source = None
    package_type = None
    package_data = None
    if harvest_object.package_id:
        data_dict = {'id': harvest_object.package_id}
        package_show_context = {'model': model, 'session': model.Session,
                                'ignore_auth': True}
        package_dict = toolkit.get_action('package_show')(package_show_context, data_dict)
        package_uri_in_ckan = get_value_of_a_package_extras_key(package_dict, PackageConstants.KEY_EXTRAS_CKAN_URI)
        package_uri_in_source = get_value_of_a_package_extras_key(package_dict, PackageConstants.KEY_EXTRAS_SOURCE_URI)
        package_type = package_dict.get("type", None) 
        if return_all_package_data:
            package_data = package_dict 
    return package_uri_in_ckan, package_uri_in_source, package_type, package_data

@log_info
def delete_dataset_or_dataservice_in_source_graph(harvest_object: HarvestObject, source_graph_name:str):
    '''
    Delete metadata of a deleted dataset or dataservice in source graph
    
    :param harvest_object: Harvest object that contains info of the dataset or dataservice
    :type harvest_object: HarvestObject
    
    :param source_graph_name: graph name of the current harvest source
    :type source_graph_name: str
    '''
    if harvest_object.package_id:
        rdf_store_delete = RDFStoreDelete(source_graph_name)
        package_uri_in_ckan, _package_uri_in_source, package_type, _ = _get_package_info(harvest_object, False)
        if package_type and (package_type == PackageConstants.KEY_TYPE_DATASET_VALUE or package_type == PackageConstants.KEY_TYPE_DATASERVICE_VALUE):
            if package_type == PackageConstants.KEY_TYPE_DATASERVICE_VALUE:
                rdf_store_delete.delete_dataservice_in_graph(package_uri_in_ckan)
            else:
                rdf_store_delete.delete_dataset_in_graph(package_uri_in_ckan)
            rdf_store_delete.drop_all_unreferenced_nodes()
