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
import time
import inspect
from pyshacl import validate
from rdflib import ConjunctiveGraph, Graph #, URIRef, BNode
from rdflib.exceptions import ParserError
from typing import List, Tuple
from ...utils import load_graph_from_source
from ...decorators import log_debug, log_info
from .shacl_results_formatter import format_shacl_validation_results

log = logging.getLogger(__name__)

class ShaclValidatorException(Exception):
    def __init__(self, msg=None):
        Exception.__init__(self, msg)
        self.msg = msg

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
                                                            do_owl_imports=False)#,
                                                            #serialize_report_graph='turtle')
            #log.info(f'{method_log_prefix} \nConforms={conforms}; \nresults_graph={results_graph.serialize()}; \nresults_text={results_text}')
            messages = format_shacl_validation_results(results_graph, data_graph)
        except (AttributeError, RuntimeError, Exception) as e:
            log.debug(f'{method_log_prefix} Exception:{e}. Time: {time.time() - ini} seconds.')
            raise ShaclValidatorException(e)
        return conforms, messages