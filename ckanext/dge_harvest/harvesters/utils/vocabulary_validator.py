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
from rdflib.namespace import SKOS
from rdflib import Graph, URIRef, BNode, Literal
from typing import List, Tuple, Union
from ...rdf_store  import RDFStoreHelper
from ...decorators import log_debug, log_info
from ...utils import safe_n3_uriref

log = logging.getLogger(__name__)

class VocabularyValidatorException(Exception):
    def __init__(self, msg=None):
        Exception.__init__(self, msg)
        self.msg = msg

class VocabularyValidator():
    '''
    VocabularyValidator
    '''
    def _get_log_prefix(self, method_name):
        return f'[{self.__class__.__name__}][{method_name}]'

    def __init__(self, rdf_store:RDFStoreHelper, vocabularies:List[str], vocabulary_graph_name:str, elements_belonging_to_vocabulary:dict[str, List[str]] = {}, elements_unbelonging_to_vocabulary:dict[str, List[str]] = {}):
        '''
        :param rdf_store: RDF Store with the connection to store where the vocabulary graph is stored
        :type rdf_store: RDFStoreHelper

        :param vocabulary_graph_name: Graph name where vocabulary is stored in rdf store. 
        :type vocabulary_to_check: str

        :param elements_belonging_to_vocabulary: Dictionary with vocabulary_uri and list of checked elements that belong to the vocabulary
        :type elements_belonging_to_vocabulary: dict[str, List[str]]

        :param elements_unbelonging_to_vocabulary: Dictionary with vocabulary_uri and list of checked elements that not belong to the vocabulary
        :type elements_unbelonging_to_vocabulary: dict[str, List[str]]
        '''
        self.rdf_store = rdf_store
        self.vocabulary_graph_name = vocabulary_graph_name
        self.vocabularies =  vocabularies or []
        self.elements_belonging_to_vocabulary = elements_belonging_to_vocabulary if elements_belonging_to_vocabulary is not None else {}
        self.elements_unbelonging_to_vocabulary = elements_unbelonging_to_vocabulary if elements_unbelonging_to_vocabulary is not None else {}

    def update_vocabulary_store(self, rdf_store:RDFStoreHelper, clean_checked_elements: bool=False):
        '''
        Update RDF store where vocabularies is stores
        
        :param rdf_store: RDF Store with the connection to store where the vocabulary graph is stored
        :type rdf_store: RDFStoreHelper
        
        :param clean_checked_elements: True if clean dictionaries with checked elements, False in other case
        :type clean_checked_elements: bool
        '''
        self.rdf_store = rdf_store
        if clean_checked_elements:
            self.clean_checked_elements()

    def vocabulary_graph_name(self, vocabulary_graph_name:str, clean_checked_elements: bool=False):
        '''
        Update graph_name where vocabulary is stores
        
        :param vocabulary_graph_name: Graph name where vocabulary is stored in rdf store. 
        :type vocabulary_graph_name: str
        
        :param clean_checked_elements: True if clean dictionaries with checked elements, False in other case
        :type clean_checked_elements: bool
        '''
        self.vocabulary_graph_name = vocabulary_graph_name
        if clean_checked_elements:
            self.clean_checked_elements()

    def clean_checked_elements(self):
        '''
        Clean dictionaries with checked elements
        '''
        self.elements_belonging_to_vocabulary.clear()
        self.elements_unbelonging_to_vocabulary.clear()

    def _filter_triples(self, graph_to_validate:Graph, vocabulary_uri:str, metadata:List[str]) -> List[str]:
        '''
        Filter triples of a graph depends on vocabulary and the list of metadata to validate

        :param graph_to_validate: Graph to validate vocabularies
        :type graph_to_validate: Graph

        :param vocabulary_uri: Vocabulary URIs to check. 
        :type vocabulary_uri: str

        :param metadata: List of metadata to validate
        :type metadata: List[str]
        '''
        filtered_triples = []
        for predicate in metadata or []:
            filtered_triples.extend([(s, p, o) for s, p, o in graph_to_validate if isinstance(o, URIRef) and str(o).startswith(vocabulary_uri) and isinstance(p,URIRef) and str(p)==predicate])
        return filtered_triples

    @log_debug
    def check_element_of_vocabulary_in_rdf_store(self, vocabulary_uri:str, vocabulary_element_uri:str) -> bool:
        '''
        check if a vocabulary element uri is in vocabulary

        :param vocabulary_uri: Vocabulary URIs to check. 
        :type vocabulary_uri: str
        
        :param vocabulary_element_uri: Vocabulary element URI to check. 
        :type vocabulary_element_uri: str

        :returns: True if the element uri in vocabulary uri
        :rtype bool
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        if not self.rdf_store or not vocabulary_uri or not vocabulary_element_uri:
            return False
        
        query = f'''ASK {{ GRAPH {safe_n3_uriref(self.vocabulary_graph_name)} {{ 
                        {safe_n3_uriref(vocabulary_element_uri)} {safe_n3_uriref(SKOS.inScheme)} {safe_n3_uriref(vocabulary_uri)} . 
                        {{ {safe_n3_uriref(vocabulary_element_uri)} {safe_n3_uriref(SKOS.topConceptOf)}  {safe_n3_uriref(vocabulary_uri)} .  }} 
                        UNION {{ {safe_n3_uriref(vocabulary_uri)} {safe_n3_uriref(SKOS.hasTopConcept)} {safe_n3_uriref(vocabulary_element_uri)} . }} 
                        }} }}'''
        result = self.rdf_store.get_result_of_ask_query(query)
        log.debug(f'{method_log_prefix} {vocabulary_element_uri} is {"not" if not result else ""} in {vocabulary_uri}')
        return result

    @log_info
    def check_vocabulary(self, graph_to_validate:Graph, vocabulary_uri:str, metadata:List[str]):
        '''
        check if the graph to validate has right elements a vocabulary

        :param graph_to_validate: Graph to validate vocabularies
        :type graph_to_validate: Graph

        :param rdf_store:
        :type rdf_store: RDFStore

        :param vocabulary_check: Vocabulary URIs to check. 
        :type vocabulary_to_check: str

        :param metadata: List of metadata to validate
        :type metadata: List[str]

        :returns: List of messages of metadata with values not in vocabulary
        :rtype List[str]
        ''' 
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        if not graph_to_validate or not self.rdf_store or not vocabulary_uri:
            return []
        messages = []
        # filter triples
        filtered_triples = self._filter_triples(graph_to_validate, vocabulary_uri, metadata)
        for s, p, o in filtered_triples or []:
            if str(o) in self.elements_belonging_to_vocabulary.get(vocabulary_uri, set()):
                # right value
                continue
            elif str(o) in self.elements_unbelonging_to_vocabulary.get(vocabulary_uri, set()):
                # wrong value; write message
                messages.append(f'{str(o)} is not an element of {vocabulary_uri} vocabulary. It is not a valid value for {str(p)}.')
            else:
                # query to sparql
                log.debug(f'{method_log_prefix} consult to .... {self.vocabulary_graph_name}')
                if self.vocabulary_graph_name:
                    self._check_vocabulary_element(str(vocabulary_uri), str(o), messages)
        return messages

    def _check_vocabulary_element(self, vocabulary_uri, vocabulary_element_uri, messages):
        if not messages:
            messages = []
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        exist = self.check_element_of_vocabulary_in_rdf_store(vocabulary_uri, vocabulary_element_uri)
        log.debug(f'{method_log_prefix} exist.... {exist}')
        if exist:
            if self.elements_belonging_to_vocabulary.get(vocabulary_uri) is None:
                self.elements_belonging_to_vocabulary[vocabulary_uri] = set()
            self.elements_belonging_to_vocabulary[vocabulary_uri].add(vocabulary_uri)
            log.debug(f'{method_log_prefix} elements_belonging_to_vocabulary.... {self.elements_belonging_to_vocabulary}')
        else:
            if self.elements_unbelonging_to_vocabulary.get(vocabulary_uri) is None:
                self.elements_unbelonging_to_vocabulary[vocabulary_uri] = set()
            self.elements_unbelonging_to_vocabulary[vocabulary_uri].add(vocabulary_uri)
            messages.append(f'{vocabulary_element_uri} is not an element of {vocabulary_uri} vocabulary. It is not a valid value for {str(p)}.')
            log.debug(f'{method_log_prefix} elements_unbelonging_to_vocabulary.... {self.elements_unbelonging_to_vocabulary}')

    @log_info
    def check_vocabularies(self, graph_to_validate:Graph, vocabularies_metadata_to_check:dict[str,List[str]]={}) -> List[str]:
        '''
        check if the graph to validate has right elements of vocabularies

        :param graph_to_validate: Graph to validate vocabularies
        :type graph_to_validate: Graph

        :param vocabularies_to_check: Dictionary where the key is a uri of a vocabulary allowed and the value is a list of metadata to validate against said vocabulary. List of vocaburaries URIs to check. These vocabularies must be in self.vocabularies 
        :type vocabularies_to_check: dict[str, List[str]]

        :returns: List of messages of metadata with values not in vocabularies
        :rtype List[str]
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        messages = []
        if vocabularies_metadata_to_check is None:
            vocabularies_metadata_to_check = {}
        vocabularies_to_check = vocabularies_metadata_to_check.keys()
        for vocabulary_uri in vocabularies_to_check:
            if vocabulary_uri not in self.vocabularies:
                log.debug(f'{method_log_prefix} {vocabulary_uri} is not an allowed vocabulary. It will not be checked.')
                continue
            log.debug(f'{method_log_prefix} Checking.... {vocabulary_uri}')
            messages.extend(self.check_vocabulary(graph_to_validate, vocabulary_uri, vocabularies_metadata_to_check.get(vocabulary_uri, [])))
        log.debug(f'{method_log_prefix} messages.... {messages}')
        return messages
