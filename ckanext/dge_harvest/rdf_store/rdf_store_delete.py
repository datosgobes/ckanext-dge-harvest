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
from typing import List, Set
from SPARQLWrapper import  QueryResult
from urllib.error import HTTPError
from rdflib import Namespace, URIRef
from ..constants.dcat_ap_es_constants import DCAT, RDF_NAMESPACE, DCT, HYDRA, FOAF, DCATAPESPrefixConstants, DcatClassNameEnum
from ..constants.constants import RDFStoreConstants
from .rdf_store_helper import RDFStoreHelper, RDFStoreException, RDFStoreInternalException
from ..decorators import log_debug, log_info

log = logging.getLogger(__name__)

class RDFStoreDelete(RDFStoreHelper):
    '''
    Class that contains utils method to delete data in virtuoso
    '''
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
            log.error(f'{method_log_prefix} An exception has occurred deleting catalogs in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
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
            result = self._drop_triples_in_graph(triples_to_delete)
            log.info(f'{method_log_prefix} Deleted data of {dataservice_uri} in graph {graph_uri}')

        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred deleting of {dataservice_uri} data in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
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
            triples_to_delete_str = '\n'.join([f"{URIRef(s)} {URIRef(p)} {URIRef(o)} ." for s, p, o in triples_to_delete])
            
            # Obtain IRIs of distributions linked to the dataset (distribution and sample)
            distribution_list = self._get_objects_by_subject_and_predicate(dataset_uri, DCAT.distribution, True)
            distribution_sample_list = self._get_objects_by_subject_and_predicate(dataset_uri, ADMS.sample, True)
            distribution_list.extend(distribution_sample_list)
            filter_distributions = ''
            if distribution_list:
                distribution_list_str = [f"{self._get_uriref_to_query(distribution_uri)}" for distribution_uri in distribution_list]
                distribution_list_str = ', '.join(distribution_list_str)
                filter_distributions = f'?distribution ?p2 ?o2 . FILTER( ?distribution IN ({distribution_list_str})) .'

            # Deletion query for the dataset
            try:
                query = f'''DELETE {{ GRAPH {graph_uri} {{ {self._get_uriref_to_query(dataset_uri)} ?p ?o . }} }} 
                            WHERE {{ GRAPH {graph_uri} {{ {self._get_uriref_to_query(dataset_uri)} ?p ?o . {filter_distributions} {triples_to_delete_str} }} }}'''
                result = self._get_results_by_query(query)
                log.info(f'{method_log_prefix} Deleted data of {dataset_uri} in graph {graph_uri} using a single query')
            except (RDFStoreInternalException) as e:
                log.error(f'{method_log_prefix} An exception has occurred deleting of {dataset_uri} data in graph {graph_uri} using a single query. The deletion will be attempted in batch queries. {type(e).__name__}: {str(e)}')
                query = f'''DELETE {{ GRAPH {graph_uri} {{ {self._get_uriref_to_query(dataset_uri)} ?p ?o . }} }} 
                            WHERE {{ GRAPH {graph_uri} {{ {self._get_uriref_to_query(dataset_uri)} ?p ?o . {filter_distributions} }} }}'''
                result = self._get_results_by_query(query)
                result = self._drop_triples_in_graph(triples_to_delete)
                log.info(f'{method_log_prefix} Deleted data of {dataset_uri} in graph {graph_uri} using batch queries')
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred deleting of {dataset_uri} data in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
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
            MAX_NUM_OF_ITERATIONS = 20
            iteration = 0
            while True and iteration < MAX_NUM_OF_ITERATIONS:
                # Find non referened_nodes
                find_nodes_query = f""" SELECT DISTINCT ?node_subject FROM {graph_uri} WHERE {{ 
                    ?node_subject ?p ?o .
                    FILTER NOT EXISTS {{ ?s ?any_predicate ?node_subject }} # It is not an object
                    FILTER (?node_subject != {self._get_uriref_to_query(root_catalog)}) # Except root catalog
                    }}"""
                non_referenced_node_uris = self.get_objects_by_query(find_nodes_query, 'node_subject')
                if not non_referenced_node_uris:
                    break
                else:
                    triples_to_delete = []
                    for i, non_referenced_node_uri in enumerate(non_referenced_node_uris or [], start=0):
                        unreferenced_nodes.add(str(non_referenced_node_uri))
                        triples_to_delete = [(f'{self._get_uriref_to_query(non_referenced_node_uri)}', f'?p{i}', f'?o{i}') ]
                        self._drop_triples_in_graph(triples_to_delete)
                iteration +=1
                log.debug(f'{method_log_prefix} Deleted all unreferenced nodes in {iteration} iterations.')
            if iteration == MAX_NUM_OF_ITERATIONS:
                log.warning(f'{method_log_prefix} The maximum number of iterations has been reached. The node may not have been completely removed. It would be necessary to check that the queries are correct.')
                raise RDFStoreInternalException(f'Unreferenced nodes {non_referenced_node_uris} have not been completely removed in graph {graph_uri}')

        except (KeyError, RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred deleting non referenced nodes in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
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
            log.error(f'{method_log_prefix} An exception has occurred removing undescribed catalogs in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
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
            log.error(f'{method_log_prefix} An exception has occurred removing undescribed {dcat_class_name}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
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
            log.error(f'{method_log_prefix} An exception has occurred removing unreferenced {dcat_class_name} in catalogs in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
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
            # Delete all triples where node is object and delete unreferenced nodes
            if result_uris:
                result_uris_to_delete = ", ".join([self._get_uriref_to_query(result_uri) for result_uri in result_uris])
                query = f'''DELETE {{ GRAPH {graph_uri} {{ ?s ?p ?o . }} }} 
                            WHERE {{ GRAPH {graph_uri} {{  ?s ?p ?o .  FILTER (?o IN ({result_uris_to_delete})) }} }}'''
                self._get_results_by_query(query)
                log.info(f'{method_log_prefix} Removed unreferenced described {dcat_class_name} in {graph_uri}: {result_uris}')
                self.drop_all_unreferenced_nodes()
            
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred removing undescribed {dcat_class_name} in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
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
        try:
            query = f'''DELETE {{ GRAPH {graph_uri} {{ ?s ?p ?o . }} }} 
                        WHERE {{ GRAPH {graph_uri} {{  ?s ?p ?o . FILTER (?p in {self._get_uriref_to_query(FOAF.primaryTopic)}, {self._get_uriref_to_query(DCAT.record)} ) }} }}'''
            subject_name ='catalog_record_1' 
            query = f'''
                SELECT DISTINCT ?{subject_name} FROM {graph_uri} WHERE {{ 
                    ?{subject_name} {self._get_uriref_to_query(RDF_NAMESPACE.type)} {self._get_uriref_to_query(DCAT.CatalogRecord)} .
                }}
                '''
            result_uris = self.get_objects_by_query(query, subject_name)
            if result_uris:
                query = f'''DELETE {{ GRAPH {graph_uri} {{ ?s ?p ?o . }} }} 
                            WHERE {{ GRAPH {graph_uri} {{  ?s ?p ?o . FILTER (?o IN ({", ".join([self._get_uriref_to_query(result_uri) for result_uri in result_uris])})) }} }}'''
                self._get_results_by_query(query)
                log.info(f'{method_log_prefix} Removed catalog records in {graph_uri}')
                self.drop_all_unreferenced_nodes()
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred removing catalog records in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
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
            log.error(f'{method_log_prefix} An exception has occurred removing undescribed dataservices in graph {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
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
                # Delete triples where publisher is a subject
                metadata_query = f'''DELETE {{ GRAPH {graph_uri} {{ ?s ?p ?o . }} }} WHERE {{  GRAPH {graph_uri} {{ ?s ?p ?o . 
                    FILTER (?s IN ({", ".join([self._get_uriref_to_query(uri) for uri in uris_publishers_and_creators])})) }} }}'''
                self._get_results_by_query(metadata_query)
                log.info(f'{method_log_prefix} Removed data of publihsers in {graph_uri}: {uris_publishers_and_creators}')
                self.drop_all_unreferenced_nodes()
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred deleting data from nti-risp publishers and creators in graph = {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
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
            log.error(f'{method_log_prefix} An exception has occurred deleting internal metadata of the dataset or dataservice {dataset_or_dataservice_uri} and its CatalogRecord in graph = {graph_uri}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
