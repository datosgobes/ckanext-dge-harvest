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
from collections import deque

from SPARQLWrapper import GET, RDF as RDF_FORMAT, JSON, TURTLE

from urllib.error import HTTPError
from rdflib import ConjunctiveGraph, Graph, URIRef
from rdflib.exceptions import ParserError
from ..constants.dcat_ap_es_constants import DCAT, RDF_NAMESPACE, FOAF, XSD, ADMS
from ..constants.dcat_ap_es_constants import DcatClassNameEnum, DCATAPESPrefixConstants
from .rdf_store_helper import RDFStoreHelper, RDFStoreException, RDFStoreInternalException
from ..decorators import log_debug, log_info

log = logging.getLogger(__name__)

class RDFStoreQuery(RDFStoreHelper):
    '''
    Class that contains utils method to query data from RDF store (virtuso)
    '''

    @log_debug
    def get_distinct_objects_by_predicate(self, predicate_value: str) -> List[str]:
        '''
        Get objects for specific predicate in a graph

        :param predicate_value: predicate of the triple
        :type predicate_value: str

        :return: List of objects uri
        :rtype: List[str]

        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        log.info(f'{method_log_prefix} Init method. Param predicate_value ={predicate_value}')
        try:
            result_uris = result_uris = self._get_objects_by_subject_and_predicate(None, predicate_value, True)
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred getting distincts data objects by predicate_value ={predicate_value}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        log.info(f'{method_log_prefix} End method. Result = {result_uris}')
        return result_uris

    def get_customized_node(self, node_uri:str, predicates_to_exclude:List[URIRef] = [], node_classes_to_exclude:List[URIRef] = [], predicates_to_include_only_their_type:List[URIRef] = {})-> ConjunctiveGraph:
        '''
        Get complete node from graph_uri graph, except nodes of predicate in exclude_predicates

        :param node_uri: node uri to parse
        :type node_uri: str

        :param predicates_to_exclude: list of URIRef predicates that are filtered in query. 
                                   Example: if exclude_predicates contains http://www.w3.org/ns/dcat#dataset, the query will not get triples whith this predicate
        :type predicates_to_exclude: list[UriRef]

        :param types_of_nodes_to_exclude: list of child node types whose description should not be obtained, e.g. [DCAT.CatalogRecord, DCAT.Catalog]
        :type types_of_nodes_to_exclude: list[UriRef]
        
        :param predicates_to_include_only_their_type: list of predicates of node
                                    Example: If add_type_triple_from_predicates contains the pair 'http://www.w3.org/ns/dcat#servesDataset: http://www.w3.org/ns/dcat#dataset',
                                     a query will retrieve an object using the URI object associated with http://www.w3.org/ns/dcat#servesDataset as the subject and http://www.w3.org/1999/02/22-rdf-syntax-ns#type as the predicate. If the retrieved object matches http://www.w3.org/ns/dcat#dataset, a triple consisting of the subject, predicate and object will be added to result_graph
        :type predicates_to_include_only_their_type: dict[UriRef, URIRef]

        :return: The node graph
        :rtype: :class:`ConjunctiveGraph` instance

        :raise: RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        try:
            node_graph = self.get_complete_node(node_uri, node_classes_to_exclude)
            if predicates_to_exclude:
                for predicate_to_exclude in predicates_to_exclude:
                    triples_to_remove = list(node_graph.triples((self._get_uriref_from_str_value(node_uri), self._get_uriref_from_str_value(predicate_to_exclude), None)))
                    for triple in triples_to_remove:
                        node_graph.remove(triple)
            if predicates_to_include_only_their_type:
                query_filter = "\n".join([f"{self._get_uriref_to_query(pred)}" for pred in predicates_to_include_only_their_type])
                query = f"""CONSTRUCT {{ ?subject {self._get_uriref_to_query(RDF_NAMESPACE.type)} ?object. }}
                            WHERE {{ GRAPH {graph_uri} {{ VALUES ?predicate {{ {query_filter} }}
                            {self._get_uriref_to_query(node_uri)} ?predicate ?subject .
                            ?subject {self._get_uriref_to_query(RDF_NAMESPACE.type)} ?object.
                        }} }}"""
                result_graph = self._set_execute_and_convert_sparql_query_to_virtuoso(query=query, method=GET, return_format=RDF_FORMAT)
                if result_graph:
                    for s, p, o in result_graph:
                        node_graph.add((s, p, o))
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred getting data of {node_uri} from graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        except (ParserError, SyntaxError) as e:
            log.error(f'{method_log_prefix} An exception has occurred getting data of {node_uri} from graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise RDFStoreException(str(e))
        return node_graph

    @log_debug
    def get_complete_node(self, node_uri:str, node_classes_to_exclude:list[URIRef], depth_level:int=4) -> ConjunctiveGraph:
        '''
        Get complete node from current graph_uri graph, except default subnodes of types:
        Catalog, Dataset, Distribution or Dataservice that are referenced in a catalog

        :param node_uri: node uri to parse
        :type node_uri: str

        :param types_of_nodes_to_exclude: list of child node types whose description should not be obtained.
        :type types_of_nodes_to_exclude: list[UriRef]
        
        :param depth_level: depth level. 4 by default
        :type types_of_nodes_to_exclude: integer
        
        :return: The node graph
        :rtype: :class:`ConjunctiveGraph` instance

        :raise: RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        try:
            result_graph = ConjunctiveGraph()
            default_node_classes_to_exclude = [DCAT.Catalog, DCAT.CatalogRecord, DCAT.DataService, DCAT.Dataset, DCAT.Distribution]
            _node_classes_to_exclude = []
            if not node_classes_to_exclude:
               _node_classes_to_exclude = default_node_classes_to_exclude
            else: 
                for node_class in node_classes_to_exclude or []:
                    if isinstance(node_class, URIRef) and node_class not in _node_classes_to_exclude:
                        _node_classes_to_exclude.append(node_class)

            construct_clause = f'{self._get_uriref_to_query(node_uri)} ?p ?s . \n'
            where_clause = f'{self._get_uriref_to_query(node_uri)} ?p ?s . \n '
            prev_var = '?s'
            depth_level = depth_level or 4
            for level in range(depth_level):
                node_var = f'?o{level}'
                construct_clause = f'{construct_clause} {prev_var} ?p{level} {node_var} .\n'
                filter_clause = "".join([f"FILTER NOT EXISTS {{ {prev_var} {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(node_class)} }}\n " for node_class in _node_classes_to_exclude])
                where_clause = f'{where_clause} OPTIONAL {{ {prev_var} ?p{level} {node_var} .\n {filter_clause} '
                prev_var = node_var
            where_clause = f'{where_clause} {"}" * depth_level}'

            query = f'CONSTRUCT {{ {construct_clause} }} WHERE {{ GRAPH {graph_uri} {{ {where_clause} }} }}'
            result_graph = self._set_execute_and_convert_sparql_query_to_virtuoso(query=query, method=GET, return_format=RDF_FORMAT)
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred getting data of {node_uri} from graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        except (ParserError, SyntaxError) as e:
            log.error(f'{method_log_prefix} An exception has occurredgetting data of {node_uri} from graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise RDFStoreException(str(e))
        return result_graph

    @log_debug
    def get_uris_from_referenced_datasets_or_dataservices_in_catalogs_of_a_graph(self, dcat_class_name:DcatClassNameEnum) -> List[str]:
        '''
        Get dataservices uris from dataservices that are referenced in the catalogs of a graph

        :param dcat_class_name: Name of dcat class name. Only DATASET or DATASERVICE are expected values.
        :type dcat_class_name: DcatClassNameEnum

        :return: The list of dataset or datasrvices uris if dcat_class_name is DATASET or DATASERVICE. None in other case.
        :rtype: List[str]

        :raise: RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        result_uris = []
        try:
            if dcat_class_name and dcat_class_name == DcatClassNameEnum.DATASERVICE:
                query = f'''SELECT DISTINCT ?s FROM {graph_uri} WHERE  {{
                            ?s {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.DataService)} .
                            ?catalog {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Catalog)} ; {self._get_uriref_to_query(DCAT.service)} ?s .
                        }}'''
            elif dcat_class_name and dcat_class_name == DcatClassNameEnum.DATASET:
                query = f'''SELECT DISTINCT ?s FROM {graph_uri} WHERE  {{
                            ?s {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Dataset)} .
                            ?catalog {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Catalog)} ; {self._get_uriref_to_query(DCAT.dataset)} ?s .
                        }}'''
            else:
                raise ValueError("Unexpected value. Only DATASET or DATASERVICE are expected values.")
            results = self._set_execute_and_convert_sparql_query_to_virtuoso(query=query, method=GET, return_format=JSON)
            for result in results["results"]["bindings"]:
                result_uris.append(result['s']['value'])
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred getting {dcat_class_name} uris in a catalog of graph_uri={graph_uri}. Exception {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        return result_uris

    @log_debug
    def get_graph(self, offset:int=None) -> ConjunctiveGraph:
        '''
        Get a graph_uri graph and parse in a RDF-xml

        :param offset: the specified number of rows to skip before beginning to return results.
        :type offset: int

        :return: The complete graph
        :rtype: :class:`ConjunctiveGraph` instance

        :raise: RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            result = self.get_and_parse_graph(offset)
            result.serialize(format="pretty-xml").decode("utf-8")
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred getting data from graph. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        return result

    @log_debug
    def get_and_parse_graph(self, offset:int=None) -> ConjunctiveGraph:
        '''
        Get a graph_uri graph and parse in a RDF-xml
        
        :param offset: the specified number of rows to skip before beginning to return results.
        :type offset: int

        :return: The complete graph
        :rtype: :class:`ConjunctiveGraph` instance

        :raise: RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        result = Graph()
        try:
            query = f"CONSTRUCT {{ ?s ?p ?o }} FROM {graph_uri} WHERE {{ ?s ?p ?o }} ORDER BY ?s ?p ?o"
            if self.max_triples_per_query:
                query = f'{query} LIMIT {self.max_triples_per_query}'
            if offset:
                query = f'{query} OFFSET {offset}'
            results = self._set_execute_and_convert_sparql_query_to_virtuoso(query=query, method=GET, return_format='rdf')
            if results:
                graph = ConjunctiveGraph()
                result = graph.parse(data=results.serialize(format='xml'), format='xml')
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred getting data from graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        except (ParserError, SyntaxError) as e:
            log.error(f'{method_log_prefix} An exception has occurred parsing data from graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise RDFStoreException(str(e))
        return result

    @log_debug
    def get_catalogs_where_a_dataset_or_dataservice_is_referenced(self, dataset_or_dataservice_uri:str) -> List[str]:
        '''
        Get catalogs where a dataset or dataservice is referenced (dcat:dataset or dcat:service)
        
        :param dataset_or_dataservice_uri: uri of the dataset or dataservice that has to be referenced in a catalog 
        :type dataset_or_dataservice_uri: str

        :return: The list of catalags uris where de dataset or dataservice is referenced
        :rtype: List[str]

        :raise: RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        query = None
        try:
            query = f"""SELECT DISTINCT ?catalog FROM {graph_uri} WHERE {{
                ?catalog {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Catalog)};  ?p {self._get_uriref_to_query(dataset_or_dataservice_uri)} .
                FILTER (?p IN ({self._get_uriref_to_query(DCAT.dataset)}, {self._get_uriref_to_query(DCAT.service)}))
                }}"""
            result_uris = self.get_objects_by_query(query, 'catalog')
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred finding the catalogs where the dataset or dataservice with uri {dataset_or_dataservice_uri} is referenced in graph_uri={graph_uri}.')
            raise self._get_raise_exception(e)
        return result_uris

    @log_debug
    def get_catalogs_uris_sorted_by_depth_level(self) -> List[str]:
        '''
        Get uri catalogs in a graph sorted by depth level
        
        :return: The list of catalog uris in the graph sorted by depth level 
        :rtype: List[str]

        :raise: RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        catalog_uris = []
        try:
            tree = self._get_hierarchical_catalog_tree()
            queue = deque([tree.get_node(tree.root)])  # Init queue with the root node
            while queue:
                node = queue.popleft()  # Pop the node of the queue
                catalog_uris.append(node.tag)  # Save node name
                # Append node's children to the queue
                for child in tree.children(node.identifier):
                    queue.append(child)
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred getting catalogs uris sorted by depth_level. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        return catalog_uris

    @log_debug
    def get_subcatalogs_uris_of_a_catalog(self, catalog_uri:str) -> List[str]:
        '''
        Get subcatalogs_uris of a catalog from graph
        
        :param catalog_uri: uri of the catalog from which to obtain the subcatalogs
        :type  catalog_uri: str
        
        :return: The list of catalog uris that are subcatalogs of catalog_uri 
        :rtype: List[str]
        
        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        subcatalogs = []
        try:
            tree = self._get_hierarchical_catalog_tree()
            if tree:
                subtree = tree.subtree(catalog_uri)
                subcatalogs = [node.identifier for node in subtree.all_nodes() if node.identifier != catalog_uri]
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred getting subcatalog of a catalog. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        return subcatalogs

    @log_debug
    def get_graphs_names_starting_with_a_prefix(self, prefix:str) -> List[str]:
        '''
        Get graphs names starting with a given prefix
        
        :param prefix: prefix
        :type prefix: str
        
        :return: The list of grpsh names starting with the given prefix
        :rtype: List[str]

        :raise: RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        grahps_names = []
        try:
            if prefix:
                object_name = 'graph_name'
                query = f"""SELECT DISTINCT ?{object_name} WHERE {{ GRAPH ?{object_name} {{ ?s ?p ?o }}
                            FILTER STRSTARTS(STR(?{object_name}), '{prefix}') }}"""
                grahps_names = self.get_objects_by_query(query, object_name)
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred getting catalogs uris sorted by depth_level. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        return grahps_names

    @log_debug
    def get_catalogs_with_europan_theme_taxonomy(self) -> List[str]:
        '''
        Get catalog uris that have the european theme taxonomy

        :return: List of catalogs uri
        :rtype: List[str]

        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph = self.get_graph_uri_to_query()
        result_uris = []
        try:
            object_value_query = f'{self._get_uriref_to_query(DCATAPESPrefixConstants.THEME_EU_PREFIX)}'
            predicate_value_query = f'{self._get_uriref_to_query(str(DCAT.themeTaxonomy))}'
            query = f"SELECT DISTINCT ?s FROM {graph} WHERE {{ ?s {predicate_value_query} {object_value_query} }}"
            results = self._set_execute_and_convert_sparql_query_to_virtuoso(query=query, method=GET, return_format=JSON)
            for result in results["results"]["bindings"]:
                result_uris.append(result['s']['value'])
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred getting catalogs with european theme taxonomy in graph {graph}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        log.info(f'{method_log_prefix} End method. Result = {result_uris}')
        return result_uris

    @log_debug
    def get_entities_with_europan_themes(self) -> List[str]:
        '''
        Get entity (dataset and dataservices) uris that have european themes

        :return: List of catalogs uri
        :rtype: List[str]

        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph = self.get_graph_uri_to_query()
        result_uris = []
        try:
            predicate_value_query = f'{self._get_uriref_to_query(str(DCAT.theme))}'
            query = f"SELECT DISTINCT ?s FROM {graph} WHERE {{ ?s {predicate_value_query} ?o . FILTER (STRSTARTS(STR(?o), '{DCATAPESPrefixConstants.THEME_EU_PREFIX_SLASH}')) }}"
            results = self._set_execute_and_convert_sparql_query_to_virtuoso(query=query, method=GET, return_format=JSON)
            for result in results["results"]["bindings"]:
                result_uris.append(result['s']['value'])
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred getting catalogs with european theme taxonomy in graph {graph}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        log.info(f'{method_log_prefix} End method. Result = {result_uris}')
        return result_uris
        
