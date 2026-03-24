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
import re
from typing import List, Dict, Set
from SPARQLWrapper import POST, GET, JSON, QueryResult
from SPARQLWrapper.SPARQLExceptions import SPARQLWrapperException
from urllib.error import HTTPError
from rdflib import Graph, URIRef
from ..constants.dcat_ap_es_constants import DCAT, RDF_NAMESPACE, DCT, HYDRA, FOAF
from .rdf_store_helper import RDFStoreHelper
from .rdf_store import RDFStoreException, RDFStoreInternalException, RDFStore
from ..decorators import log_debug, log_info

log = logging.getLogger(__name__)

class RDFStoreInsertOrUpdate(RDFStoreHelper):
    '''
    Class that contains utils method to insert data in RDF store
    '''
    def _get_prefix_bnodes(self):
        return str(self.get_graph_uri())

    @log_debug
    def insert_rdf_data(self, rdf_data: Graph) -> QueryResult:
        '''
        Insert into graph graph_uri from virtuoso the rdf_data

        :param rdf_data: rdf data
        :type rdf_data: rdflib.Graph

        :return: QueryResult
        :rtype: :class:`QueryResult` instance

        :raise: RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        def _insert_data(data, batch_size):
            total_batch = len(data) // batch_size + 1
            # Insert triplates in bathes
            for i in range(0, len(data), batch_size):
                batch_number = i // batch_size + 1
                triples_to_insert = []
                duration_triples = []
                duration_values = []
                triples = data[i:i+batch_size]
                # get triples with duration values
                for triple in triples:
                    duration_value = self._check_if_is_triple_nt_with_xsd_duration_value_and_get_duration_value(triple)
                    if not duration_value:
                        triples_to_insert.append(triple)
                    else:
                        duration_triples.append(triple)
                        duration_values.append(duration_value)
                triples_block = "\n".join(triples_to_insert)
                log.debug(f'{method_log_prefix} Inserting batch {batch_number}/{total_batch} of data into graph {graph_uri}')
                # insert triples without duration values
                query = f"""INSERT DATA INTO {graph_uri} {{ {triples_block} }}"""
                result = self._set_and_execute_sparql_query_to_virtuoso(query=query, method=POST, return_format=None)
                # insert triples with duration values, first original and, if error, with complete value
                for duration_triple in duration_triples: 
                    result = self._insert_triple_with_duration_value(graph_uri, duration_triple, duration_values.pop(0))
            return result
            
        graph_uri = self.get_graph_uri_to_query()
        BATCH_SIZE = RDFStore.BATCH_SIZE_FOR_INSERTS
        MIN_BATCH_SIZE = RDFStore.BATCH_SIZE_FOR_INSERTS_MIN
        batch_number = 1
        result = None
        try:
            # replace blank nodes
            rdf_data_without_blank_nodes = self._replace_blank_nodes(rdf_data, self._get_prefix_bnodes())
            encoded_data_to_insert = self._encode_uris_of_graph(rdf_data_without_blank_nodes)
            data = encoded_data_to_insert.serialize(format='nt').splitlines()
            try:
                result = _insert_data(data, BATCH_SIZE)
            except RDFStoreInternalException:
                log.warning(f'{method_log_prefix} Error trying to insert triples in batches of size {BATCH_SIZE}. Trying to insert in batches of size {MIN_BATCH_SIZE}. ')
                result = _insert_data(data, MIN_BATCH_SIZE)
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred inserting batch {batch_number} of data into graph {graph_uri}. {type(e).__name__}: {str(e)}')
            result = None
            raise self._get_raise_exception(e)
        return result

    def _insert_triple_with_duration_value(self, graph_uri, duration_triple, duration_value):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        result = None
        if graph_uri and duration_triple and duration_value:
            try:
                log.info(f'{method_log_prefix} Trying to insert orginal triple with duration value {duration_value}')
                query = f"""INSERT DATA INTO {graph_uri} {{ {duration_triple} }}"""
                result = self._set_and_execute_sparql_query_to_virtuoso(query, method=POST, return_format=None)
            except RDFStoreInternalException as e:
                complete_duration_value = self._complete_all_param_values_of_duration_value(duration_value)
                if complete_duration_value:
                    complete_duration_triple = duration_triple.replace(duration_value, complete_duration_value)
                    log.error(f'{method_log_prefix} Original triple with duration value {duration_value} failed to save. Trying to insert orginal triple with complete duration value {complete_duration_value}')
                    query = f"""INSERT DATA INTO {graph_uri} {{ {complete_duration_triple} }}"""
                    result = self._set_and_execute_sparql_query_to_virtuoso(query, method=POST, return_format=None)
                else:
                    raise e
        return result

    def _insert_triple_into_graph(self, subject_value, predicate_value, object_value) -> QueryResult:
        '''
        Insert a triple into graph in Virtuoso

        :param subject_value: subject of the triple
        :type subject_value: str

        :param predicate_value: predicate of the triple
        :type predicate_value: str

        :param object_value: object of the triple
        :type object_value: str

        :return: QueryResult
        :rtype: :class:`QueryResult` instance
        '''
        graph_uri = self.get_graph_uri_to_query()        
        g = Graph()
        g.add((subject_value, predicate_value, object_value))
        encoded_g = self._encode_uris_of_graph(g)
        triple = encoded_g.serialize(format='nt')
        # check and complete if duration_value
        duration_value = self._check_if_is_triple_nt_with_xsd_duration_value_and_get_duration_value(triple)
        if not duration_value:
            query = f"""INSERT DATA INTO {graph_uri} {{ {triple} }}"""
            result = self._set_and_execute_sparql_query_to_virtuoso(query, method=POST, return_format=None)
        else:
            result = self._insert_triple_with_duration_value( graph_uri, triple, duration_value)
        return result

    @log_debug
    def insert_triples_list_into_graph(self, triples_list) -> List[QueryResult]:
        '''
        Insert a list of triples into graph in Virtuoso

        :param triples_list: list of triples
        :type triples_list: List[str]

        :return: a list of query results
        :rtype: List[:class:`QueryResult` instance]
        
        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        results_list = []
        try:
            for triple in triples_list:
                subject_value, predicate_value, object_value = triple
                result = self._insert_triple_into_graph(subject_value, predicate_value, object_value)
                results_list.append(result)
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred inserting triples into graph. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        return results_list

    def _remove_the_deepest_catalog_uri(self, catalogs:List[str]) -> Set[str]:
        '''
        Get all catalog uris except the deepest catalog uri. 
        If two or more catalogs whith the same depth, select one of them as the deepest and get others.
        
        :param catalog: uriRef of catalogs where node is referenced
        :type first_catalog: list[str]
        
        :return: Set of catalog uris that are not the deepest
        :rtype:  Set[str]
        '''
        max_depth = 0
        selected_catalogs = set()
        deepest_catalog_uri_ref = None
        for catalog in catalogs:
            current_catalog_depth = self._get_hierarchical_catalog_tree().depth(catalog)
            if  current_catalog_depth > max_depth:
                # if this catalog is deeper than current deepest catalog, delete reference in current deepest catalog
                if deepest_catalog_uri_ref:
                    selected_catalogs.add(deepest_catalog_uri_ref)
                deepest_catalog_uri_ref = catalog
                max_depth = current_catalog_depth
            else:
                #  if this catalog is not deeper than current deepest catalog, delete reference in this catalog
                selected_catalogs.add(catalog)
        return selected_catalogs

    def _remove_multiples_node_references(self, multireferenced_nodes:Dict[str, List[str]] = {}, remove_datasets:bool = True) -> Dict[str, List[str]]:
        '''
        For each of the nodes referenced in multiple catalogs, keep a single reference for each node and remove the others
        
        :param multireferenced_nodes: dictionary with node_uris as keys and list of catalog_uris where node_uri is referenced
        :type: dict
        
        :param remove_datasets: True if the multireferenced nodes are datasets, False if they dataservices
        :type query: bool
        
        :return: dictionary whith key = node uri and value = list of catalogs_uri where node_uri was referenced and has been deleted
        :rtype: dict[str, list[str]]
        '''
        triples_to_delete = set()
        references_to_delete = {}
        predicate = f'{self._get_uriref_to_query(DCAT.dataset)}' if remove_datasets else f'{self._get_uriref_to_query(DCAT.service)}'
        for key in multireferenced_nodes.keys() or []:
            selected_catalogs =  self._remove_the_deepest_catalog_uri(multireferenced_nodes.get(key, []))
            for selected_catalog in selected_catalogs or []:
                triples_to_delete.add((f'{self._get_uriref_to_query(selected_catalog)}', predicate, f'{self._get_uriref_to_query(key)}'))
                references_to_delete.setdefault(key, []).append(selected_catalog)
        self._drop_triples_in_graph(list(triples_to_delete))
        return references_to_delete

    def _get_datasets_or_dataservices_referenced_in_several_catalogs(self, get_datasets:bool = True) -> Dict[str, List[str]]:
        '''
        Obtains the datasets or dataservices that are referenced in several catalogs.
        
        :param get_datasets: True if get datasets, False if get dataservices
        :type query: bool
        
        :return: dictionary where keys are dataset_uris, and values are list of catalogs_uri where dataset_uri is refereced
        :rtype: dict[str, list[str]]
        '''
        graph_uri = self.get_graph_uri_to_query()
        subject_name ='catalog_uri' 
        object_name = 'object_uri'
        predicate = DCAT.dataset if get_datasets else DCAT.service
        query = f'''
                SELECT ?{subject_name} ?{object_name} FROM {graph_uri} WHERE {{
                    # Selecciona todas las tripletas con el predicado dado
                    ?{subject_name} {self._get_uriref_to_query(predicate)} ?{object_name} .
                
                    # Group by object (object_name) and count distinct subjects number
                    {{
                        SELECT ?{object_name} (COUNT(DISTINCT ?{subject_name}) AS ?count)
                        FROM {graph_uri} WHERE {{ 
                            ?{subject_name} {self._get_uriref_to_query(predicate)} ?{object_name} .
                        }}
                        GROUP BY ?{object_name}
                        HAVING (COUNT(DISTINCT ?{subject_name}) > 1)
                    }}
                    # Assert than object_name has more than one triple with distinct subjects
                    ?{subject_name} {self._get_uriref_to_query(predicate)} ?{object_name} .
                }}
            '''
        result_query = self._get_results_by_query(query=query)
        result = {} 
        for item in result_query or []:
            result.setdefault(item[object_name]['value'], []).append(item[subject_name]['value'])
        return result

    @log_debug
    def update_graph_to_fullfil_one_dataset_reference_in_a_single_catalog(self) -> Dict[str, List[str]]:
        '''
        Update graph to fullfill the premise 'one dataset in a single_catalog'
        
        :return: dictionary whith key = node uri and value = list of catalogs_uri where node_uri was referenced and has been deleted
        :rtype: dict[str, list[str]]

        :raise: RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            result = self._remove_multiples_node_references(self._get_datasets_or_dataservices_referenced_in_several_catalogs(True), True)
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred updating graph to fullfill one dataset reference in a sible catalog. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        return result

    @log_debug
    def update_graph_to_fullfil_one_dataservice_reference_in_a_single_catalog(self) -> Dict[str, List[str]]:
        '''
        Update graph to fullfill the premise 'one dataservice in a single_catalog'

        :param graph: graph uri
        :type graph: str
        
        :return: dictionary whith key = node uri and value = list of catalogs_uri where node_uri was referenced and has been deleted
        :rtype: dict[str, list[str]]

        :raise: RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            result = self._remove_multiples_node_references(self._get_datasets_or_dataservices_referenced_in_several_catalogs(False), False)
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred updating graph to fullfill one dataset reference in a sible catalog. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        return result

    @log_debug
    def replace_uriRef_value(self, old_uri_ref:str, new_uri_ref:str) -> None:
        '''
        Replace one URIRef with another in a graph.
        
        :param old_uri_ref: uri ref to replace
        :type old_uri_ref: str
        
        :param new_uri_ref: uri to replace with.
        :type new_uri_ref: str

        :return: The complete graph
        :rtype: :class:`ConjunctiveGraph` instance

        :raise: RDFStoreException
        '''
        if old_uri_ref and new_uri_ref and old_uri_ref != new_uri_ref:
            # Query to replace URI in subject
            self._replace_uriRef_value_in_subjects(old_uri_ref, new_uri_ref)
            self._replace_uriRef_value_in_objects(old_uri_ref, new_uri_ref)

    def _replace_uriRef_value_in_subjects(self, old_uri_ref:str, new_uri_ref:str):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        log.info(f'{old_uri_ref != new_uri_ref}')
        if old_uri_ref and new_uri_ref and old_uri_ref != new_uri_ref:
            graph_uri = self.get_graph_uri_to_query()
            query = None
            try:
                # Query to replace URI in subject
                update_subject_query = f"""
                    DELETE {{ GRAPH {graph_uri} {{ {self._get_uriref_to_query(old_uri_ref)} ?p ?o }} }}
                    INSERT {{ GRAPH {graph_uri} {{ {self._get_uriref_to_query(new_uri_ref)} ?p ?o }} }}
                    WHERE {{ GRAPH {graph_uri} {{ {self._get_uriref_to_query(old_uri_ref)} ?p ?o }} }}
                """
                self._set_and_execute_sparql_query_to_virtuoso(query=update_subject_query, method=POST, return_format=None)
            except (RDFStoreInternalException) as e:
                log.warning(f'{method_log_prefix} An exception has occurred replacing the old URIRef {old_uri_ref} with the URIRef {new_uri_ref} in graph {graph_uri} executing the query {query}. {type(e).__name__}: {str(e)}')
                self._replace_uriRef_value_in_subjects_by_predicate(old_uri_ref, new_uri_ref)

    def _replace_uriRef_value_in_subjects_by_predicate(self, old_uri_ref:str, new_uri_ref:str):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        
        def _replace_uris(batch_size):
            total_batch = len(results) // batch_size + 1
            total_resuls = len(results)
            for i in range(0, total_resuls, total_batch):
                predicates = [self._get_uriref_to_query(item['p']['value']) for item in results[i:i+batch_size] ]
                # Query to replace URI in subject
                query = f"""DELETE {{ GRAPH {graph_uri} {{ {_old_uri_ref} ?p ?o }} }}
                            INSERT {{ GRAPH {graph_uri} {{ {_new_uri_ref} ?p ?o }} }}
                            WHERE {{ GRAPH {graph_uri} {{ 
                                {_old_uri_ref} ?p ?o.
                                FILTER (?p in ({','.join(predicates)}))
                                }} }}"""
                self._set_and_execute_sparql_query_to_virtuoso(query=query, method=POST, return_format=None)
                log.info(f'{method_log_prefix} Successfully processed batch with predicates {predicates}')

        log.info(f'{old_uri_ref != new_uri_ref}')
        predicates = []
        query = ''
        if old_uri_ref and new_uri_ref and old_uri_ref != new_uri_ref:
            graph_uri = self.get_graph_uri_to_query()
            try:
                # Query to get a batch of triples
                _old_uri_ref = self._get_uriref_to_query(old_uri_ref)
                _new_uri_ref = self._get_uriref_to_query(new_uri_ref)
                query = f'''SELECT DISTINCT ?p FROM {graph_uri} WHERE {{ {_old_uri_ref} ?p ?o . }}'''
                results = self._get_results_by_query(query)
                # Exit the loop if no more results
                if results:
                    BATCH_SIZE = RDFStore.BATCH_SIZE_FOR_UPDATES
                    MIN_BATCH_SIZE = RDFStore.BATCH_SIZE_FOR_UPDATES_MIN
                    try:
                        _replace_uris(BATCH_SIZE)
                    except RDFStoreInternalException:
                        log.warning(f'{method_log_prefix} Error trying to replace triples in batches of size {BATCH_SIZE}. Trying to replace in batches of size {MIN_BATCH_SIZE}. ')
                        _replace_uris(MIN_BATCH_SIZE)
            except (RDFStoreInternalException) as e:
                log.error(f'{method_log_prefix} An exception has occurred replacing the old URIRef {old_uri_ref} with the URIRef {new_uri_ref} in graph {graph_uri} with predicates = {predicates} executing the query {update_subject_query}. {type(e).__name__}: {str(e)}')
                raise self._get_raise_exception(e)

    def _replace_uriRef_value_in_objects(self, old_uri_ref:str, new_uri_ref:str):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        log.info(f'{old_uri_ref != new_uri_ref}')
        if old_uri_ref and new_uri_ref and old_uri_ref != new_uri_ref:
            graph_uri = self.get_graph_uri_to_query()
            query = None
            try:
               # Query to replace URI in object only in certain predicates 
                predicate_list = [DCAT.service, DCAT.dataset, FOAF.primaryTopic, DCAT.distribution, DCAT.servesDataset, DCAT.accessService]
                predicates = [self._get_uriref_to_query(predicate) for predicate in predicate_list] 
                update_object_query = f"""
                    DELETE {{ GRAPH {graph_uri} {{ ?s ?p {self._get_uriref_to_query(old_uri_ref)} }} }}
                    INSERT {{ GRAPH {graph_uri} {{ ?s ?p {self._get_uriref_to_query(new_uri_ref)} }} }}
                    WHERE {{ GRAPH {graph_uri} {{ 
                    ?s ?p {self._get_uriref_to_query(old_uri_ref)} .
                    FILTER (?p in ({','.join(predicates)}))
                    }} }}
                """
                self._set_and_execute_sparql_query_to_virtuoso(query=update_object_query, method=POST, return_format=None)
            except (RDFStoreInternalException) as e:
                log.warning(f'{method_log_prefix} An exception has occurred replacing the old URIRef {old_uri_ref} with the URIRef {new_uri_ref} in graph {graph_uri} exectuting the query {query}. {type(e).__name__}: {str(e)}')
                self._replace_uriRef_value_in_subjects_by_predicate(old_uri_ref, new_uri_ref)

    def _replace_uriRef_value_in_objects_by_predicate(self, old_uri_ref:str, new_uri_ref:str):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        log.info(f'{old_uri_ref != new_uri_ref}')
        if old_uri_ref and new_uri_ref and old_uri_ref != new_uri_ref:
            graph_uri = self.get_graph_uri_to_query()
            query = None
            try:
               # Query to replace URI in object only in certain predicates 
                predicate_list = [DCAT.service, DCAT.dataset, FOAF.primaryTopic, DCAT.distribution, DCAT.servesDataset, DCAT.accessService]
                predicates = [self._get_uriref_to_query(predicate) for predicate in predicate_list] 
                _old_uri_ref = self._get_uriref_to_query(old_uri_ref)
                _new_uri_ref = self._get_uriref_to_query(new_uri_ref)
                for predicate in predicates:
                    update_object_query = f"""
                        DELETE {{ GRAPH {graph_uri} {{ ?s ?p {_old_uri_ref} }} }}
                        INSERT {{ GRAPH {graph_uri} {{ ?s ?p {_new_uri_ref} }} }}
                        WHERE {{ GRAPH {graph_uri} {{ 
                            ?s {predicate} {self._get_uriref_to_query(old_uri_ref)} .
                        }} }}
                    """
                    self._set_and_execute_sparql_query_to_virtuoso(query=update_object_query, method=POST, return_format=None)
            except (RDFStoreInternalException) as e:
                log.error(f'{method_log_prefix} An exception has occurred replacing the old URIRef {old_uri_ref} with the URIRef {new_uri_ref} in graph {graph_uri} exectuting the query {query}. {type(e).__name__}: {str(e)}')
                raise self._get_raise_exception(e)
    
    @log_debug
    def copy_source_graph_in_target_graph(self, source_graph:str, target_graph:str):
        '''
        Copy all content of source_graph graph in target_graph
        
        :param target_graph: target graph name
        :type target_graph: str

        :raise: RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        query = None
        try: 
            if target_graph and source_graph:
                self.update_graph_uri(target_graph)
                source_graph_to_query = self._get_uriref_to_query(source_graph)
                target_graph_to_query = self._get_uriref_to_query(target_graph)
                ask_query_source_graph = f"""ASK WHERE {{ GRAPH {source_graph_to_query} {{ }} }}"""
                ask_query_target_graph = f"""ASK WHERE {{ GRAPH {target_graph_to_query} {{ }} }}"""
                result = self.get_result_of_ask_query(ask_query_target_graph)
                if result and result == True:
                    self.clear_graph()
                    log.info(f'{method_log_prefix} Cleared graph {target_graph_to_query}')
                else:
                    try:
                        query = f"""CREATE GRAPH <{target_graph}>"""
                        self._set_and_execute_sparql_query_to_virtuoso(query)  
                        log.info(f'{method_log_prefix} Created graph {self._get_uriref_to_query(target_graph)}')
                    except RDFStoreInternalException:
                        log.warning(f'{method_log_prefix} Exception creating graph {target_graph_to_query}. It may have already been created before')
                        self.clear_graph()
                        log.info(f'{method_log_prefix} Cleared graph {target_graph_to_query}')
                
                result = self.get_result_of_ask_query(ask_query_source_graph)
                if result and result == True:
                    query = f"""INSERT {{ GRAPH {target_graph_to_query} {{ ?s ?p ?o }} }} 
                                WHERE {{ GRAPH {source_graph_to_query} {{ ?s ?p ?o }} }}"""
                    self._set_and_execute_sparql_query_to_virtuoso(query)
                    log.info(f'{method_log_prefix} Copied graph {source_graph_to_query} into graph {target_graph_to_query}')
                self.update_graph_uri(source_graph)
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred copyng graph {source_graph} in graph {target_graph}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)

    @log_debug
    def update_references_between_dataset_dataservices_distribution_nodes(self) -> None:
        '''
        Update possible old references between dataset and datservices, and distribution and dataservices.
        
        :param old_uri_ref: uri ref to replace
        :type old_uri_ref: str
        
        :param new_uri_ref: uri to replace with.
        :type new_uri_ref: str

        :return: The complete graph
        :rtype: :class:`ConjunctiveGraph` instance

        :raise: RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        query = None
        try:
            # Query to replace URI in object only in certain predicates 
            predicate_list = [DCAT.accessService, DCAT.servesDataset]
            predicates = [self._get_uriref_to_query(predicate) for predicate in predicate_list] 
            for predicate in predicates:
                query = f"""
                    DELETE {{ GRAPH {graph_uri} {{ ?subject {predicate} ?old_uri_ref . }} }}
                    INSERT {{ GRAPH {graph_uri} {{ ?subject {predicate} ?new_uri_ref . }} }}
                    WHERE {{  GRAPH {graph_uri} {{ 
                        ?subject {predicate} ?old_uri_ref .
                        ?subject_cr {self._get_uriref_to_query(DCT.identifier)} ?old_uri_ref ;
                                    {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.CatalogRecord)} ;
                                    {self._get_uriref_to_query(FOAF.primaryTopic)} ?new_uri_ref .
                    }} }}"""
                self._set_and_execute_sparql_query_to_virtuoso(query=query, method=POST, return_format=None)
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred replacing uris in DCAT.accessService and DCAT.servesDataset triples in graph {graph_uri} exectuting the query {query}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)

    @log_debug
    def replace_uriref_bnodes(self):
        '''
        Replace bnodes uri prefix (graph name) with root catalog uri 
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        def _replace_uris(count, batch_size):
            offset = 0
            while count >= offset:
                query = f'''DELETE {{ GRAPH {graph_uri} {{ ?s ?p ?o }} }}
                            INSERT {{ GRAPH {graph_uri} {{?ns ?p ?no }} }}
                            WHERE  {{  
                                {{ SELECT ?s ?p ?o FROM {graph_uri} WHERE {{ ?s ?p ?o FILTER (STRSTARTS(STR(?s), "{prefix}") || STRSTARTS(STR(?o), "{prefix}"))}} LIMIT {batch_size} }}
                                BIND ( IF (isIRI(?s) && STRSTARTS(STR(?s), "{prefix}"), IRI(REPLACE(STR(?s), "{prefix}", "{str(root_catalog_uri)}")), ?s) AS ?ns) 
                                BIND ( IF (isIRI(?o) && STRSTARTS(STR(?o), "{prefix}"), IRI(REPLACE(STR(?o), "{prefix}", "{str(root_catalog_uri)}")), ?o) AS ?no)
                            }}'''
                self._set_and_execute_sparql_query_to_virtuoso(query=query, method=POST, return_format=None)
                offset += BATCH_SIZE
                log.info(f'{method_log_prefix} Successfully processed batch with OFFSET {offset}')
        
        graph_uri = self.get_graph_uri_to_query()
        query = None
        try:
            BATCH_SIZE = RDFStore.BATCH_SIZE_FOR_UPDATES
            root_catalog_uri = self.get_root_catalog_uri()
            prefix = self._get_prefix_bnodes()
            if root_catalog_uri and prefix:
                query = f'''SELECT (COUNT(*) AS ?count) FROM {graph_uri} WHERE {{ ?s ?p ?o }}'''
                result = self._set_execute_and_convert_sparql_query_to_virtuoso(query=query, method=GET, return_format=JSON)
                count = int(result['results']['bindings'][0]['count']['value']) if result and result['results']['bindings'] else 0
                BATCH_SIZE = RDFStore.BATCH_SIZE_FOR_UPDATES
                MIN_BATCH_SIZE = RDFStore.BATCH_SIZE_FOR_UPDATES_MIN
                try:
                    _replace_uris(count, BATCH_SIZE)
                except RDFStoreInternalException:
                    log.warning(f'{method_log_prefix} Error trying to replace triples in batches of size {BATCH_SIZE}. Trying to replace in batches of size {MIN_BATCH_SIZE}. ')
                    _replace_uris(count, MIN_BATCH_SIZE)
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred replacing uris of nodes in graph {graph_uri} exectuting the query {query}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)