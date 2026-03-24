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
import time
import re
from typing import List, Tuple, Set
from SPARQLWrapper import SPARQLWrapper, DIGEST, GET, JSON, QueryResult
from SPARQLWrapper import RDF as RDF_FORMAT
from SPARQLWrapper.SPARQLExceptions import SPARQLWrapperException, EndPointNotFound
from urllib.error import HTTPError, URLError
from rdflib import Graph, BNode, Literal, URIRef
from ckantoolkit import config

from ckan.plugins.toolkit import config
from ..constants.dcat_ap_es_constants import RDF as RDF_NAMESPACE, XSD
from ..constants import DCATAPESConfigConstants as ConfigConstants
from ..decorators import log_debug, log_info
from ..utils import safe_n3_uriref, from_str_to_uriref, get_int_value_from_ckan_property
from rdflib import Graph, BNode, Literal, URIRef

log = logging.getLogger(__name__)

class RDFStoreInternalException(Exception):
    def __init__(self, msg=None) -> None:
        Exception.__init__(self, msg)
        self.msg = msg

class RDFStoreException(RDFStoreInternalException):
    def __init__(self, msg=None) -> None:
        Exception.__init__(self, msg)
        self.msg = msg

class RDFStore():
    '''
    Class that contains utils basic method to store and get info from graphs in virtuoso
    '''
    BATCH_SIZE_FOR_INSERTS = get_int_value_from_ckan_property('ckanext.dge_harvest.virtuoso.batch_size.inserts', 1000)
    BATCH_SIZE_FOR_INSERTS_MIN = get_int_value_from_ckan_property('ckanext.dge_harvest.virtuoso.batch_size.inserts.min', 1)
    BATCH_SIZE_FOR_UPDATES = get_int_value_from_ckan_property('ckanext.dge_harvest.virtuoso.batch_size.updates', 500)
    BATCH_SIZE_FOR_UPDATES_MIN = get_int_value_from_ckan_property('ckanext.dge_harvest.virtuoso.batch_size.updates.min', 1)
    BATCH_SIZE_FOR_DELETES = get_int_value_from_ckan_property('ckanext.dge_harvest.virtuoso.batch_size.deletes', 10)
    BATCH_SIZE_FOR_DELETES_MIN = get_int_value_from_ckan_property('ckanext.dge_harvest.virtuoso.batch_size.deletes.min', 1)

    def _get_log_prefix(self, method_name):
        return f'[{self.__class__.__name__}][{method_name}]'

    def _get_raise_exception(self, exception: RDFStoreInternalException) -> RDFStoreException:
        '''
        Return the exception if it a RDFStoreException or a new RDFStore exception if it is a RDFStoreInteralExceptio.
        Out of these methos always return RDFStoreInternalException
        '''
        return exception if isinstance(exception, RDFStoreException) else RDFStoreException(str(exception))

    def __init__(self, graph_uri:str) -> None:
        '''
        Create a connection to virtuoso to update content

        :return: SPARQLWrapper
        :rtype: SPARQLWrapper
        '''
        endpoint = config.get('ckanext.dge_harvest.virtuoso.sparql.auth.endpoint', None)
        username = config.get('ckanext.dge_harvest.virtuoso.username', None)
        pwd = config.get('ckanext.dge_harvest.virtuoso.password', None)
        self.sparql = None
        if endpoint:
            self.sparql = SPARQLWrapper(endpoint)
        if username and pwd:
            self.sparql.setHTTPAuth(DIGEST)
            self.sparql.setCredentials(username, pwd)

        self.max_triples_per_query = get_int_value_from_ckan_property('ckanext.dge_harvest.virtuoso.max_triples_per_query',ConfigConstants.TRIPLES_PER_QUERY)
        self.max_attempts = get_int_value_from_ckan_property('ckanext.dge_harvest.max_attempts', 2)

        self.graph_uri = None
        self.update_graph_uri(graph_uri)

    def _get_uriref_from_str_value(self, value) -> URIRef:
        return from_str_to_uriref(value)

    def _get_uriref_to_query(self, value) -> str:
        return safe_n3_uriref(value)

    def update_graph_uri(self, graph_uri:str):
        self.graph_uri = None
        if graph_uri:
            self.graph_uri = self._get_uriref_from_str_value(graph_uri)

    def get_graph_uri(self) -> URIRef:
        '''
        Get the graph uri of the object.
        :raise RDFStoreException if not graph_uri
        '''
        if not self.graph_uri:
            raise RDFStoreException('A graph uri is mandatory')
        return self.graph_uri

    def get_graph_uri_to_query(self) -> str:
        '''
        Get the graph uri to a query.
        :raise RDFStoreException if not graph_uri
        '''
        return self._get_uriref_to_query(self.graph_uri)

    def _set_query(self, query: str, method: str=GET, return_format: str=RDF_FORMAT) -> None:
        '''
        Set the query, the invocation mehtod and the return format to the sparql wrapper object

        :param query: The query to execute
        :type query: str

        :param query: The invocation method, GET by default
        :type query: str

        :param query: The return format, RDF by default
        :type query: str
        '''
        self.sparql.resetQuery()
        self.sparql.setMethod(method)
        self.sparql.setQuery(query)
        if return_format:
            self.sparql.setReturnFormat(return_format)

    def _set_and_execute_sparql_query_to_virtuoso(self, query: str, method: str=GET, return_format: str=RDF_FORMAT) -> QueryResult:
        '''
        Set method and query parameters an execute the query

        :param query: The query to execute
        :type query: str

        :param query: The invocation method, GET by default
        :type query: str

        :param query: The return format, RDF by default
        :type query: str

        :return: Query result
        :rtype: :class:`QueryResult` instance

        :raise RDFStoreInternalException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        result = None
        self._set_query(query, method, return_format)
        attempt = 0
        while attempt < self.max_attempts:
            try:
                result = self.sparql.query()
                return result
            except (URLError, EndPointNotFound) as e:
                attempt += 1
                log.warning(f'{method_log_prefix} Attempt {attempt}/{self.max_attempts} An exception has occurred executing query {query}, with method {method} and return format = {return_format}. {type(e).__name__}: {str(e)}')
                if attempt < self.max_attempts:
                    time.sleep(2)
                else:
                    raise RDFStoreInternalException(str(e))
            except (SPARQLWrapperException, Exception) as e:
                log.error(f'{method_log_prefix} An exception has occurred executing query {query}, with method {method} and return format = {return_format}. {type(e).__name__}: {str(e)}', exc_info=True)
                raise RDFStoreInternalException(str(e))

    def _set_execute_and_convert_sparql_query_to_virtuoso(self, query: str, method: str=GET, return_format: str=RDF_FORMAT) ->  "QueryResult.ConvertResult":
        '''
        Set method and query parameters an execute the query

        :param query: The query to execute
        :type query: str

        :param query: The invocation method, GET by default
        :type query: str

        :param query: The return format, RDF by default
        :type query: str

        :return: the converted query result.
        :rtype: :class:`QueryResult.ConvertResult` instance, str

        :raise RDFStoreInternalException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        result = None
        attempt = 0
        while attempt < self.max_attempts:
            try:
                self._set_query(query, method, return_format)
                result = self.sparql.queryAndConvert()
                return result
            except (URLError, EndPointNotFound) as e:
                attempt += 1
                log.warning(f'{method_log_prefix} Attempt {attempt}/{self.max_attempts} An exception has occurred executing query {query}, with method {method} and return format = {return_format}. {type(e).__name__}: {str(e)}')
                if attempt < self.max_attempts:
                    time.sleep(2)
                else:
                    raise RDFStoreInternalException(str(e))
            except (SPARQLWrapperException, Exception) as e:
                log.error(f'{method_log_prefix} An exception has occurred executing query {query}, with method {method} and return format = {return_format}. {type(e).__name__}: {str(e)}', exc_info=True)
                raise RDFStoreInternalException(str(e))

    def _get_subjects_by_predicate_and_object(self, predicate_value: str, object_value: str, distinct:bool = False) -> List[str]:
        '''
        Get subjects for specific predicate and object in a graph

        :param predicate_value: predicate of the triple
        :type predicate_value: str

        :param object_value: object of the triple
        :type object_value: str

        :param distinct: True if distinct values, False in other case
        :type distinct: bool

        :return: List of subject uris
        :rtype: List[str]
        '''
        graph = self.get_graph_uri_to_query()
        result_uris = []
        object_value_query = f'{self._get_uriref_to_query(object_value)}' if object_value else '?o'
        predicate_value_query = f'{self._get_uriref_to_query(predicate_value)}' if predicate_value else '?p'
        query = f"SELECT{' DISTINCT' if distinct else ''} ?s FROM {graph} WHERE {{ ?s {predicate_value_query} {object_value_query} }}"
        results = self._set_execute_and_convert_sparql_query_to_virtuoso(query=query, method=GET, return_format=JSON)
        for result in results["results"]["bindings"]:
            result_uris.append(result['s']['value'])
        return result_uris

    def _get_objects_by_subject_and_predicate(self, subject_value: str, predicate_value: str, distinct: bool=False) -> List[str]:
        '''
        Get objects for specific predicate and subject in a graph

        :param subject_value: subject of the triple. None if any subject
        :type subject_value: str

        :param predicate_value: predicate of the triple. None if any predicate
        :type predicate_value: str

        :param distinct: True if get distinct objects, False if other case
        :type distinct: bool

        :return: List of objects uris
        :rtype: List[str]
        '''
        result_uris = []
        graph = self.get_graph_uri_to_query()
        subject_value_query = f'{self._get_uriref_to_query(subject_value)}' if subject_value else '?s'
        predicate_value_query = f'{self._get_uriref_to_query(predicate_value)}' if predicate_value else '?p'
        query = f"SELECT{' DISTINCT' if distinct else ''} ?o FROM {graph} WHERE {{ {subject_value_query} {predicate_value_query} ?o }}"
        result_uris = self.get_objects_by_query(query, 'o')
        return result_uris

    def _get_type_triple_from_subject_if_exists(self, subject_uri_or_bnode, object_to_check):
        '''
        Retrieve an object from "graph_uri" using "subject_uri_or_bnode" as the subject and "RDF.type" as the predicate.
        If the object is retrieved, check if it matches "object_to_check". If it matches, return a triple
        with "subject_uri_or_bnode" as the subject, "RDF.type" as the predicate and the retrieved object as the object.
        If no object is retrieved, return None.

        :param subject_uri_or_bnode: subject to use in query
        :type subject_uri_or_bnode: str
        
        :param object_to_check: object to compare with the retrieved object in query
        :type object_to_check: str

        :return: A triple with the object retrieved. None if nothing was retrieved from the query
        :rtype: tuple(:class:`rdflib.term.URIRef` | :class:`rdflib.term.BNode`, :class:`rdflib.term.URIRef`, :class:`rdflib.term.URIRef`) | None
        '''
        graph_uri = self.get_graph_uri_to_query()
        triple = None
        query = f'''SELECT ?o FROM {graph_uri} WHERE {{ {self._get_uriref_to_query(subject_uri_or_bnode)} {self._get_uriref_to_query(RDF_NAMESPACE.type)} ?o . }}'''
        result = self._get_results_by_query(query=query)
        if result and result[0]['o']['type'] == 'uri' and object_to_check == URIRef(result[0]['o']['value']):
            triple_object = URIRef(result[0]['o']['value'])
            triple = (subject_uri_or_bnode, RDF_NAMESPACE.type, triple_object)
        return triple

    @log_debug
    def get_result_of_ask_query(self, ask_query:str) -> bool:
        '''
        Get the result True or False of an ask query
        
        :param ask_query: ask query to execute
        :type ask_query: str

        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        result = False
        try:
            if ask_query:
                result = self._set_execute_and_convert_sparql_query_to_virtuoso(query=ask_query, method=GET, return_format=JSON)
                result = result["boolean"] if result else False
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred executing query = {ask_query}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        return result

    def _get_results_by_query(self, query:str) -> List[str]:
        '''
        Get a list of object value as the result of a query

        :param query: query to execute
        :type query: str

        :return: List of objects uri
        :rtype: List[str]
        '''
        result_list = []
        if query:
            results = self._set_execute_and_convert_sparql_query_to_virtuoso(query=query, method=GET, return_format=JSON)
            if results and results["results"] and results["results"]["bindings"]:
                result_list = results["results"]["bindings"]
        return result_list

    @log_debug
    def get_objects_by_query(self, query:str, object_name:str='o') -> List[str]:
        '''
        Get a list of object value as the result of a query

        :param query: query to execute
        :type query: str

        :param object_name: name of object to get. 'o' by default
        :type query: str

        :return: List of objects uri
        :rtype: List[str]

        :raise RDFStoreException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        result_uris = []
        try:
            if query:
                results = self._get_results_by_query(query=query)
                if results:
                    result_uris = [result[object_name]['value'] for result in results]
        except (RDFStoreInternalException) as e:
            log.error(f'{method_log_prefix} An exception has occurred getting data objects by query={query}. {type(e).__name__}: {str(e)}')
            raise self._get_raise_exception(e)
        return result_uris

    def _check_if_only_one_subject_by_object_uri(self, object_uri) -> bool:
        '''
        Check if an URI-type object has only one subject associated

        :param object_uri: URI of the object
        :type object_uri: str

        :return: whether the URI-type object has only one subject associated
        :rtype: bool

        :raise: RDFStoreException
        '''
        graph_uri = self.get_graph_uri_to_query()
        has_only_one_subject = False
        query = f"""SELECT ?s ?p ?o FROM {graph_uri} WHERE {{ ?s ?p ?o. FILTER (?o = {self._get_uriref_to_query(object_uri)}) }}"""
        results = self.get_objects_by_query(query, 's')
        if results and len(results) > 0:
            if len(results) > 1:
                has_only_one_subject = False
            else:
                has_only_one_subject = True
        return has_only_one_subject

    def _check_if_is_triple_nt_with_xsd_duration_value_and_get_duration_value(self, triple_in_nt_format: str) -> bool:
        '''
        Check if the triple in nt format has a xsd:duration value and get these duration value
        
        :param triple_in_nt_format: triple in nt format
        :rtype triple_in_nt_format: str
        
        :return str with duration value or None
        :rtype str
        '''
        duration_value = None
        regex_duration = r'"[^"]+"\^\^<http://www.w3.org/2001/XMLSchema#duration>'
        if triple_in_nt_format:
            match = re.search(regex_duration, triple_in_nt_format)
            if match:
                duration_value = match.group(0).split('^^')[0].strip('"')
        return duration_value

    @log_debug
    def _complete_all_param_values_of_duration_value(self, duration_value:str) -> str:
        '''
        Completes all parameter values ​​of a duration with ISO 8601 format ((P) Years, Months, Weeks, Days (T) Hours, Minutes, Seconds.)
        Fills with a value of 0 those that did not come in the original value
        '''
        result = duration_value
        if duration_value:
            negative_duration = str(duration_value).startswith('-')
            str_duration = str(duration_value).lstrip('-')
            pattern = re.compile(r'P(?:(?P<years>\d+)Y)?(?:(?P<months>\d+)M)?(?:(?P<weeks>\d+)W)?(?:(?P<days>\d+)D)?'
                    r'(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?')
            match = pattern.fullmatch(str_duration)
            if match:
                # Extrcat values and complete with 
                values = {k: int(v) if v else 0 for k, v in match.groupdict().items()}
                # Build the new duration with all values
                result = f'P{values["years"]}Y{values["months"]}M{values["weeks"]}W{values["days"]}DT{values["hours"]}H{values["minutes"]}M{values["seconds"]}S'
                result = f'-{result}' if negative_duration else result
        return result

    def _replace_blank_nodes(self, graph_to_update: Graph, blank_node_prefix:str):
        """
        Replace automatically blank nodes to URIs

        :param graph_to_update: graph where replace blank nodes
        :rtype graph_to_update: Graph
        
        :param blank_node_prefix: prefix to update blank nodes
        :rtype blank_node_prefix: str
        
        :returns: new grpah without bland nodes
        :rtype Graph
        
        """
        def get_n3_bnode_identifier(bnode):
            try:
                return bnode.n3().strip('_:')
            except Exception:
                return str(bnode)

        def get_bnode_identifier(bnode):
            try:
                return bnode.identifier
            except AttributeError:
                return get_n3_bnode_identifier(bnode)
                
        
        mapping = {}  
        new_graph = Graph()  
        
        for s, p, o in graph_to_update:
            if isinstance(s, BNode):
                if s not in mapping:
                    mapping[s] = URIRef(f"{blank_node_prefix}/bnode/{get_bnode_identifier(s)}")
                s = mapping[s]

            if isinstance(o, BNode):
                if o not in mapping:
                    mapping[o] = URIRef(f"{blank_node_prefix}/bnode/{get_bnode_identifier(o)}")
                o = mapping[o]
            
            new_graph.add((s, p, o))     
        return new_graph
    
    def _encode_uris_of_graph(self, graph_to_encode: Graph):
        """
        Encode URIs

        :param graph_to_update: graph where encode URIRef
        :rtype graph_to_update: Graph
        
        :returns: new grpah with encoded URIRef
        :rtype Graph        
        """
        encoded_graph = Graph()
        for s, p, o in graph_to_encode:
            encoded_s = self._get_uriref_from_str_value(s) if isinstance(s, URIRef) else s
            encoded_p = self._get_uriref_from_str_value(p) if isinstance(p, URIRef) else p
            encoded_o = self._get_uriref_from_str_value(o) if isinstance(o, URIRef) else o
            encoded_graph.add((encoded_s, encoded_p, encoded_o))
        return encoded_graph
