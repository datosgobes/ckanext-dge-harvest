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
import math
import re
from typing import List, Dict, Set
from SPARQLWrapper import POST, GET, JSON, QueryResult
from SPARQLWrapper.SPARQLExceptions import SPARQLWrapperException
from urllib.error import HTTPError
from rdflib import Graph, URIRef, Literal, BNode
from rdflib.exceptions import ParserError
from rdflib.namespace import XSD
from ..constants.dcat_ap_es_constants import DCAT, RDF_NAMESPACE, DCT, HYDRA, FOAF
from ..utils import get_int_value_from_ckan_property
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

    def _get_root_catalog_uri_from_graph(self, rdf_data: Graph):
        '''
        Resolve the root catalog URI directly from a local RDF graph.

        This mirrors the graph-store root catalog discovery used later in the
        gather flow, but runs before insertion so blank-node materialization
        can use the final stable prefix without requiring a post-insert
        rewrite.
        '''
        catalogs = {
            str(catalog)
            for catalog in rdf_data.subjects(RDF_NAMESPACE.type, DCAT.Catalog)
            if isinstance(catalog, URIRef)
        }
        if not catalogs:
            return None

        subcatalogs = set()
        for catalog_uri in catalogs:
            catalog_ref = URIRef(catalog_uri)
            for subcatalog in rdf_data.objects(catalog_ref, DCT.hasPart):
                if (
                    isinstance(subcatalog, URIRef)
                    and (subcatalog, RDF_NAMESPACE.type, DCAT.Catalog) in rdf_data
                ):
                    subcatalogs.add(str(subcatalog))
            for subcatalog in rdf_data.subjects(DCT.isPartOf, catalog_ref):
                if (
                    isinstance(subcatalog, URIRef)
                    and (subcatalog, RDF_NAMESPACE.type, DCAT.Catalog) in rdf_data
                ):
                    subcatalogs.add(str(subcatalog))

        root_catalogs = catalogs - subcatalogs
        if root_catalogs:
            return next(iter(root_catalogs))
        return next(iter(catalogs))

    def _get_n3_bnode_identifier(self, bnode):
        try:
            return bnode.n3().strip('_:')
        except Exception:
            return str(bnode)

    def _get_bnode_identifier(self, bnode):
        try:
            return bnode.identifier
        except AttributeError:
            return self._get_n3_bnode_identifier(bnode)

    def _type_dct_identifier_literal(self, predicate, obj):
        if (
            predicate == DCT.identifier
            and isinstance(obj, Literal)
            and obj.datatype is None
            and obj.language is None
        ):
            return Literal(str(obj), datatype=XSD.string)
        return obj

    def _get_or_create_bnode_uri(self, node, bnode_mapping, blank_node_prefix):
        if node not in bnode_mapping:
            bnode_mapping[node] = URIRef(f"{blank_node_prefix}/bnode/{self._get_bnode_identifier(node)}")
        return bnode_mapping[node]

    def _encode_term_if_uri(self, value):
        return self._get_uriref_from_str_value(value) if isinstance(value, URIRef) else value

    def _prepare_triple_for_insert(self, subject, predicate, obj, bnode_mapping, blank_node_prefix):
        obj = self._type_dct_identifier_literal(predicate, obj)

        if isinstance(subject, BNode):
            subject = self._get_or_create_bnode_uri(subject, bnode_mapping, blank_node_prefix)

        if isinstance(obj, BNode):
            obj = self._get_or_create_bnode_uri(obj, bnode_mapping, blank_node_prefix)

        subject = self._encode_term_if_uri(subject)
        predicate = self._encode_term_if_uri(predicate)
        obj = self._encode_term_if_uri(obj)
        return subject, predicate, obj

    def _prepare_rdf_data_for_insert(self, rdf_data: Graph):
        blank_node_prefix = self._get_root_catalog_uri_from_graph(rdf_data) or self._get_prefix_bnodes()
        bnode_mapping = {}
        prepared_graph = Graph()

        for subject, predicate, obj in rdf_data:
            prepared_graph.add(
                self._prepare_triple_for_insert(
                    subject,
                    predicate,
                    obj,
                    bnode_mapping,
                    blank_node_prefix
                )
            )

        return prepared_graph.serialize(format='nt').splitlines()

    def _split_duration_triples(self, triples):
        triples_to_insert = []
        duration_triples = []
        duration_values = []

        for triple in triples:
            duration_value = self._check_if_is_triple_nt_with_xsd_duration_value_and_get_duration_value(triple)
            if duration_value:
                duration_triples.append(triple)
                duration_values.append(duration_value)
            else:
                triples_to_insert.append(triple)

        return triples_to_insert, duration_triples, duration_values

    def _insert_nt_batch(self, graph_uri, triples_to_insert):
        if not triples_to_insert:
            return None

        triples_block = "\n".join(triples_to_insert)
        query = f"""INSERT DATA {{ GRAPH {graph_uri} {{ {triples_block} }} }}"""
        return self._set_and_execute_sparql_query_to_virtuoso(
            query=query,
            method=POST,
            return_format=None
        )

    def _insert_duration_triples(self, graph_uri, duration_triples, duration_values):
        result = None
        for duration_triple, duration_value in zip(duration_triples, duration_values):
            result = self._insert_triple_with_duration_value(
                graph_uri,
                duration_triple,
                duration_value
            )
        return result

    def _insert_batch(self, graph_uri, triples):
        triples_to_insert, duration_triples, duration_values = self._split_duration_triples(triples)
        result = self._insert_nt_batch(graph_uri, triples_to_insert)
        duration_result = self._insert_duration_triples(graph_uri, duration_triples, duration_values)
        return duration_result if duration_result is not None else result

    def _insert_batch_with_split(self, graph_uri, triples, min_batch_size):
        try:
            return self._insert_batch(graph_uri, triples)
        except RDFStoreInternalException:
            if len(triples) <= min_batch_size:
                raise

            mid = len(triples) // 2
            self._insert_batch_with_split(graph_uri, triples[:mid], min_batch_size)
            return self._insert_batch_with_split(graph_uri, triples[mid:], min_batch_size)

    def _insert_data_batches(self, graph_uri, data, batch_size, min_batch_size, method_log_prefix):
        total_batch = math.ceil(len(data) / batch_size)
        result = None

        for i in range(0, len(data), batch_size):
            batch_number = i // batch_size + 1
            triples = data[i:i+batch_size]
            log.debug(
                f'{method_log_prefix} Inserting batch {batch_number}/{total_batch} '
                f'with {len(triples)} triples into graph {graph_uri}'
            )
            result = self._insert_batch_with_split(graph_uri, triples, min_batch_size)

        return result

    def _get_graph_page(self, graph_uri: str, offset: int):
        '''
        Read one page of triples from graph_uri using configured pagination size.

        Backup copy must avoid `ORDER BY` because Virtuoso rejects high
        `OFFSET` values on sorted results (`SR353`).

        :param graph_uri: Graph URI to read from.
        :type graph_uri: str

        :param offset: Pagination offset.
        :type offset: int

        :return: Parsed RDF page.
        :rtype: rdflib.Graph

        :raise RDFStoreInternalException: If query or RDF parsing fails.
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        result = Graph()
        graph_uri_to_query = self._get_uriref_to_query(graph_uri)

        try:
            query = f"CONSTRUCT {{ ?s ?p ?o }} FROM {graph_uri_to_query} WHERE {{ ?s ?p ?o }}"
            if self.max_triples_per_query:
                query = f'{query} LIMIT {self.max_triples_per_query}'
            if offset:
                query = f'{query} OFFSET {offset}'

            results = self._set_execute_and_convert_sparql_query_to_virtuoso(
                query=query,
                method=GET,
                return_format='rdf'
            )
            if results:
                result = Graph().parse(data=results.serialize(format='xml'), format='xml')
        except (RDFStoreInternalException) as e:
            log.error(
                f'{method_log_prefix} An exception has occurred getting backup page '
                f'from graph {graph_uri_to_query} with offset={offset}. '
                f'{type(e).__name__}: {str(e)}'
            )
            raise
        except (ParserError, SyntaxError) as e:
            log.error(
                f'{method_log_prefix} An exception has occurred parsing backup page '
                f'from graph {graph_uri_to_query} with offset={offset}. '
                f'{type(e).__name__}: {str(e)}'
            )
            raise RDFStoreInternalException(str(e))

        return result

    def _copy_graph_in_pages(self, source_graph: str, target_graph_to_query: str, method_log_prefix: str) -> int:
        '''
        Copy source graph into current target graph using paginated reads and batched inserts.

        :param source_graph: Graph URI to read from.
        :type source_graph: str

        :param target_graph_to_query: Query-safe target graph URI, only used for logs.
        :type target_graph_to_query: str

        :param method_log_prefix: Prefix used in log lines.
        :type method_log_prefix: str

        :return: Number of copied triples.
        :rtype: int

        :raise RDFStoreInternalException: If page copy fails.
        '''
        copied_triples = 0
        offset = 0

        while True:
            page_graph = self._get_graph_page(source_graph, offset)
            page_size = len(page_graph)
            if page_size == 0:
                break

            self.insert_rdf_data(page_graph)
            copied_triples += page_size
            log.info(
                f'{method_log_prefix} Copied page with {page_size} triples from '
                f'graph {self._get_uriref_to_query(source_graph)} into graph '
                f'{target_graph_to_query}. offset={offset}'
            )
            offset += self.max_triples_per_query
            page_graph.remove((None, None, None))

        return copied_triples
    
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
        graph_uri = self.get_graph_uri_to_query()
        try:
            data = self._prepare_rdf_data_for_insert(rdf_data)
            return self._insert_data_batches(
                graph_uri,
                data,
                RDFStore.BATCH_SIZE_FOR_INSERTS,
                RDFStore.BATCH_SIZE_FOR_INSERTS_MIN,
                method_log_prefix
            )
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred inserting data into graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e) from e

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
                    raise self._get_raise_exception(e) from e
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
            raise self._get_raise_exception(e) from e
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
            raise self._get_raise_exception(e) from e
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
            raise self._get_raise_exception(e) from e
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
            self._replace_uriRef_value_in_subjects_by_predicate(old_uri_ref, new_uri_ref)

    def _execute_uri_rewrite_batches(self, predicates, batch_query_builder, method_log_prefix):
        '''
        Execute URI rewrite queries in predicate batches.

        :param predicates: Predicates to process, already encoded for SPARQL.
        :type predicates: List[str]

        :param batch_query_builder: Callback that builds SPARQL query from a predicate batch.
        :type batch_query_builder: Callable[[List[str]], str]

        :param method_log_prefix: Prefix used in log lines.
        :type method_log_prefix: str

        :raise RDFStoreInternalException: If any batch cannot be executed.
        '''
        def _run_batches(batch_size):
            total_predicates = len(predicates)
            total_batches = math.ceil(total_predicates / batch_size) if total_predicates else 0
            for i in range(0, total_predicates, batch_size):
                current_predicates = predicates[i:i+batch_size]
                if not current_predicates:
                    continue

                query = batch_query_builder(current_predicates)
                self._set_and_execute_sparql_query_to_virtuoso(query=query, method=POST, return_format=None)

                batch_number = i // batch_size + 1
                log.info(
                    f'{method_log_prefix} Successfully processed batch '
                    f'{batch_number}/{total_batches} with {len(current_predicates)} predicates'
                )

        if predicates:
            batch_size = RDFStore.BATCH_SIZE_FOR_UPDATES
            min_batch_size = RDFStore.BATCH_SIZE_FOR_UPDATES_MIN
            try:
                _run_batches(batch_size)
            except RDFStoreInternalException:
                log.warning(
                    f'{method_log_prefix} Error trying to replace triples in batches '
                    f'of size {batch_size}. Trying to replace in batches of size '
                    f'{min_batch_size}. '
                )
                _run_batches(min_batch_size)

    def _replace_uriRef_value_in_subjects_by_predicate(self, old_uri_ref:str, new_uri_ref:str):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)

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
                predicates = [self._get_uriref_to_query(item['p']['value']) for item in results or []]

                def _build_query(current_predicates):
                    return f"""DELETE {{ GRAPH {graph_uri} {{ {_old_uri_ref} ?p ?o }} }}
                               INSERT {{ GRAPH {graph_uri} {{ {_new_uri_ref} ?p ?o }} }}
                               WHERE {{ GRAPH {graph_uri} {{
                                   {_old_uri_ref} ?p ?o .
                                   FILTER (?p in ({','.join(current_predicates)}))
                               }} }}"""

                self._execute_uri_rewrite_batches(predicates, _build_query, method_log_prefix)
            except (RDFStoreInternalException) as e:
                log.error(
                    f'{method_log_prefix} An exception has occurred replacing the '
                    f'old URIRef {old_uri_ref} with the URIRef {new_uri_ref} in '
                    f'graph {graph_uri} with predicates = {predicates} executing '
                    f'the query {query}. {type(e).__name__}: {str(e)}'
                )
                raise self._get_raise_exception(e) from e

    def _replace_uriRef_value_in_objects(self, old_uri_ref:str, new_uri_ref:str):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        log.info(f'{old_uri_ref != new_uri_ref}')
        if old_uri_ref and new_uri_ref and old_uri_ref != new_uri_ref:
            self._replace_uriRef_value_in_objects_by_predicate(old_uri_ref, new_uri_ref)

    def _replace_uriRef_value_in_objects_by_predicate(self, old_uri_ref:str, new_uri_ref:str):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        log.info(f'{old_uri_ref != new_uri_ref}')
        if old_uri_ref and new_uri_ref and old_uri_ref != new_uri_ref:
            graph_uri = self.get_graph_uri_to_query()
            query = ''
            try:
               # Query to replace URI in object only in certain predicates 
                predicate_list = [DCAT.service, DCAT.dataset, FOAF.primaryTopic, DCAT.distribution, DCAT.servesDataset, DCAT.accessService]
                predicates = [self._get_uriref_to_query(predicate) for predicate in predicate_list] 
                _old_uri_ref = self._get_uriref_to_query(old_uri_ref)
                _new_uri_ref = self._get_uriref_to_query(new_uri_ref)

                def _build_query(current_predicates):
                    return f"""DELETE {{ GRAPH {graph_uri} {{ ?s ?p {_old_uri_ref} }} }}
                               INSERT {{ GRAPH {graph_uri} {{ ?s ?p {_new_uri_ref} }} }}
                               WHERE {{ GRAPH {graph_uri} {{
                                   ?s ?p {_old_uri_ref} .
                                   FILTER (?p in ({','.join(current_predicates)}))
                               }} }}"""

                query = _build_query(predicates)
                self._execute_uri_rewrite_batches(predicates, _build_query, method_log_prefix)
            except (RDFStoreInternalException) as e:
                log.error(f'{method_log_prefix} An exception has occurred replacing the old URIRef {old_uri_ref} with the URIRef {new_uri_ref} in graph {graph_uri} exectuting the query {query}. {type(e).__name__}: {str(e)}')
                raise self._get_raise_exception(e) from e
    
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
                self.drop_graph()
                log.info(f'{method_log_prefix} Dropped graph {target_graph_to_query}')
                
                result = self.get_result_of_ask_query(ask_query_source_graph)
                if result and result == True:
                    copied_triples = self._copy_graph_in_pages(source_graph, target_graph_to_query, method_log_prefix)
                    log.info(
                        f'{method_log_prefix} Copied graph {source_graph_to_query} '
                        f'into graph {target_graph_to_query}. triples={copied_triples}'
                    )
                self.update_graph_uri(source_graph)
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred copyng graph {source_graph} in graph {target_graph}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e) from e

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
            raise self._get_raise_exception(e) from e

    @log_debug
    def replace_uriref_bnodes(self):
        '''
        Replace bnodes uri prefix (graph name) with root catalog uri 
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)

        def _binding_to_query_term(binding):
            binding_type = binding.get('type')
            binding_value = binding.get('value')

            if binding_type == 'uri':
                return self._get_uriref_to_query(binding_value)
            if binding_type == 'bnode':
                return f'_:{binding_value}'
            if binding_type in ('literal', 'typed-literal'):
                datatype = binding.get('datatype')
                language = binding.get('xml:lang') or binding.get('lang')
                literal = Literal(
                    binding_value,
                    datatype=URIRef(datatype) if datatype else None,
                    lang=language
                )
                return literal.n3()
            raise RDFStoreInternalException(f'Unsupported SPARQL binding type: {binding_type}')

        def _replace_prefixed_uri(binding_value):
            if binding_value and binding_value.startswith(prefix):
                return binding_value.replace(prefix, str(root_catalog_uri), 1)
            return binding_value

        def _build_values_rows(results, target_name):
            values_rows = []
            for result in results or []:
                s_term = _binding_to_query_term(result['s'])
                p_term = _binding_to_query_term(result['p'])
                o_term = _binding_to_query_term(result['o'])

                ns_value = _replace_prefixed_uri(result['s']['value']) if target_name == 'subject' else result['s']['value']
                no_value = _replace_prefixed_uri(result['o']['value']) if target_name == 'object' else result['o']['value']

                ns_term = self._get_uriref_to_query(ns_value) if target_name == 'subject' else s_term
                no_term = self._get_uriref_to_query(no_value) if target_name == 'object' else o_term
                values_rows.append(f'({s_term} {p_term} {o_term} {ns_term} {no_term})')
            return values_rows

        def _get_batch_fingerprint(results):
            return tuple(
                (
                    result['s'].get('type'),
                    result['s'].get('value'),
                    result['p'].get('type'),
                    result['p'].get('value'),
                    result['o'].get('type'),
                    result['o'].get('value'),
                    result['o'].get('datatype'),
                    result['o'].get('xml:lang') or result['o'].get('lang')
                )
                for result in results or []
            )

        def _count_candidates(target_filter):
            count_query = f'''SELECT (COUNT(*) AS ?count) FROM {graph_uri} WHERE {{
                                  ?s ?p ?o .
                                  FILTER ({target_filter})
                              }}'''
            results = self._get_results_by_query(count_query)
            if not results:
                return 0
            return int(results[0]['count']['value'])

        def _replace_uris(batch_size, target_name, target_filter):
            batch_number = 0
            repeated_batch_hits = 0
            previous_batch_fingerprint = None
            initial_candidates = _count_candidates(target_filter)
            log.info(
                f'{method_log_prefix} Found {initial_candidates} {target_name} '
                f'candidates to rewrite with batch_size={batch_size}'
            )
            while True:
                if max_batches and batch_number >= max_batches:
                    raise RDFStoreInternalException(
                        f'Maximum number of {target_name} batches reached '
                        f'({max_batches}). Aborting to avoid non-convergent URI '
                        f'rewrite loop.'
                    )

                select_query = f'''SELECT ?s ?p ?o FROM {graph_uri} WHERE {{
                                     ?s ?p ?o .
                                     FILTER ({target_filter})
                                 }} LIMIT {batch_size}'''
                results = self._get_results_by_query(select_query)
                if not results:
                    break

                current_batch_fingerprint = _get_batch_fingerprint(results)
                if current_batch_fingerprint == previous_batch_fingerprint:
                    repeated_batch_hits += 1
                    if repeated_batch_hits >= max_repeated_batches:
                        raise RDFStoreInternalException(
                            f'Repeated {target_name} batch detected '
                            f'{repeated_batch_hits} consecutive times. Aborting to '
                            f'avoid non-convergent URI rewrite loop.'
                        )
                else:
                    repeated_batch_hits = 0
                    previous_batch_fingerprint = current_batch_fingerprint

                batch_number += 1
                values_rows = _build_values_rows(results, target_name)
                query = f'''DELETE {{ GRAPH {graph_uri} {{ ?s ?p ?o }} }}
                            INSERT {{ GRAPH {graph_uri} {{ ?ns ?p ?no }} }}
                            WHERE {{
                                VALUES (?s ?p ?o ?ns ?no) {{
                                    {' '.join(values_rows)}
                                }}
                            }}'''
                self._set_and_execute_sparql_query_to_virtuoso(query=query, method=POST, return_format=None)
                log.info(
                    f'{method_log_prefix} Successfully processed {target_name} '
                    f'batch {batch_number} with {len(results)} triples'
                )
                if candidate_check_every and batch_number % candidate_check_every == 0:
                    current_candidates = _count_candidates(target_filter)
                    log.info(
                        f'{method_log_prefix} Candidate check after {target_name} '
                        f'batch {batch_number}. remaining_candidates='
                        f'{current_candidates}'
                    )

            remaining_candidates = _count_candidates(target_filter)
            log.info(
                f'{method_log_prefix} Finished {target_name} rewrite. '
                f'initial_candidates={initial_candidates}, '
                f'remaining_candidates={remaining_candidates}, '
                f'processed_batches={batch_number}'
            )
        
        graph_uri = self.get_graph_uri_to_query()
        query = None
        try:
            BATCH_SIZE = RDFStore.BATCH_SIZE_FOR_UPDATES
            root_catalog_uri = self.get_root_catalog_uri()
            prefix = self._get_prefix_bnodes()
            if root_catalog_uri and prefix:
                BATCH_SIZE = RDFStore.BATCH_SIZE_FOR_UPDATES
                MIN_BATCH_SIZE = RDFStore.BATCH_SIZE_FOR_UPDATES_MIN
                max_batches = get_int_value_from_ckan_property(
                    'ckanext.dge_harvest.virtuoso.batch_max_rewrite_batches',
                    100000
                )
                max_repeated_batches = get_int_value_from_ckan_property(
                    'ckanext.dge_harvest.virtuoso.batch_max_repeated_rewrite_batches',
                    3
                )
                candidate_check_every = get_int_value_from_ckan_property(
                    'ckanext.dge_harvest.virtuoso.batch_candidate_check_every',
                    100
                )
                max_batches = max(max_batches, 1)
                max_repeated_batches = max(max_repeated_batches, 1)
                candidate_check_every = max(candidate_check_every, 1)
                subject_filter = f'isIRI(?s) && STRSTARTS(STR(?s), "{prefix}")'
                object_filter = f'isIRI(?o) && STRSTARTS(STR(?o), "{prefix}")'
                try:
                    _replace_uris(BATCH_SIZE, 'subject', subject_filter)
                    _replace_uris(BATCH_SIZE, 'object', object_filter)
                except RDFStoreInternalException:
                    log.warning(f'{method_log_prefix} Error trying to replace triples in batches of size {BATCH_SIZE}. Trying to replace in batches of size {MIN_BATCH_SIZE}. ')
                    _replace_uris(MIN_BATCH_SIZE, 'subject', subject_filter)
                    _replace_uris(MIN_BATCH_SIZE, 'object', object_filter)
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred replacing uris of nodes in graph {graph_uri} exectuting the query {query}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e) from e
