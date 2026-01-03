# Copyright (C) 2025 Entidad Pública Empresarial Red.es
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
import uuid
import inspect
import sqlalchemy as sa
from typing import List, Tuple
from rdflib import URIRef, Literal, Graph
import ckan.logic as logic
import ckan.model as model
import ckan.plugins as p
import ckan.lib.plugins as lib_plugins
from ckantoolkit import h
from ckanext.dcat.interfaces import IDCATRDFHarvester
from ckanext.harvest.logic.schema import unicode_safe
from ckanext.harvest.model import (HarvestJob, HarvestObject, HarvestObjectError, HarvestGatherError)
from ...constants import (DCATAPESDatasetConstants as DatasetConstants,
                                               DCATAPESDistributionConstants as DistributionConstants,
                                               DCATAPESHarvesterConstants as HarvesterConstants,
                                               CommonPackageConstants, HarvestObjectExtraKeyConstants as HOEKeyConstants)
from ...constants.dcat_ap_es_constants import (DCAT, RDF, DCT, SKOS, XSD, FOAF, ADMS)
from ...rdf_store  import RDFStoreComplete, RDFStoreDelete
from .harvester_utils import _get_package_info
from ...utils import generate_graph_uri_from_job, dge_harvest_resource_uri, dge_harvest_dataservice_uri, dge_harvest_dataset_uri
from ...decorators import log_debug, log_info

log = logging.getLogger(__name__)

_save_object_error = HarvestObjectError.create

IMPORT_STAGE = 'Import'
    
@log_info
def delete_package(harvest_object:HarvestObject, user_name:str) -> bool:
    """
    Delete the package associated with harvest_object, 
    delete package metadata of graph related to job where this guid is current and
    mark the rest of objects for this guid as not current 

    :param harvest_object: harvest object that contains the package data to delete
    :type haverst_ob: HarvestObject

    :param user_name: user name with permissions to delete package
    :type user_name: str
    
    :return True if package has been deleted, False in other case
    :rtype: bool
    """
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    log.debug(f'{method_log_prefix}. Harvest_object with id = {harvest_object.id}; guid= {harvest_object.guid}; package_id={harvest_object.package_id}')
    context = {'model': model, 'session': model.Session,
               'user': user_name, 'ignore_auth': True}
    try:
        if harvest_object.package_id:
            p.toolkit.get_action('package_delete')(context, {'id': harvest_object.package_id})
            log.info(f'{method_log_prefix} Deleted package {harvest_object.package_id} with guid {harvest_object.guid}')
        else:
            log.info(f'{method_log_prefix} Harvest_object with guid {harvest_object.guid} has not package_id {harvest_object.package_id}')
    except p.toolkit.ObjectNotFound:
        log.info(f'Package {harvest_object.package_id} already deleted.')
    
    # Mark the rest of objects for this guid as not current
    model.Session.query(HarvestObject) \
                        .filter_by(guid=harvest_object.guid) \
                        .update({'current': False}, False)
    return True

@log_debug
def get_graph_uri_for_harvest_object(harvest_object: HarvestObject) -> str:
    '''
    Get the graph uri for a harvest object
    
    :param harvest_object: harvest_object
    :type harvest_object: HarvestObject
    
    :return graph uri
    :rtype: str
    '''
    harvest_job = model.Session.query(HarvestJob) \
        .filter(HarvestJob.id == harvest_object.harvest_job_id) \
        .first()
    graph_uri =  generate_graph_uri_from_job(harvest_job)
    return graph_uri

@log_debug
def process_dataset_before_finish_import_stage(package: model.Package, harvest_object: HarvestObject):
    """
    Provess datasets before finish import_stage to replace harvest objects id with ckan uris in servedByDataservice and accessService metadata

    :param package: package to update
    :type package: model.Package
    
    :param harvest_object: harvest object that is being processed
    type harvest_object: Harvest Object
    """
    object_type = CommonPackageConstants.KEY_TYPE_DATASET_VALUE

    # update servedByDataservice property
    served_by_dataservices = package.get(DatasetConstants.KEY_DATASET_SERVED_BY_DATASERVICE)
    package[DatasetConstants.KEY_DATASET_SERVED_BY_DATASERVICE] = _get_related_dataservices_data_from_harvest_object_ids(harvest_object, served_by_dataservices, 'dataset', object_type)
    
    # update accessService in each resource
    resources = package.get(DatasetConstants.KEY_RESOURCES, [])
    for resource in resources:
        access_services = resource.get(DistributionConstants.KEY_DISTRIBUTION_ACCESS_SERVICE, [])
        resource[DistributionConstants.KEY_DISTRIBUTION_ACCESS_SERVICE] = _get_related_dataservices_data_from_harvest_object_ids(harvest_object, access_services, 'distribution', object_type)


def _get_related_dataservices_data_from_harvest_object_ids(harvest_object, ho_id_list:List[str], associated_entity:str, object_type) -> List[str]:
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    results = []
    for ho_id in ho_id_list or []:
        if not ho_id:
            continue
        ho = model.Session.query(HarvestObject) \
                .filter(HarvestObject.id == ho_id) \
                .first()
        if (ho and ho.current == True and ho.package_id != None):
            result = model.Session.query(model.PackageExtra.value) \
                            .join(model.Package) \
                            .filter(model.PackageExtra.key == 'ckan_uri') \
                            .filter(model.Package.id == ho.package_id) \
                            .filter(model.Package.state == 'active') \
                            .first()
            if result and result[0]:
                results.append(result[0])
        else:
            log.warning(f'Could not find the current data service (package_id) associated with Harvest_object {ho_id}')
            warning = HarvesterConstants.IMPORT_WARNING.format(object_type, f"The data service associated with the {associated_entity} could not be found")
            log.warning(f"{method_log_prefix} Saving objectError {warning} for harvest_object_guid {harvest_object.guid}")
            _save_object_error(warning, harvest_object, )
    return results

@log_debug
def build_triples_of_catalog_record_and_lineage(catalog, old_package_uri, new_package_uri, created_datetime , modified_datetime, conforms_to_uri) ->  List[Tuple[URIRef, URIRef, URIRef]]:
    """
    Build triples of catalog record and lineage of a dataset or dataservie

    :param catalog: catalog to add triples
    :type catalog: str
    
    :param old_package_uri: package uri in source
    :type old_package_uri: str
    
    :param new_package_uri: package uri in ckan
    :type new_package_uri: str
    
    :param created_datetime: created datetime of the package in ckan
    :type created_datetime: datetime
    
    :param modified_datetime: modified datetime of the package in ckan
    :type modified_datetime: datetime
    
    :param conforms_to_uri: uri of the package rule
    :type conforms_to_uri: str

    :returns: List of triples to add with the catalogRecord object and lineage
    :rtype: List[Tuple[URIRef, URIRef, URIRef]]
    """    
    triples = []
    record_uriref = URIRef(f'{new_package_uri}{CommonPackageConstants.CATALOG_RECORD_URI_SUFFIX}')
    triples.append((URIRef(str(catalog)), DCAT.record, record_uriref))
    triples.append((record_uriref, RDF.type, DCAT.CatalogRecord))
    triples.append((record_uriref, FOAF.primaryTopic, URIRef(new_package_uri)))
    timezone = h.get_display_timezone()
    if modified_datetime:
        triples.append((record_uriref, DCT.modified, Literal(modified_datetime.astimezone(timezone).isoformat(), datatype=XSD.dateTime)))
    if created_datetime:
        triples.append((record_uriref, DCT.issued, Literal(created_datetime.astimezone(timezone).isoformat(), datatype=XSD.dateTime)))
    if conforms_to_uri:
        triples.append((record_uriref, DCT.conformsTo, URIRef(conforms_to_uri)))
    # add lineage
    triples.append((record_uriref, DCT.identifier, URIRef(old_package_uri)))
    triples.append((URIRef(new_package_uri), SKOS.closeMatch, URIRef(old_package_uri)))
    return triples

@log_info
def delete_package_in_rdf_store(object_type:str, rdf_store:RDFStoreDelete, harvest_object:HarvestObject, uri:str):
    """
    Delete package in rdf store

    object_type: object type 
    object_type: str 
    
    rdf_store: RDS Store to delete data 
    rdf_store:  RDFStoreDelete
    
    harvest_object: Harvest object
    harvest_object: HarvestObject
    
    uri: object/package uri
    uri: str 
    """
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    log.debug(f'{method_log_prefix}. Deleting package with uri {uri} in graph {rdf_store.graph_uri}')
    deleted_object = False
    if not uri:
        return
    if object_type and object_type == CommonPackageConstants.KEY_TYPE_DATASERVICE_VALUE:
        rdf_store.delete_dataservice_in_graph(uri)
        deleted_object = True
        _save_object_error(HarvesterConstants.DELETE_DATASERVICE.format(uri), harvest_object)
    if object_type and object_type == CommonPackageConstants.KEY_TYPE_DATASET_VALUE:
        rdf_store.delete_dataset_in_graph(uri)
        deleted_object = True
        _save_object_error(HarvesterConstants.DELETE_DATASET.format(uri), harvest_object)
    if deleted_object:
        rdf_store.drop_all_unreferenced_nodes()

@log_info
def import_existing_package(existing_package, package, harvest_object, harvest_object_extras, context):
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    object_type = package.get('type', 'unknown')        
    IMPORT_STAGE = 'Import'
    harvest_object_guid = harvest_object.guid
    package_plugin = lib_plugins.lookup_package_plugin(package.get('type', None))
    package_schema = package_plugin.update_package_schema()
    for harvester in p.PluginImplementations(IDCATRDFHarvester):
        package_schema = harvester.update_packagHoe_schema_for_update(package_schema)
    context['schema'] = package_schema
    
    # Don't change the package name even if the title has
    package[CommonPackageConstants.KEY_NAME] = existing_package[CommonPackageConstants.KEY_NAME]
    package[CommonPackageConstants.KEY_ID] = existing_package[CommonPackageConstants.KEY_ID]
        
    # check if resources already exist based on their URI
    existing_resources =  existing_package.get(DatasetConstants.KEY_RESOURCES)
    resource_mapping = {r.get('uri'): r.get('id') for r in existing_resources if r.get('uri')}
    for resource in package.get('resources'):
        res_uri = resource.get('uri')
        if res_uri and res_uri in resource_mapping:
            resource['id'] = resource_mapping[res_uri]

    try:
        if package:
            _update_harvest_object_and_info(package, harvest_object, harvest_object_extras, object_type)
            log.debug(f'{method_log_prefix} Updating existing {object_type}')
            p.toolkit.get_action('package_update')(context, package)
        else:
            log.info(f'Ignoring {object_type} {existing_package["name"]}' )
            return 'unchanged'
    except p.toolkit.ValidationError as e:
        error = HarvesterConstants.IMPORT_ERROR.format(object_type, f'Update validation Error: {str(e.error_summary)}')
        log.error(f"{method_log_prefix} Error saving objectError {error} for harvest_object_guid {harvest_object_guid}", exc_info=True)
        _save_object_error(error, harvest_object, IMPORT_STAGE)
        return False

    log.info(f'{method_log_prefix} Updated {object_type} {package.get(CommonPackageConstants.KEY_NAME)}')
    return True

def _update_harvest_object_and_info(package, harvest_object, harvest_object_extras, object_type):
    package_ckan_uri = None
    if object_type == 'dataset':
        package_ckan_uri = dge_harvest_dataset_uri(package)
    elif object_type == 'dataservice':
        package_ckan_uri = dge_harvest_dataservice_uri(package)
        
    for extra in package[CommonPackageConstants.KEY_EXTRAS]:
        if extra['key'] == CommonPackageConstants.KEY_EXTRAS_CKAN_URI:
            extra['value'] =  package_ckan_uri
            break
    # Save reference to the package on the object
    harvest_object.package_id = package[CommonPackageConstants.KEY_ID]
    harvest_object.add()
    
    # Update ckan_uri in harvest_object_extra
    for harvest_object_extra in harvest_object_extras or []:
        if harvest_object_extra.key == HOEKeyConstants.HOE_CKAN_URI_KEY:
            harvest_object_extra.value = package_ckan_uri
        elif harvest_object_extra.key == HOEKeyConstants.HOE_CKAN_NAME_KEY:
            harvest_object_extra.value = package.get('name', None)
        harvest_object_extra.add()

@log_info
def import_new_package(package, harvest_object, harvest_object_extras, context):
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    object_type = package.get('type', 'unknown')
    IMPORT_STAGE = 'Import'
    harvest_object_guid = harvest_object.guid
    log.debug(f'{method_log_prefix} New {object_type} object')
    package_schema = logic.schema.default_create_package_schema()
    for harvester in p.PluginImplementations(IDCATRDFHarvester):
        package_schema = harvester.update_package_schema_for_create(package_schema)
    context['schema'] = package_schema

    # We need to explicitly provide a package ID
    package[CommonPackageConstants.KEY_ID] = str(uuid.uuid4())
    package_schema[CommonPackageConstants.KEY_ID] = [unicode_safe]

    harvester_tmp_dict = {}

    name = package[CommonPackageConstants.KEY_NAME]
    for harvester in p.PluginImplementations(IDCATRDFHarvester):
        harvester.before_create(harvest_object, package, harvester_tmp_dict)
    try:
        if package:
            # Save reference to the package on the object
            harvest_object.package_id = package[CommonPackageConstants.KEY_ID]
            harvest_object.add()
            _update_harvest_object_and_info(package, harvest_object, harvest_object_extras, object_type)
            
            # Defer constraints and flush so the dataset can be indexed with
            # the harvest object id (on the after_show hook from the harvester
            # plugin)
            model.Session.execute(sa.text('SET CONSTRAINTS harvest_object_package_id_fkey DEFERRED'))
            model.Session.flush()
            log.debug(f'{method_log_prefix} Creating new {object_type} object: {package}')
            p.toolkit.get_action('package_create')(context, package)
            log.debug(f'{method_log_prefix} Created {object_type} new object')
        else:
            log.info(f'Ignoring {object_type} {name}')
            return 'unchanged'
    except (p.toolkit.ValidationError, Exception) as e:
        log.error(f'{method_log_prefix} Create validation Error {type(e)}: {str(e)} for harvest_object_guid {harvest_object_guid}', exc_info=True)
        error = HarvesterConstants.IMPORT_ERROR.format(object_type, f'Create validation Error: {str(e)}')
        _save_object_error(error, harvest_object, IMPORT_STAGE)
        return False
    for harvester in p.PluginImplementations(IDCATRDFHarvester):
        err = harvester.after_create(harvest_object, package, harvester_tmp_dict)
        if err:
            _save_object_error('RDFHarvester plugin error: %s' % err, harvest_object, IMPORT_STAGE)
            return False
    log.info(f'{method_log_prefix} Created {object_type} {package.get(CommonPackageConstants.KEY_NAME)}')
    return True


@log_info
def add_dataset_or_dataservice_in_target_graph_from_source_graph(harvest_object:HarvestObject, 
                                                                 node_uri_in_source_graph: str, source_graph_name:str, 
                                                                 target_graph_name:str, catalog_uri_in_target_graph:str,
                                                                 conforms_to_uri:str, rdf_store:RDFStoreComplete) -> None:
    '''
    Add metadata of a new dataset or dataservice in source graph from data in the current job graph
    
    :param harvest_object: Harvest object that contains info of the dataset or dataservice
    :type harvest_object: HarvestObject
    
    :param source_graph_name: graph name that contains data to add
    :type source_graph_name
    
    :str:param node_uri_in_source_graph:  URI of dataset or dataservice node in the source_graph_name graph
    :type node_uri_in_source_graph: str
    
    :param target_graph_name: graph name where to copy the data
    :type target_graph_name: str
    
    :param catalog_uri_in_target_graph:  URI of root catalog in target_graph_name graph
    :type catalog_uri_in_target_graph: str
    
    :param conforms_to_uri:  URI to complete metadata conforms_to of catalog record
    :type conforms_to_uri: str
    
    :param rdf_store: object to access to rdf store 
    :type rdf_store: RDFStoreComplete 
    '''
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    rdf_store = RDFStoreComplete(source_graph_name) if not rdf_store else rdf_store
    rdf_store.rdf_store_query.update_graph_uri(source_graph_name)
    _node_uri_in_source_graph = str(node_uri_in_source_graph) if node_uri_in_source_graph else None
    # get catalog data from root_catalog in job_graph_name
    package_uri, source_package_uri, package_type, package_dict = _get_package_info(harvest_object, True)
    right_node_uri_in_source_graph = (_node_uri_in_source_graph and 
                                      (package_uri == _node_uri_in_source_graph or source_package_uri == _node_uri_in_source_graph))
    right_package_type = (package_type and (package_type == CommonPackageConstants.KEY_TYPE_DATASET_VALUE 
                            or package_type == CommonPackageConstants.KEY_TYPE_DATASERVICE_VALUE))
    if not (right_node_uri_in_source_graph and package_uri and right_package_type):
        warning_message = "wrong node in source graph" if not right_node_uri_in_source_graph else ""
        warning_message += f"{' ' if warning_message != '' else ''}{'wrong type' if not right_package_type else ''}"
        warning_message += f"{' ' if warning_message != '' else ''}{'no ckan package' if not package_uri else ''}"
        log.warning(f'{method_log_prefix} Node {_node_uri_in_source_graph} not added in graph {target_graph_name} because {warning_message}')
        return
    package_graph = rdf_store.rdf_store_query.get_complete_node(_node_uri_in_source_graph, None)
    if not package_graph or len(package_graph) == 0:
        log.warning(f'{method_log_prefix} Node {_node_uri_in_source_graph} not added in graph {target_graph_name} because no info was found for this node in graph {source_graph_name}')
        return
    if package_type == CommonPackageConstants.KEY_TYPE_DATASET_VALUE:
        _add_complete_dataset_data(package_dict, rdf_store, package_graph, _node_uri_in_source_graph)
    
    # add reference in catalog
    _catalog_uri = rdf_store.rdf_store_query._get_uriref_from_str_value(catalog_uri_in_target_graph)
    _package_uri = rdf_store.rdf_store_query._get_uriref_from_str_value(package_uri)
    _predicate = rdf_store.rdf_store_query._get_uriref_from_str_value(DCAT.dataset if package_type == CommonPackageConstants.KEY_TYPE_DATASET_VALUE else DCAT.service)
    package_graph.add((_catalog_uri, _predicate, _package_uri))
    
    # confirm that package_uri is not in target catalog_uri (mainly in aborted job)
    rdf_store.update_graph_uri(target_graph_name)
    catalogs = rdf_store.rdf_store_query.get_catalogs_where_a_dataset_or_dataservice_is_referenced(_package_uri)
    if catalogs and len(catalogs) > 0:
        log.warning(f'{method_log_prefix} Node {_node_uri_in_source_graph} already been previously added to target graph {target_graph_name}. Node data will not be added from soruce graph {source_graph_name}')
        return
    
    # build and add catalog record
    metadata_created, metadata_modified = model.Session.query(model.Package.metadata_created,  \
    model.Package.metadata_modified) \
        .filter(model.Package.id == harvest_object.package_id) \
        .first()
                
    triples = build_triples_of_catalog_record_and_lineage(catalog_uri_in_target_graph, source_package_uri, package_uri, metadata_created, metadata_modified, conforms_to_uri)
    for triple in triples:
        package_graph.add(triple)
    # insert new catalog data 
    rdf_store.update_graph_uri(target_graph_name)
    rdf_store.rdf_store_insert_or_update.insert_rdf_data(package_graph)
    # update possible references to the dataset or dataservice
    if source_package_uri != package_uri:
        rdf_store.rdf_store_insert_or_update.replace_uriRef_value(source_package_uri, package_uri)
    # update other references 
    rdf_store.rdf_store_insert_or_update.update_references_between_dataset_dataservices_distribution_nodes()
    rdf_store.update_graph_uri(source_graph_name)

def _add_complete_dataset_data(package_dict: dict, rdf_store:RDFStoreComplete, package_graph: Graph, node_uri_in_source_graph):
    distrib_source_uri_distrib_target_uri = _get_distribution_info_dict(package_dict)
    _node_uriref_in_source_graph = rdf_store.rdf_store_query._get_uriref_from_str_value(node_uri_in_source_graph)
    for predicate in [DCAT.distribution, ADMS.sample]:
        for s, p, distribution in package_graph.triples((_node_uriref_in_source_graph, predicate, None)):
            # update distribution uri reference in dataset
            target_distrib_uri = distrib_source_uri_distrib_target_uri.get(str(distribution))
            if target_distrib_uri:
                target_distrib_uri = rdf_store.rdf_store_query._get_uriref_from_str_value(target_distrib_uri)
                package_graph.remove((s, p, distribution))
                package_graph.add((s, p, target_distrib_uri))
            # add distribution graph and update distribution uri in graph
            distribution_graph = _add_complete_distribution_data(rdf_store, distribution, target_distrib_uri)
            if distribution_graph and len(distribution_graph) > 0:
                package_graph += distribution_graph

def _get_distribution_info_dict(package_dict: dict):
    resources = package_dict.get(CommonPackageConstants.KEY_RESOURCES)
    distrib_source_uri_distrib_target_uri = {}
    for resource in resources:
        if resource:
            source_distrib_uri = resource.get(DistributionConstants.KEY_DISTRIBUTION_SOURCE_URI)
            ckan_distrib_uri = dge_harvest_resource_uri(resource, package_dict)
            if source_distrib_uri and ckan_distrib_uri:
                distrib_source_uri_distrib_target_uri[source_distrib_uri] = ckan_distrib_uri
    return distrib_source_uri_distrib_target_uri

def _add_complete_distribution_data(rdf_store:RDFStoreComplete, distribution, target_distrib_uri):
    distribution_graph = rdf_store.rdf_store_query.get_complete_node(str(distribution), None)
    _distribution_uriref = rdf_store.rdf_store_query._get_uriref_from_str_value(distribution)
    if distribution_graph and len(distribution_graph) > 0 and target_distrib_uri:
        for s, p, o in distribution_graph.triples((_distribution_uriref, None, None)):
            distribution_graph.remove((s,p,o))
            distribution_graph.add((target_distrib_uri, p, o))
    return distribution_graph

@log_info
def copy_from_old_harvester_graph_not_conforms_packages(guids_list, source_graph_name, target_graph_name, catalog_uri_in_target_graph,conforms_to_uri, rdf_store):
    for guid in guids_list or []:
        previous_object = model.Session.query(HarvestObject)\
            .filter(HarvestObject.guid == guid) \
            .filter(HarvestObject.current == True)\
            .first()

        if previous_object:
            for extra in previous_object.extras or []:
                if extra.key == HOEKeyConstants.HOE_CKAN_URI_KEY:
                    hoe_ckan_uri = extra.value
                    add_dataset_or_dataservice_in_target_graph_from_source_graph(previous_object, 
                                                                 hoe_ckan_uri, source_graph_name, 
                                                                 target_graph_name, catalog_uri_in_target_graph,
                                                                 conforms_to_uri, rdf_store)
                    break