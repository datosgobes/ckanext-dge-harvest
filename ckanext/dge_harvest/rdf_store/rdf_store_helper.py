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
import inspect
from typing import List, Tuple
from treelib import Tree
from treelib.exceptions import (
    NodeIDAbsentError,
    DuplicatedNodeIdError,
    MultipleRootError
)
from SPARQLWrapper import POST, GET,  JSON, QueryResult
from urllib.error import HTTPError
from rdflib import URIRef
from ..constants.dcat_ap_es_constants import DCAT, RDF_NAMESPACE, DCT, FOAF, DcatClassNameEnum
from .rdf_store import RDFStore, RDFStoreException, RDFStoreInternalException
from ..decorators import log_debug

log = logging.getLogger(__name__)
class RDFStoreHelper(RDFStore):
    '''
    Class that contains utils method to store and get info from graphs in virtuoso
    '''
    @log_debug
    def get_root_catalog_uri(self) -> str:
        '''
        Get the root catalog in the graph of the object

        :return catalog_uri
        :rtype: str

        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            tree = self._get_hierarchical_catalog_tree()
            root_catalog_uri =  tree.root if tree else None
        except RDFStoreInternalException as e:
            log.error(f'{method_log_prefix} Exception getting root catalog uri. Exception{type(e): str(e)}')
            raise self._get_raise_exception(e)
        return root_catalog_uri   

    def _get_hierarchical_catalog_tree(self)-> Tree:
        '''
        Get the hierarchical catalog tree in the graph of the object

        :return: Tree of catalogs in graph
        :rtype: Tree

        :raise RDFStoreInternalException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        tree = None
        root_catalog = None
        try:
            children_catalog_dict = {}        
            catalogs = set(self._get_subjects_by_predicate_and_object(predicate_value=RDF_NAMESPACE.type, object_value=DCAT.Catalog, distinct=True))
            subcatalogs = set()
            for catalog_uri in catalogs:
                children = set(self._get_direct_subcatalogs_from_a_catalog_in_graph(catalog_uri))
                children_catalog_dict.setdefault(catalog_uri, set()).update(children)
                subcatalogs.update(children)
            if catalogs:
                root_catalog = (catalogs - subcatalogs).pop()
            
                tree = Tree()
                tree.create_node(tag=root_catalog, identifier=root_catalog)
                # pending nodes
                pending_nodes = {}
                def add_node(catalog, parent_catalog):
                    if tree.contains(parent_catalog):
                        tree.create_node(tag=catalog, identifier=catalog, parent=parent_catalog)
                        # process pending nodes
                        if catalog in pending_nodes:
                            for item in pending_nodes[catalog]:
                                add_node(item, catalog)
                            del pending_nodes[catalog]
                    else:
                        pending_nodes.setdefault(parent_catalog, set()).add(catalog)
                for catalog, subcatalog_items in children_catalog_dict.items():
                    for item in subcatalog_items:
                        add_node(item, catalog)
        
        except (OSError, DuplicatedNodeIdError, MultipleRootError, NodeIDAbsentError) as e:
            log.error(f'{method_log_prefix} Exception building hierarchical catalog tree. Exception{type(e): str(e)}') 
            raise RDFStoreInternalException(f'The catalog tree structure is wrong. {str(e)}')
        return tree

    def _get_direct_subcatalogs_from_a_catalog_in_graph(self, catalog_uri: str, distinct: bool=True) -> List[str]:
        '''
        Get direct subcatalogs for specific catalog in a graph taking into account properties: dct:hasPart and dct:isPartOf

        :param catalog_uri: catalog_uri
        :type catalog_uri: str

        :param distinct: True if get distinct objects, False if other case
        :type distinct: bool

        :return: List of subcatalogs_uris
        :rtype: List[str]

        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph = self.get_graph_uri_to_query()
        result_uris = []
        if catalog_uri:
            catalog_uri_uriref = URIRef(catalog_uri)
            try:
                query = f'''SELECT{' DISTINCT' if distinct else ''} ?subcatalog FROM {graph} WHERE {{ 
                {{ {self._get_uriref_to_query(catalog_uri_uriref)} {self._get_uriref_to_query(DCT.hasPart)} ?subcatalog }}
                UNION
                {{ ?subcatalog {self._get_uriref_to_query(DCT.isPartOf)} {self._get_uriref_to_query(catalog_uri_uriref)} }}
                ?subcatalog {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Catalog)}
                }}'''
                results = self._set_execute_and_convert_sparql_query_to_virtuoso(query=query, method=GET, return_format=JSON)
                for result in results["results"]["bindings"]:
                    result_uris.append(result['subcatalog']['value'])
            except (RDFStoreInternalException) as e:
                log.error(f'{method_log_prefix} An exception has occurred getting direct subcatalogs of catalog_uri={catalog_uri} in graph {graph}. {type(e).__name__}: {str(e)}')
                raise RDFStoreInternalException(str(e))
        log.debug(f'{method_log_prefix} End method. Result = {result_uris}')
        return result_uris

    @log_debug
    def drop_graph(self) -> QueryResult:
        '''
        Drop the graph_uri graph

        :return: QueryResult
        :rtype: :class:`QueryResult` instance

        :raise: RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        result = None
        try:
            query = f"DROP SILENT GRAPH {graph_uri}"
            result = self._set_and_execute_sparql_query_to_virtuoso(query=query, method=POST, return_format=None)
            log.info(f'{method_log_prefix} Dropped graph {graph_uri}.')
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred dropping graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        return result

    @log_debug
    def clear_graph(self) -> QueryResult:
        '''
        Clear the graph_uri graph

        :return: QueryResult
        :rtype: :class:`QueryResult` instance

        :raise: RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        result = None
        try:
            query = f"CLEAR GRAPH {graph_uri}"
            result = self._set_and_execute_sparql_query_to_virtuoso(query=query, method=POST, return_format=None)
            log.info(f'{method_log_prefix} Cleared graph {graph_uri}.')
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred clearing graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        return result

    def _drop_triples_in_graph(self, triples_to_delete:List[Tuple[str, str, str]]) -> QueryResult:
        '''
        Drop triples in the graph_uri graph

        :param triples_to_delete: List of triples to delete
        :type triples_to_delete: List[Tuple[str, str, str]]

        :return: QueryResult
        :rtype: :class:`QueryResult` instance
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        def _drop_triples(batch_size):
            if triples_to_delete:
                total_batch = len(triples_to_delete) // batch_size + 1
                for i in range(0, len(triples_to_delete), batch_size):
                    batch_number = i // batch_size + 1
                    current_triples_to_delete = triples_to_delete[i:i+batch_size]
                    triples = '\n'.join(f'{s} {p} {o} .' for s, p, o in current_triples_to_delete)
                    query = f'''DELETE {{ GRAPH {graph_uri} {{ {triples} }} }} WHERE {{GRAPH {graph_uri} {{ {triples} }} }}'''
                    log.info(f'{method_log_prefix} Deleting triples in batch... {batch_number}/{total_batch}. \n query={query}')
                    return self._set_and_execute_sparql_query_to_virtuoso(query=query, method=POST, return_format=None)
        BATCH_SIZE = RDFStore.BATCH_SIZE_FOR_DELETES
        MIN_BATCH_SIZE = RDFStore.BATCH_SIZE_FOR_DELETES_MIN
        graph_uri = self.get_graph_uri_to_query()
        result = None
        try:
            result = _drop_triples(BATCH_SIZE)
        except RDFStoreInternalException:
            log.warning(f'{method_log_prefix} Error trying to delete triples in batches of size {BATCH_SIZE}. Trying to delete in batches of size {MIN_BATCH_SIZE}. ')
            result = _drop_triples(MIN_BATCH_SIZE)
        return result

    def _get_undescribed_datasets_or_dataservices_in_a_catalog(self, dcat_class_name:DcatClassNameEnum) -> List[str]:
        '''
        Get URIs of undescribed dataservices in a catalog (metadata DCAT.dataservice in Catalog) 

        :param dcat_class_name: Name of dcat class name. Only DATASET or DATASERVICE are expected values.
        :type dcat_class_name: DcatClassNameEnum

        :return: List of objects uri 
        :rtype: List[str]
        '''
        graph_uri = self.get_graph_uri_to_query()
        result_uris = [] 
        if dcat_class_name and (dcat_class_name == DcatClassNameEnum.DATASET or dcat_class_name == DcatClassNameEnum.DATASERVICE):
            if dcat_class_name == DcatClassNameEnum.DATASET:
                object_name ='dataset_1' 
                query = f'''
                    SELECT DISTINCT ?{object_name} FROM {graph_uri} WHERE {{ 
                        ?catalog_1 {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Catalog)} . 
                        ?catalog_1 {self._get_uriref_to_query(DCAT.dataset)} ?{object_name} .
                        FILTER NOT EXISTS {{ ?{object_name} {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Dataset)} .}}
                        }}
                    '''
            else:
                object_name ='dataservice_1' 
                query = f'''
                    SELECT DISTINCT ?{object_name} FROM {graph_uri} WHERE {{ 
                    ?catalog_1 {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Catalog)} . 
                    ?catalog_1 {self._get_uriref_to_query(DCAT.service)} ?{object_name} .
                    FILTER NOT EXISTS {{ ?{object_name} {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.DataService)} .}}
                    }}
                '''
            result_uris = self.get_objects_by_query(query, object_name)
        return result_uris

    def _get_undescribed_dataservices_in_a_distribution(self) -> List[str]:
        '''
        Get URIs of undescribed dataservices in a distribution (metadata DCAT.accessService in Distribution)

        :return: List of objects uri 
        :rtype: List[str]
        '''
        graph_uri = self.get_graph_uri_to_query()
        result_uris = []
        object_name ='dataservice_1' 
        query = f'''
            SELECT DISTINCT ?{object_name} FROM {graph_uri} {{ 
                ?catalog_1 {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Catalog)} . 
                ?catalog_1 {self._get_uriref_to_query(DCAT.dataset)} ?dataset_1 .
                ?dataset_1 {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Dataset)} . 
                ?dataset_1 {self._get_uriref_to_query(DCAT.distribution)} ?distribution_1 . 
                ?distribution_1 {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Distribution)} .
                ?distribution_1 {self._get_uriref_to_query(DCAT.accessService)} ?{object_name} . 
                FILTER NOT EXISTS {{ ?{object_name} {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.DataService)} .}}
                }}
            '''
        result_uris = self.get_objects_by_query(query, object_name)
        return result_uris

    @log_debug
    def get_catalog_records_triples_of_a_dataset_or_a_dataservice(self, dataset_or_dataservice_uri: URIRef) -> List[Tuple[URIRef, URIRef, URIRef]]:
        '''
        Get triples of catalog record where a dataset or dataservice is referenced in foaf:primarytopic
        
        :param dataset_or_dataservice_uri: dataset or dataservice uri
        :type dataset_or_dataservice_uri: URIRef
        
        :return: The of catalog record where a dataset or dataservice is referenced in foaf:primarytopic n
        :rtype: List[Tuple[URIRef, URIRef, URIRef]]

        :raise: RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        query = None
        triples = []
        try:
            if dataset_or_dataservice_uri:
                query = f'''SELECT DISTINCT ?catalog_uri ?record_uri FROM {graph_uri} WHERE {{
                                ?catalog_uri {self._get_uriref_to_query(DCAT.record)} ?record_uri .
                                ?record_uri {self._get_uriref_to_query(FOAF.primaryTopic)} {self._get_uriref_to_query(dataset_or_dataservice_uri)} . }}'''
                results = self._get_results_by_query(query=query)
                triples = [(f"{self._get_uriref_to_query(result['catalog_uri']['value'])}", 
                            f'{self._get_uriref_to_query(DCAT.record)}', 
                            f"{self._get_uriref_to_query(result['record_uri']['value'])}")  for result in results or []]
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred finding the catalog records where the dataset or dataservice with uri {dataset_or_dataservice_uri} is the foaf:primarytopic in graph_uri={graph_uri}.')
            raise self._get_raise_exception(e)
        return triples

    def _get_undescribed_datasets_in_a_dataservice(self) -> List[str]:
        '''
        Get URIs of undescribed datasets in a dataservice (metadata DCAT.servesDataset in Dataset)
        
        :return: List of objects uri 
        :rtype: List[str]
        '''
        graph_uri = self.get_graph_uri_to_query()
        object_name ='dataset_1' 
        query = f'''
            SELECT DISTINCT ?{object_name} FROM {graph_uri} WHERE {{ 
                ?catalog_1 {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Catalog)} . 
                ?catalog_1 {self._get_uriref_to_query(DCAT.service)} ?dataservice_1 .
                ?dataservice_1 {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.DataService)} . 
                ?dataservice_1 {self._get_uriref_to_query(DCAT.servesDataset)} ?{object_name} . 
                FILTER NOT EXISTS {{ ?{object_name} {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Dataset)} .}}
                }}
            '''
        result_uris = self.get_objects_by_query(query, object_name)
        return result_uris

    def check_if_there_are_entities_in_graph(self, entities_types:List[URIRef]) -> bool:
        '''
        Checks if the graph has at least one entity of any of the indicated types
        
        :param entities_types: List of entity types
        :param entities_types: List[URIRef]
        
        :return: True if there are at least one entity, False in other case
        :rtype: bool
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        query = None
        result = False
        try:
            if entities_types and len(entities_types) > 0:
                _triples = [f'{{ ?subject {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(entity_type)} . }}' for entity_type in entities_types]
                query = f'''ASK {{ GRAPH {graph_uri} {{ {' UNION '.join(_triples)} }} }}'''
            result = self.get_result_of_ask_query(query)
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred checking if there are entities of types {entities_types} in graph_uri={graph_uri}.')
            raise self._get_raise_exception(e)
        return result