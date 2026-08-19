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
from typing import List, Set
from SPARQLWrapper import POST, QueryResult
from urllib.error import HTTPError
from rdflib import Namespace, URIRef
from ..constants.dcat_ap_es_constants import DCAT, RDF_NAMESPACE, DCT, HYDRA, FOAF, DCATAPESPrefixConstants, DcatClassNameEnum
from ..constants.constants import RDFStoreConstants
from .rdf_store_helper import RDFStoreHelper, RDFStoreException, RDFStoreInternalException
from ..decorators import log_debug, log_info
from ..utils import get_int_value_from_ckan_property
from .rdf_store import RDFStore

log = logging.getLogger(__name__)
MAX_PREPROCESS_ITERATIONS_PROPERTY = 'ckanext.dge_harvest.preprocess.max_num_of_iterations'

class RDFStoreDelete(RDFStoreHelper):
    '''
    Class that contains utils method to delete data in virtuoso
    '''
    def _drop_subjects_in_graph(self, subject_uris: List[str]) -> QueryResult:
        '''
        Delete all triples whose subject is one of the provided URIs.

        This helper is required when deleting batches of nodes by subject. A
        query composed as multiple `<subject> ?p ?o` patterns in the same
        `DELETE/WHERE` would incorrectly join on shared `?p` and `?o`
        variables, so deletion must be expressed with `FILTER (?s IN (...))`.

        :param subject_uris: Subject URIs to delete from the current graph.
        :type subject_uris: List[str]

        :return: Query result or None if there are no subjects to delete.
        :rtype: QueryResult | None
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()

        def _drop_subjects(batch_size):
            result = None
            if subject_uris:
                total_batch = math.ceil(len(subject_uris) / batch_size)
                for i in range(0, len(subject_uris), batch_size):
                    batch_number = i // batch_size + 1
                    current_subjects = subject_uris[i:i+batch_size]
                    subjects = ', '.join(
                        self._get_uriref_to_query(subject_uri)
                        for subject_uri in current_subjects
                    )
                    query = f'''DELETE {{ GRAPH {graph_uri} {{ ?s ?p ?o . }} }}
                                WHERE {{ GRAPH {graph_uri} {{
                                    ?s ?p ?o .
                                    FILTER (?s IN ({subjects}))
                                }} }}'''
                    log.info(
                        f'{method_log_prefix} Deleting subjects in batch '
                        f'{batch_number}/{total_batch} with {len(current_subjects)} '
                        f'subjects from graph {graph_uri}'
                    )
                    result = self._set_and_execute_sparql_query_to_virtuoso(
                        query=query,
                        method=POST,
                        return_format=None
                    )
            return result

        result = None
        batch_size = RDFStore.BATCH_SIZE_FOR_DELETES
        min_batch_size = RDFStore.BATCH_SIZE_FOR_DELETES_MIN
        try:
            result = _drop_subjects(batch_size)
        except RDFStoreInternalException:
            log.warning(
                f'{method_log_prefix} Error trying to delete subjects in batches '
                f'of size {batch_size}. Trying to delete in batches of size '
                f'{min_batch_size}. '
            )
            result = _drop_subjects(min_batch_size)
        return result

    def _delete_reference_triples(self, triples_to_delete, node_uri, node_type_label, method_log_prefix, graph_uri):
        '''
        Delete references that point to a node.

        :param triples_to_delete: Triples to remove.
        :type triples_to_delete: List[tuple[str, str, str]]

        :param node_uri: URI of node whose references are removed.
        :type node_uri: str

        :param node_type_label: Label used only in logs.
        :type node_type_label: str

        :param method_log_prefix: Prefix used in log lines.
        :type method_log_prefix: str

        :param graph_uri: Graph URI used in logs.
        :type graph_uri: str

        :return: Query result or None if no triples.
        :rtype: QueryResult | None
        '''
        if not triples_to_delete:
            return None

        result = self._drop_triples_in_graph(triples_to_delete)
        log.info(
            f'{method_log_prefix} Deleted {len(triples_to_delete)} reference triples '
            f'for {node_type_label} {node_uri} in graph {graph_uri}'
        )
        return result

    def _process_uri_batches(self, uris, batch_handler, method_log_prefix, batch_size=None):
        '''
        Process URIs in fixed-size batches.

        :param uris: URIs to process.
        :type uris: List[str]

        :param batch_handler: Callback invoked with one URI batch.
        :type batch_handler: Callable[[List[str]], None]

        :param method_log_prefix: Prefix used in log lines.
        :type method_log_prefix: str

        :param batch_size: Maximum URIs per batch. Defaults to update batch size.
        :type batch_size: int | None
        '''
        if not uris:
            return

        batch_size = batch_size or RDFStoreHelper.BATCH_SIZE_FOR_UPDATES
        total_uris = len(uris)
        total_batches = math.ceil(total_uris / batch_size)
        for i in range(0, total_uris, batch_size):
            batch_number = i // batch_size + 1
            current_uris = uris[i:i+batch_size]
            batch_handler(current_uris)
            log.info(
                f'{method_log_prefix} Processed URI batch {batch_number}/{total_batches} '
                f'with {len(current_uris)} URIs'
            )

    @log_debug
    def delete_catalogs_in_graph(self, catalog_uris: List[str]) -> List[QueryResult]:
        '''
        Delete the catalogs nodes ignoring its subnodes in graph in Virtuoso

        :param catalog_uris: List of the catalog URIs to delete
        :type catalog_uri: List[str]

        :return: a list of query results
        :rtype: List[:class:`QueryResult` instance]

        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        try:
            catalog_list_to_delete = set(catalog_uris or [])
            if catalog_list_to_delete:
                """
                catalogs_to_delete = ', '.join(f'{self._get_uriref_to_query(uri)}' for uri in catalog_list_to_delete)
                # Query de borrado para el catalog
                query = f'''DELETE  {{ GRAPH {graph_uri} {{ ?s ?p ?o . }} }}
                            WHERE {{ GRAPH {graph_uri} {{ ?catalog ?p ?o .
                            FILTER (?catalog IN ({catalogs_to_delete}))  }} }}'''
                result = self._get_results_by_query(query)
                log.info(f'{method_log_prefix} Deleted data of catalogs {catalogs_to_delete} in graph {graph_uri}')
                """
                for catalog in catalog_list_to_delete:
                    _uriref_catalog = self._get_uriref_to_query(catalog)
                    query = f'''DELETE {{ GRAPH {graph_uri} {{ {_uriref_catalog} ?p ?o .}} }}
                                WHERE  {{ GRAPH {graph_uri} {{ {_uriref_catalog} ?p ?o .}} }}'''
                    result = self._get_results_by_query(query)
                    log.info(f'{method_log_prefix} Deleted data of catalogs {catalog} in graph {graph_uri}')
        except (RDFStoreInternalException) as e:
            log.exception(f'{method_log_prefix} An exception has occurred deleting catalogs in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e) from e
        return result

    @log_debug
    def delete_dataservice_in_graph(self, dataservice_uri) -> List[QueryResult]:
        '''
        Delete a Dataservice node ignoring its subnodes in graph in Virtuoso

        :param dataservice_uri: URI of the dataservice to delete
        :type dataservice_uri: str

        :return: a list of query results
        :rtype: List[:class:`QueryResult` instance]

        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        try:
            if not dataservice_uri:
                log.info(f'{method_log_prefix} No dataservice_uri to delete')
                return []
            # Search for references to the dataservice as an object in the catalog
            catalog_list = self._get_subjects_by_predicate_and_object(DCAT.service, dataservice_uri, True)
            triples_to_delete = [(f"{self._get_uriref_to_query(catalog_uri)}", f"{self._get_uriref_to_query(DCAT.service)}", f"{self._get_uriref_to_query(dataservice_uri)}") for catalog_uri in catalog_list or []] 

            # Find references to the dataservice as an object in record catalog
            catalog_record_triples = self.get_catalog_records_triples_of_a_dataset_or_a_dataservice(dataservice_uri)
            if catalog_record_triples:
                triples_to_delete.extend(catalog_record_triples)
            
            # Find references to the dataservice as an object in distributions/accessService
            distribution_list = self._get_subjects_by_predicate_and_object(DCAT.accessService, dataservice_uri, True)
            triples_to_delete.extend([(f"{self._get_uriref_to_query(distribution_uri)}", f"{self._get_uriref_to_query(DCAT.accessService)}", f"{self._get_uriref_to_query(dataservice_uri)}") for distribution_uri in distribution_list or []])

            # Deletion query for the dataservice
            result = self._drop_triples_in_graph([(self._get_uriref_to_query(dataservice_uri), '?p', '?o')])
            result = self._delete_reference_triples(
                triples_to_delete,
                dataservice_uri,
                'dataservice',
                method_log_prefix,
                graph_uri
            ) or result
            log.info(f'{method_log_prefix} Deleted data of {dataservice_uri} in graph {graph_uri}')

        except (RDFStoreInternalException) as e:
            log.exception(f'{method_log_prefix} An exception has occurred deleting of {dataservice_uri} data in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e) from e
        return result

    @log_debug
    def delete_dataset_in_graph(self, dataset_uri) -> List[str]:
        '''
        Delete a Dataset node ignoring its subnodes in graph in Virtuoso

        :param dataset_uri: URI of the dataset to delete
        :type dataset_uri: str

        :return: a list of query results
        :rtype: List[str]

        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        result = None
        try:
            if not dataset_uri:
                log.info(f'{method_log_prefix} No dataset_uri to delete')
                return []
            ADMS = Namespace(RDFStoreConstants.ADMS_URI)
            # Search for references to the dataset as an object in the catalog
            catalog_list = self._get_subjects_by_predicate_and_object(DCAT.dataset, dataset_uri, True)
            triples_to_delete = [(f"{self._get_uriref_to_query(catalog_uri)}", f"{self._get_uriref_to_query(DCAT.dataset)}", f"{self._get_uriref_to_query(dataset_uri)}") for catalog_uri in catalog_list or []]
            
            # Find references to the dataset as an object in record catalog
            catalog_record_triples = self.get_catalog_records_triples_of_a_dataset_or_a_dataservice(dataset_uri)
            if catalog_record_triples:
                triples_to_delete.extend(catalog_record_triples)
            
            # Find references to the dataset as an object in dataservices/servesDataset
            dataservice_list = self._get_subjects_by_predicate_and_object(DCAT.servesDataset, dataset_uri, True)
            triples_to_delete.extend([(f"{self._get_uriref_to_query(dataservice_uri)}", f"{self._get_uriref_to_query(DCAT.servesDataset)}", f"{self._get_uriref_to_query(dataset_uri)}") for dataservice_uri in dataservice_list or []])
            
            # Obtain IRIs of distributions linked to the dataset (distribution and sample)
            distribution_list = self._get_objects_by_subject_and_predicate(dataset_uri, DCAT.distribution, True)
            distribution_sample_list = self._get_objects_by_subject_and_predicate(dataset_uri, ADMS.sample, True)
            distribution_list.extend(distribution_sample_list)


            result = self._drop_triples_in_graph([
                (self._get_uriref_to_query(dataset_uri), '?p', '?o')
            ])
            log.info(f'{method_log_prefix} Deleted direct triples of dataset {dataset_uri} in graph {graph_uri}')


            result = self._delete_reference_triples(
                triples_to_delete,
                dataset_uri,
                'dataset',
                method_log_prefix,
                graph_uri
            ) or result

            # Phase 5: delete direct triples of related distributions/samples
            if distribution_list:
                distribution_triples_to_delete = [
                    (self._get_uriref_to_query(distribution_uri), '?p', '?o')
                    for distribution_uri in distribution_list
                ]
                result = self._drop_triples_in_graph(distribution_triples_to_delete)
                log.info(
                    f'{method_log_prefix} Deleted direct triples of {len(distribution_list)} '
                    f'distributions/samples linked to dataset {dataset_uri} in graph {graph_uri}'
                )
        except (RDFStoreInternalException) as e:
            log.exception(f'{method_log_prefix} An exception has occurred deleting of {dataset_uri} data in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e) from e
        return result

    @log_debug
    def drop_all_unreferenced_nodes(self) -> Set[str]:
        """
        Drop all unreferenced nodes in a graph
        
        :raise RDFStoreException
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        unreferenced_nodes = set()
        try:
            graph_uri = self.get_graph_uri_to_query()
            root_catalog = self.get_root_catalog_uri()
            non_referenced_node_uris = None
            MAX_NUM_OF_ITERATIONS = get_int_value_from_ckan_property(MAX_PREPROCESS_ITERATIONS_PROPERTY, 20)
            BATCH_SIZE = get_int_value_from_ckan_property('ckanext.dge_harvest.preprocess.unreferenced_nodes_batch_size', 1000)
            iteration = 0
            total_deleted_nodes = 0
            while iteration < MAX_NUM_OF_ITERATIONS:
                # Find only one batch of non referenced nodes to avoid loading the
                # full candidate set into memory for very large graphs.
                find_nodes_query = f""" SELECT DISTINCT ?node_subject FROM {graph_uri} WHERE {{ 
                    ?node_subject ?p ?o .
                    FILTER NOT EXISTS {{ ?s ?any_predicate ?node_subject }} # It is not an object
                    FILTER (?node_subject != {self._get_uriref_to_query(root_catalog)}) # Except root catalog
                    }} LIMIT {BATCH_SIZE}"""
                non_referenced_node_uris = self.get_objects_by_query(find_nodes_query, 'node_subject')
                if not non_referenced_node_uris:
                    break

                subjects_to_delete = []
                for non_referenced_node_uri in non_referenced_node_uris or []:
                    unreferenced_nodes.add(str(non_referenced_node_uri))
                    subjects_to_delete.append(str(non_referenced_node_uri))

                self._drop_subjects_in_graph(subjects_to_delete)
                iteration +=1
                total_deleted_nodes += len(subjects_to_delete)
                log.info(
                    f'{method_log_prefix} Deleted batch {iteration}/{MAX_NUM_OF_ITERATIONS} '
                    f'with {len(subjects_to_delete)} unreferenced nodes in graph '
                    f'{graph_uri}. total_deleted={total_deleted_nodes}'
                )
            if iteration == MAX_NUM_OF_ITERATIONS:
                log.warning(f'{method_log_prefix} The maximum number of iterations has been reached. The node may not have been completely removed. It would be necessary to check that the queries are correct.')
                raise RDFStoreInternalException(f'Unreferenced nodes {non_referenced_node_uris} have not been completely removed in graph {graph_uri}')

        except (KeyError, RDFStoreInternalException) as e:
            log.exception(f'{method_log_prefix} An exception has occurred deleting non referenced nodes in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e) from e
        log.debug(f'{method_log_prefix} End method')
        return unreferenced_nodes

    @log_debug
    def remove_undescribed_catalogs(self) -> List[str]:
        '''
        Remove undescribed catalogs in a graph (metadata dct:hasPart of Catalog)
        
        :return: List of objects uri 
        :rtype: List[str]

        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            graph_uri = self.get_graph_uri_to_query()
            result_uris = []
            object_name ='catalog_2' 
            query = f'''
                SELECT DISTINCT ?{object_name} FROM {graph_uri} WHERE {{ 
                    ?catalog_1 {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Catalog)} . 
                    ?catalog_1 {self._get_uriref_to_query(DCT.hasPart)} ?{object_name} .
                    FILTER NOT EXISTS {{ ?{object_name} {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Catalog)} .}}
                    }}
                '''
            result_uris = self.get_objects_by_query(query, object_name)
            triples_to_delete = [(f'?s{i}', f'{self._get_uriref_to_query(DCT.hasPart)}', f'{self._get_uriref_to_query(result_uri)}') for i, result_uri in enumerate(result_uris or [], start=0)]
            self._drop_triples_in_graph(triples_to_delete)
        except (RDFStoreInternalException) as e:
            log.exception(f'{method_log_prefix} An exception has occurred removing undescribed catalogs in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e) from e
        return result_uris

    @log_debug
    def remove_undescribed_datasets_or_dataservices(self, dcat_class_name:DcatClassNameEnum) -> List[str]:
        '''
        Remove undescribed datasets in a graph 
        (metadata DCAT.dataset in Catalog or metadata DCAT.servesDataset in Dataset if dclat_class_name is Dataset;
        metadata DCAT.dataservice in Catalog or metadata DCAT.accessService in Distribution if dclat_class_name is Dataset) 

        :param dcat_class_name: Name of dcat class name. Only DATASET or DATASERVICE are expected values.
        :type dcat_class_name: DcatClassNameEnum
        
        :return: List of objects uri 
        :rtype: List[str]

        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        result_all_uris = []
        try:
            if dcat_class_name and (dcat_class_name == DcatClassNameEnum.DATASET or dcat_class_name == DcatClassNameEnum.DATASERVICE):
                
                result_uris = self._get_undescribed_datasets_or_dataservices_in_a_catalog(dcat_class_name)
                result_all_uris = result_uris
                predicate = DCAT.dataset if dcat_class_name == DcatClassNameEnum.DATASET else DCAT.service
                triples_to_delete = [(f'?s{i}', f'{self._get_uriref_to_query(predicate)}', f'{self._get_uriref_to_query(result_uri)}') for i, result_uri in enumerate(result_uris or [], start=0)]

                if dcat_class_name == DcatClassNameEnum.DATASET:
                    result_uris = self._get_undescribed_datasets_in_a_dataservice()
                    result_all_uris.extend(result_uris)
                    triples_to_delete.extend([(f'?s{i}', f'{self._get_uriref_to_query(DCAT.servesDataset)}', f'{self._get_uriref_to_query(result_uri)}') for i, result_uri in enumerate(result_uris or [], start = len(triples_to_delete))])
                else: 
                    result_uris = self._get_undescribed_dataservices_in_a_distribution()
                    result_all_uris.extend(result_uris)
                    triples_to_delete.extend([(f'?s{i}', f'{self._get_uriref_to_query(DCAT.accessService)}', f'{self._get_uriref_to_query(result_uri)}') for i, result_uri in enumerate(result_uris or [], start = len(triples_to_delete))])

                self._drop_triples_in_graph(triples_to_delete)
                
                log.info(f'{method_log_prefix} Removed undescribed {dcat_class_name}: {result_all_uris}')
        except (RDFStoreInternalException) as e:
            log.exception(f'{method_log_prefix} An exception has occurred removing undescribed {dcat_class_name}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e) from e
        return result_all_uris

    @log_debug
    def remove_references_of_unreferenced_datasets_or_dataservices_in_a_catalog(self, dcat_class_name:DcatClassNameEnum) -> List[str]:
        '''
        Remove references of unreferenced datasets or dataservices in a catalog 

        :param dcat_class_name: Name of dcat class name. Only DATASET or DATASERVICE are expected values.
        :type dcat_class_name: DcatClassNameEnum

        :return: List of objects uri 
        :rtype: List[str]

        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        result_uris = []
        graph_uri = self.get_graph_uri_to_query()
        try:
            if dcat_class_name and (dcat_class_name == DcatClassNameEnum.DATASET or dcat_class_name == DcatClassNameEnum.DATASERVICE):
                if dcat_class_name == DcatClassNameEnum.DATASET:
                    object_name ='dataset_1' 
                    # Get references to dataset that are not referenced in a catalog (dcat.servesDataset metadata)
                    query = f'''
                        SELECT DISTINCT ?{object_name} FROM {graph_uri} {{ 
                            ?dataservice_1 {self._get_uriref_to_query(DCAT.servesDataset)} ?{object_name} .
                            FILTER NOT EXISTS {{ 
                                ?catalog_1 {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Catalog)} . 
                                ?catalog_1 {self._get_uriref_to_query(DCAT.dataset)} ?{object_name} .
                            }}
                        }}
                        '''
                    predicate = DCAT.servesDataset
                else:
                    object_name ='dataservice_1' 
                    # Get references to dataservices that are not referenced in a catalog (dcat.accessService metadata)
                    query = f'''
                        SELECT DISTINCT ?{object_name} FROM {graph_uri} WHERE {{ 
                            ?distribution_1 {self._get_uriref_to_query(DCAT.accessService)} ?{object_name} .
                            FILTER NOT EXISTS {{ 
                                ?catalog_1 {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Catalog)} . 
                                ?catalog_1 {self._get_uriref_to_query(DCAT.service)} ?{object_name} .
                            }}
                        }}
                        '''
                    predicate = DCAT.accessService
                
                result_uris = self.get_objects_by_query(query, object_name)
                triples_to_delete = [(f'?s{i}', f'{self._get_uriref_to_query(predicate)}', f'{self._get_uriref_to_query(result_uri)}') for i, result_uri in enumerate(result_uris or [], start=0)]
                self._drop_triples_in_graph(triples_to_delete)
                log.info(f'{method_log_prefix} Removed references of unreferenced {dcat_class_name} in {graph_uri}: {result_uris}')
        except (RDFStoreInternalException) as e:
            log.exception(f'{method_log_prefix} An exception has occurred removing unreferenced {dcat_class_name} in catalogs in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e) from e
        return result_uris

    @log_debug
    def remove_unreferenced_described_datasets_or_dataservices(self, dcat_class_name:DcatClassNameEnum) -> List[str]:
        '''
        Remove unreferenced described datasets in a catalog if dcat_class_name is Dataset: 
        There is a tripleta (dataset_uri, RDF.type, DCAT.Dataset) but there are not triples
        (catalog_uri, RDF.type, DCAT.Catalog) and (catalog_uri, DCAT.dataset, dataset_uri).
        
        Remove unreferenced described dataservices in a catalog if dcat_class_name is Dataservice: 
        There is a tripleta (dataservice_uri, RDF.type, DCAT.DataService) but there are not triples
        (catalog_uri, RDF.type, DCAT.Catalog) and (catalog_uri, DCAT.service, dataservice_uri).

        :param dcat_class_name: Name of dcat class name. Only DATASET or DATASERVICE are expected values.
        :type dcat_class_name: DcatClassNameEnum

        :return: List of objects uri 
        :rtype: List[str]

        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        result_uris = []
        try:
            if dcat_class_name and (dcat_class_name == DcatClassNameEnum.DATASET or dcat_class_name == DcatClassNameEnum.DATASERVICE):
                if dcat_class_name == DcatClassNameEnum.DATASET:
                    subject_name ='dataset_1' 
                    # Get references to unreferenced described dataset in a catalog (dcat.dataset metadata)
                    query = f'''
                        SELECT DISTINCT ?{subject_name} FROM {self._get_uriref_to_query(self.graph_uri)} WHERE {{ 
                            ?{subject_name} {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Dataset)} .
                            FILTER NOT EXISTS {{ 
                                ?catalog_1 {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Catalog)} . 
                                ?catalog_1 {self._get_uriref_to_query(DCAT.dataset)} ?{subject_name} .
                            }}
                        }}
                        '''
                else:
                    subject_name ='dataservice_1' 
                    # Get references to unreferenced described dataservices in a catalog (dcat.service metadata)
                    query = f'''
                        SELECT DISTINCT ?{subject_name} FROM {graph_uri} WHERE {{ 
                            ?{subject_name} {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.DataService)} .
                            FILTER NOT EXISTS {{ 
                                ?catalog_1 {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.Catalog)} . 
                                ?catalog_1 {self._get_uriref_to_query(DCAT.service)} ?{subject_name} .
                            }}
                        }}
                        '''
                result_uris = self.get_objects_by_query(query, subject_name)
                if result_uris:
                    def _delete_uri_batch(current_uris):
                        batch_uris = ", ".join([self._get_uriref_to_query(result_uri) for result_uri in current_uris])
                        delete_query = f'''DELETE {{ GRAPH {graph_uri} {{ ?s ?p ?o . }} }} 
                                           WHERE {{ GRAPH {graph_uri} {{  ?s ?p ?o .  FILTER (?o IN ({batch_uris})) }} }}'''
                        self._get_results_by_query(delete_query)

                    self._process_uri_batches(result_uris, _delete_uri_batch, method_log_prefix)
                    log.info(f'{method_log_prefix} Removed unreferenced described {dcat_class_name} in {graph_uri}: {result_uris}')
            
        except (RDFStoreInternalException) as e:
            log.exception(f'{method_log_prefix} An exception has occurred removing undescribed {dcat_class_name} in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e) from e
        return result_uris

    @log_debug
    def remove_catalog_records(self) -> List[str]:
        '''
        Remove catalogRecords of RDF and the reference to a Catalog

        :return: List of objects uri 
        :rtype: List[str]

        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        result_uris = []
        try:
            subject_name ='catalog_record_1' 
            query = f'''
                SELECT DISTINCT ?{subject_name} FROM {graph_uri} WHERE {{ 
                    ?{subject_name} {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.CatalogRecord)} .
                }}
                '''
            result_uris = self.get_objects_by_query(query, subject_name)
            if result_uris:
                def _delete_uri_batch(current_uris):
                    batch_uris = ", ".join([self._get_uriref_to_query(result_uri) for result_uri in current_uris])
                    delete_query = f'''DELETE {{ GRAPH {graph_uri} {{ ?s ?p ?o . }} }} 
                                       WHERE {{ GRAPH {graph_uri} {{ 
                                           ?s ?p ?o .
                                           FILTER (?s IN ({batch_uris}) || ?o IN ({batch_uris}))
                                       }} }}'''
                    self._get_results_by_query(delete_query)

                self._process_uri_batches(result_uris, _delete_uri_batch, method_log_prefix)
                log.info(f'{method_log_prefix} Removed catalog records in {graph_uri}')
        except (RDFStoreInternalException) as e:
            log.exception(f'{method_log_prefix} An exception has occurred removing catalog records in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e) from e
        return result_uris

    @log_debug
    def remove_pagination_data(self) -> None:
        '''
        Remove pagination data of catalogs in a graph (metadata dct:hasPart of Catalog)

        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        try:
            query = f'''DELETE {{ GRAPH {graph_uri} {{ ?s ?p ?o . }} }} 
                        WHERE {{ GRAPH {graph_uri} {{  ?s ?p ?o . FILTER (
                        STRSTARTS(STR(?s), "{HYDRA}") || STRSTARTS(STR(?p), "{HYDRA}") || STRSTARTS(STR(?o), "{HYDRA}"))
                        }} }}'''
                
            self._get_results_by_query(query)
            log.info(f'{method_log_prefix} Removed pagination data in {graph_uri}')
        except (RDFStoreInternalException) as e:
            log.exception(f'{method_log_prefix} An exception has occurred removing undescribed dataservices in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e) from e
        return None

    @log_debug
    def delete_data_publishers_in_graph(self) -> List[str]:
        '''
        Delete data from publishers in graph in Virtuoso

        :return: a list of uri publishers or creators
        :rtype: List[str]

        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        uris_publishers_and_creators = []
        try:
            query = f'''SELECT DISTINCT ?o FROM {graph_uri} WHERE {{ ?s ?p ?o . 
                    FILTER (?p in ({self._get_uriref_to_query(DCT.publisher)}, {self._get_uriref_to_query(DCT.creator)}))
                    FILTER(isIRI(?o) && STRSTARTS(STR(?o), '{DCATAPESPrefixConstants.PUBLISHER_PREFIX}'))}}'''
            
            uris_publishers_and_creators = self.get_objects_by_query(query, 'o')
            if uris_publishers_and_creators:
                def _delete_uri_batch(current_uris):
                    batch_uris = ", ".join([self._get_uriref_to_query(uri) for uri in current_uris])
                    metadata_query = f'''DELETE {{ GRAPH {graph_uri} {{ ?s ?p ?o . }} }} WHERE {{  GRAPH {graph_uri} {{ ?s ?p ?o . 
                        FILTER (?s IN ({batch_uris})) }} }}'''
                    self._get_results_by_query(metadata_query)

                self._process_uri_batches(uris_publishers_and_creators, _delete_uri_batch, method_log_prefix)
                log.info(f'{method_log_prefix} Removed data of publihsers in {graph_uri}: {uris_publishers_and_creators}')
        except (RDFStoreInternalException) as e:
            log.exception(f'{method_log_prefix} An exception has occurred deleting data from nti-risp publishers and creators in graph = {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e) from e
        return uris_publishers_and_creators
    
    @log_debug
    def delete_internal_metadata_of_dataset_or_dataservice_and_its_catalog_record(self, dataset_or_dataservice_uri:str) -> None:
        ''' Remove all metadada of a dataset or a dataservice except triple with predicate RDF.type, 
            all metadata of its catalog record except triples with predicates RDF.type and FOAF.primary typic, 
            and last remove all unreferenced nodes.
        
            :param dataset_or_dataaservice_uri: Uri of dataset or dataservice
            :type dataset_or_dataaservice_uri: str
            
            raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        graph_uri = self.get_graph_uri_to_query()
        try:
            metadata_query = f'''DELETE {{ GRAPH {graph_uri} {{ {self._get_uriref_to_query(dataset_or_dataservice_uri)} ?p ?o . }} }}
                                WHERE {{ GRAPH {graph_uri} {{ {self._get_uriref_to_query(dataset_or_dataservice_uri)} ?p ?o . 
                                FILTER(?p != rdf:type) }} }}'''
            self._get_results_by_query(metadata_query)
            record_metadata_query = f"""DELETE {{ GRAPH {graph_uri} {{ ?s_record ?p_record ?o_record . }} }}
                                    WHERE {{ GRAPH {graph_uri} {{
                                    ?s_record {self._get_uriref_to_query(FOAF.primaryTopic)} {self._get_uriref_to_query(dataset_or_dataservice_uri)} .
                                    ?s_record ?p_record ?o_record .
                                    FILTER(?p_record != {self._get_uriref_to_query(FOAF.primaryTopic)} &&
                                    !(?p_record = rdf:type && ?o_record = {self._get_uriref_to_query(DCAT.CatalogRecord)}))
                                }} }}"""
            self._get_results_by_query(record_metadata_query)
            log.info(f'{method_log_prefix} Deleted internal metadata of {dataset_or_dataservice_uri} and its catalog record in {graph_uri}: {uris_publishers_and_creators}')
            self.drop_all_unreferenced_nodes()
        except (RDFStoreInternalException) as e:
            log.exception(f'{method_log_prefix} An exception has occurred deleting internal metadata of the dataset or dataservice {dataset_or_dataservice_uri} and its CatalogRecord in graph = {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e) from e
