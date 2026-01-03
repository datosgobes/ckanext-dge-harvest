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
import time
import inspect
from ckantoolkit import config
from rdflib.namespace import RDF, SH
from pyshacl import validate
from rdflib import ConjunctiveGraph, Graph, URIRef, BNode
from rdflib.exceptions import ParserError
from typing import List, Tuple, Union
from urllib import request
from urllib.error import HTTPError
from ...utils import load_graph_from_source
from ...decorators import log_debug, log_info
from ...constants.dcat_ap_es_constants import NAMESPACES

log = logging.getLogger(__name__)

class ShaclValidatorException(Exception):
    def __init__(self, msg=None):
        Exception.__init__(self, msg)
        self.msg = msg

class ShaclValidationResult():
    '''
    Information from a ValidationResult of a SHACL validation
    '''    
    def _get_log_prefix(self, method_name):
        return f'[{self.__class__.__name__}][{method_name}]'

    def __init__(self, focus_node = None, focus_node_type = None, result_path = None, source_constraint = None, source_shape = None,  
                 source_info_str = None, result_message = None, details = [], more_info_url = None, node_value = None, severity = None):
        self.focus_node = focus_node
        self.focus_node_type = focus_node_type
        self.result_path = result_path
        self.source_constraint = source_constraint
        self.source_shape = source_shape
        self.source_info_str = source_info_str
        self.result_message = result_message
        self.details = details
        self.more_info_url = more_info_url
        self.node_value = node_value
        self.severity = severity

    def build_message(self, level):
        result_str = []
        separator = '\r\n'
        if not level:
            level = 1
        tabs = ''.join('\t' for _ in range(level))
        if level == 1:
            result_str.append(f'''[SHACL {self.severity.upper() if self.severity else ''}]''')
        else:
            result_str.append(f'''\r\n{tabs}Severity: {self.severity or ''}.''')  
        # focus node
        if self.focus_node:
            type_to_show = f' [{self.focus_node_type}]' if self.focus_node_type else ''
            result_str.append(f'''{separator}{tabs}Focus node: {self.focus_node}{type_to_show}.''')
        # Result Message
        if self.result_message:
            result_str.append(f'''{separator}{tabs}Result Message: {self.result_message}.''')
        # Result Path
        if self.result_path:
            result_str.append(f'''{separator}{tabs}Result Path: {self.result_path}.''')
        # SourceConstraintComponent
        if self.source_constraint:
            result_str.append(f'''{separator}{tabs}Source constraint component: {self.source_constraint}.''')
        #Source Shape
        if self.source_shape:
            source_shape_info = f' {self.source_info_str}' if self.source_info_str else f'{self.source_shape}'
            result_str.append(f'''{separator}{tabs}Source shape: {source_shape_info}.''')
        #Value
        if self.node_value:
            result_str.append(f'''{separator}{tabs}Value node: {self.node_value}.''')
        # Details
        if self.details:
            result_str.append(f'''{separator}{tabs}Details:''')
        for detail in self.details or []:
            result_str.append(f'{separator}{tabs}[{detail.build_message(level + 1)}{separator}{tabs}]')

        #More info ulr
        if level == 1 and self.more_info_url:
            result_str.append(f'''{separator}{tabs}See more detail in {self.more_info_url}.''')
        message = ''.join(result_str)
        return message

class ShaclValidator():    
    def _get_log_prefix(self, method_name):
        return f'[{self.__class__.__name__}][{method_name}]'

    def __init__(self, shacl_shapes_uri_list:List[str]=None, ontology_uri_list: List[str]=None) -> None:
        '''
        This is a SHACL validator
        
        :param ontology_uri_list: List of ontology URIs used in SHACL validation  
        :rtype ontology_uri_list: List[str]
        '''
        self.ontology_graph = None
        self.shacl_shapes_graph = None
        self.load_ontology_graph(ontology_uri_list)
        self.load_shacl_shapes_graph(shacl_shapes_uri_list)

    @log_debug
    def load_ontology_graph(self, ontology_uri_list: List[str]) -> None:
        '''
        Load in ontology_graph a graph with the content of the uris in ontology_uri_list
        
        :param ontology_uri_list: List of ontology URIs or paths used in SHACL validation  
        :rtype ontology_uri_list: List[str]
        '''
        if not ontology_uri_list:
            self.ontology_graph = None
            return
        self.ontology_graph = self._get_graph_from_file_paths(ontology_uri_list, is_conjunctive_graph = True)

    @log_debug
    def load_shacl_shapes_graph(self, shacl_shapes_uri_list: List[str]) -> None:
        '''
        Load in shacl_shapes_graph a graph with the content of the uris in shacl_shapes_uri_list

        :param shacl_shapes_uri_list: List of shacl shapes URIs or paths used in SHACL validation  
        :rtype shacl_shapes_uri_list: List[str]
        '''
        if not shacl_shapes_uri_list:
            self.shacl_shapes_graph = None
            return
        self.shacl_shapes_graph = self._get_graph_from_file_paths(shacl_shapes_uri_list, is_conjunctive_graph = False)

    def _get_metadata_or_class(self, uri_ref: str) -> Tuple[str, str, str]:
        '''
        Gets the part of the uri_ref from the last # or /
        
        :param uri_ref: URI
        :type uri_ref: str
        
        :returns: the namespace, the prefix namespace and the metadata_name
        :rtype: Tuple[str, str, str]
        '''
        namespace = None
        metadata_name = None
        namespace_prefix = None
        index = -1
        if uri_ref:
            index = uri_ref.rfind('#')
            if index == -1:
                index = uri_ref.rfind('/')
            namespace = uri_ref[:index+1] if index > -1 and (index+1) < len(uri_ref)  else uri_ref
            namespace_prefix = next((k for k, v in NAMESPACES.items() if v == namespace), None)
            metadata_name = uri_ref[index+1:] if index > -1 and (index+1) < len(uri_ref) else ''
        return namespace, namespace_prefix, metadata_name

    def _get_node_info(self, node:Union[BNode, URIRef], results_graph:Graph) -> str:
        '''
        Get the info of node in results_graph
        
        :param node: Node to get info
        :type node: Union[BNode, URIRef]
        
        :param result_graph: Graph to get info
        :type result_graph: Graph
        
        :returns: str with the info of node in result_graph
        :rtype: str
        '''
        node_info = []
        for predicate, object in  results_graph.predicate_objects(subject=node):
            object_info = ''
            object_type = type(object)
            if object_type:
                if object_type == BNode:
                    object_info = self._get_node_info(object, results_graph)
                    object_info = f' {object_info} ' if object_info else ''
                else:
                    object_info = object
            node_info.append(f'{predicate} {object_info}')
        result = ''
        if len(node_info):
            result = f'[ {"; ".join(node_info)} ]'
        return result

    def _get_validation_result_info(self, validation_result: Union[BNode, URIRef], results_graph: Graph, data_graph: Graph, nested_validation_result:bool = False):
        '''
        Build a list of report messages found in a resuls_graph
        
        :param validation_result: the BNode or URIRef of the node than contains de validation result
        :type validation_result: Union[BNode, URIRef]
        
        :param results_graph: the Graph object built according to the SHACL specification's Validation Report structure
        :type results_graph: rdflib.Graph
        
        :param data_graph: the validated graph
        :type data_graph: rdflib.Graph
        
        :returns: a list with the report messages
        :rtype: list
        
        '''  
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        shacl_validation_result = ShaclValidationResult()
        try:

            # SEVERITY
            result_severity = results_graph.value(validation_result, SH.resultSeverity)
            severity = self._get_metadata_or_class(result_severity)
            shacl_validation_result.severity = severity[2] or result_severity

            # SOURCE SHAPE
            shacl_validation_result.source_shape = results_graph.value(validation_result, SH.sourceShape)
            shacl_validation_result.source_info_str = self._get_node_info(shacl_validation_result.source_shape, results_graph)

            #FOCUS NODE
            shacl_validation_result.focus_node = results_graph.value(validation_result, SH.focusNode)
            focus_node_type_in_result_graph = results_graph.value(shacl_validation_result.focus_node, RDF.type)
            focus_node_type_in_data_graph = data_graph.value(shacl_validation_result.focus_node, RDF.type)
            shacl_validation_result.focus_node_type = focus_node_type_in_data_graph or focus_node_type_in_result_graph or ''
            _class_node_namespace, class_node_prefix, class_node_name = (self._get_metadata_or_class(shacl_validation_result.focus_node_type))
            if focus_node_type_in_result_graph:
                shacl_validation_result.focus_node = self._get_node_info(shacl_validation_result.focus_node, results_graph)

            # VALUE
            shacl_validation_result.node_value = results_graph.value(validation_result, SH.value)

            # RESULT PATH
            shacl_validation_result.result_path = results_graph.value(validation_result, SH.resultPath)
            _metadata_namespace, metadata_prefix, metadata_name= self._get_metadata_or_class(shacl_validation_result.result_path)

            # MESSAGE
            shacl_validation_result.result_message = results_graph.value(validation_result, SH.resultMessage)

            # CONSTRAINT
            shacl_validation_result.source_constraint = results_graph.value(validation_result, SH.sourceConstraintComponent)

            if not nested_validation_result:
                dcat_ap_es_page = config.get('ckanext.dge_harvest.dge_dcat_ap_es.url', None)
                dcat_ap_es_prefix = config.get('ckanext.dge_harvest.dge_dcat_ap_es.prefix', '')
                if dcat_ap_es_page and class_node_name and metadata_name:
                    shacl_validation_result.more_info_url = f'{dcat_ap_es_page}#{dcat_ap_es_prefix}-{class_node_prefix.lower() or ""}_{class_node_name.lower()}-{metadata_prefix.lower() or ""}_{metadata_name.lower()}'

        except (AttributeError, TypeError) as e:
            log.error(f'{method_log_prefix} Exception {type(e)} --> {str(e)}')
        return shacl_validation_result

    def _get_validation_result_nested_nodes(self, validation_result: Union[BNode, URIRef], results_graph:Graph, data_graph:Graph) -> List[ShaclValidationResult]:
        '''
        Get a list of validation result nodes nested whithin a validation result node via the SH.detail metadata
        
        :param validation_result: the BNode or URIRef of the node than contains de validation result
        :type validation_result: Union[BNode, URIRef]

        :param results_graph: the Graph object built according to the SHACL specification's Validation Report structure
        :type results_graph: rdflib.Graph
        
        :param data_graph: the data graph
        :type data_graph: rdflib.Graph
        
        :returns: a list with nested validation results nodes
        :rtype: list(ShaclValidationResult)
        
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        results = []
        nested_validation_results = set(results_graph.objects(validation_result, SH.detail) or [])
        for nested_validation_result in nested_validation_results:
            nested_validation_result_type = results_graph.value(validation_result, RDF.type)
            log.debug(f'{method_log_prefix} processing the nested node {nested_validation_result} of type {nested_validation_result_type or ""}')
            if nested_validation_result_type and nested_validation_result_type == SH.ValidationResult:
                nested_validation_result_object = self._get_validation_result_info(nested_validation_result, results_graph, data_graph, True)
                nested_validation_result_object.details = self._get_validation_result_nested_nodes(nested_validation_result, results_graph, data_graph)
                results.append(nested_validation_result_object)
        return results

    def _get_validation_report_info(self, results_graph: Graph, data_graph: Graph) -> List[str]:
        '''
        Build a list of report messages found in a resuls_graph
        
        :param results_graph: the Graph object built according to the SHACL specification's Validation Report structure
        :type results_graph: rdflib.Graph
        
        :param data_graph: the validated graph
        :type data_graph: rdflib.Graph
        
        :returns: a list with the report messages
        :rtype: list
        
        '''  
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            messages = []
            root_nodes = results_graph.subjects(RDF.type, SH.ValidationReport)
            for root_node in root_nodes or []:
                validation_results = set(results_graph.objects(root_node, SH.result) or [])
                for validation_result in validation_results:
                    validation_result_type = results_graph.value(validation_result, RDF.type)
                    if validation_result_type and validation_result_type == SH.ValidationResult:
                        validation_result_object = self._get_validation_result_info(validation_result, results_graph, data_graph, False)
                        validation_result_object.details = self._get_validation_result_nested_nodes(validation_result, results_graph, data_graph)
                        message = validation_result_object.build_message(1)
                        messages.append(message)
        except (AttributeError, TypeError) as e:
            log.error(f'{method_log_prefix} Error building validation_report_info. Exception {type(e).__name__}: str(e)')
            raise ShaclValidatorException(e)
        return messages

    def _get_graph_from_file_paths(self, file_path_list: List[str], is_conjunctive_graph: bool) -> Graph:
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            if not file_path_list:
                return None
            graph = Graph()
            if is_conjunctive_graph:
                graph = ConjunctiveGraph()
            for file_path in file_path_list or []:
                graph += load_graph_from_source(file_path)
        except (ParserError, Exception) as e:
            log.error(f'{method_log_prefix}. Error building graph from files. Exception {type(e).__name__}: {str(e)}')
            raise ShaclValidatorException(str(e))
        return graph

    @log_info
    def check_shacl_validation(self, data_graph: ConjunctiveGraph) -> Tuple[bool, list[str]]:
        '''
        Validate a data_graph against the shapes and ontologies of the object.
        
        :param data_graph: the graph to be validated
        :type data_graph: rdflib.Graph
                
        :returns: a tuple (conforms, messages) where conforms is true if the data_graph conforms to the shacl_graph or false in other case
                and messages is a list with the report messages
        :rtype: (bool, list)
        '''  

        conforms, messages = self._check_validation(data_graph, self.shacl_shapes_graph, self.ontology_graph)
        return conforms, messages

    @log_debug
    def _check_validation(self, data_graph:Graph, shapes_graph:Graph, ontology_graph:Graph) -> Tuple[bool, list[str]]: 
        '''
        Validate a data_graph against a shape and an ontology graphs.
        
        :param data_graph: the graph to be validated
        :type data_graph: rdflib.Graph
        
        :param shapes_graph: the graph containing the SHACL shapes to validate or None if the SHACL shapes are included in the data_graph
        :type shapes_graph: rdflib.Graph
        
        :param ontology_graph: the graph containing extra ontological information, or None if not required
        :type ontology_graph: rdflib.Graph
        
        :returns: a tuple (conforms, messages) where conforms is true if the data_graph conforms to the shacl_graph or false in other case
                and messages is a list with the report messages
        :rtype: (bool, list)
        '''  
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        ini = time.time()
        try:
            # Validate https://github.com/RDFLib/pySHACL/tree/v0.27.0

            conforms, results_graph, results_text = validate(
                                                            data_graph=data_graph,
                                                            data_graph_format = 'ttl',
                                                            shacl_graph=shapes_graph,
                                                            shacl_graph_format = 'ttl',
                                                            ont_graph=ontology_graph,
                                                            inference='rdfs',#'options:  'rdfs', 'owlrl', 'both', or 'none'
                                                            inplace=False,
                                                            max_validation_depth = None,
                                                            abort_on_first=False,
                                                            allow_infos=True,
                                                            allow_warnings=True,
                                                            meta_shacl=False, 
                                                            advanced=True,
                                                            js=False,
                                                            debug=False,
                                                            do_owl_imports=False)
            log.info(f'{method_log_prefix} \nConforms={conforms}; \nresults_graph={results_graph.serialize()}; \nresults_text={results_text}')
            messages = self._get_validation_report_info(results_graph, data_graph)
        except (AttributeError, RuntimeError, Exception) as e:
            log.debug(f'{method_log_prefix} Exception:{e}. Time: {time.time() - ini} seconds.')
            raise ShaclValidatorException(e)
        return conforms, messages