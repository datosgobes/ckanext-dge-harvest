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

import logging
import inspect
from rdflib import Graph, URIRef, BNode, Literal
from urllib.error import HTTPError
from ckan.plugins.toolkit import config
from .decorators import log_info
from .utils import load_graph_from_source, safe_n3_uriref, from_str_to_uriref
from .harvester_config_reader import HarvesterConfigReader
from .rdf_store  import RDFStoreException, RDFStoreInsertOrUpdate, RDFStoreQuery, RDFStoreHelper
from urllib.error import HTTPError
from .constants.dcat_ap_es_constants import (DCATAPESConfigConstants as CC, SKOS_NAMESPACE,
                                            DCATAPESPrefixConstants as PrefixConstants)


log = logging.getLogger(__name__)


@log_info
def dge_harvester_update_vocabularies(havester_config_file_path:str) -> str:
    '''
    Remove the vocabularies graph and creates it again with the updated vocabularies

    :param havester_config_file_path: harvester config file path for all properties related to this federation.
            The method use three properties of this file:
            - vocabularies.graph_name: roperty that contains the graph name where the vocabularies will be stores
            - vocabularies.uris: property that contains the list of vocabularies URIs
            - vocabularies.uris.different_download_uri: property that contains the vocabularies whose download uri is different from the vocabulary URI. Format <vocabulary_uri>|<download_uri>
    :type havester_config_file_path: str
    '''
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    harvester_config_reader = HarvesterConfigReader(havester_config_file_path)
    graph_name = None
    vocabularies = None
    messages = []
    graph_name = harvester_config_reader.get_property(CC.SECTION_BASIC, 'vocabularies.graph_name', None)
    if not graph_name:
        raise ValueError("Graph name not found")    
    log.info(f"{method_log_prefix} Vocabularies are going to be updated in {graph_name}")
    rdf_store = RDFStoreInsertOrUpdate(graph_name)
    rdf_store.drop_graph()
    messages.append(f"Remove {graph_name} graph")
    vocabularies = harvester_config_reader.get_section_property_as_a_list(CC.SECTION_BASIC, 'vocabularies.uris', [])
    log.info(f'{method_log_prefix} download_uris={vocabularies}')
    if not vocabularies:
        messages.append(f"No vocabularies to update. Review vocabularies.uris property value in {havester_config_file_path}")
    else:
        download_uris = harvester_config_reader.get_section_property_as_a_str_dict(CC.SECTION_BASIC, 'vocabularies.uris.different_download_uri', None, '|')
        log.info(f'{method_log_prefix} download_uris={download_uris}')
        for vocabulary_uri in vocabularies:
            try:
                download_uri = download_uris.get(vocabulary_uri, None)
                log.info(f"{method_log_prefix} Trying update vocabulary {vocabulary_uri} from {download_uri or vocabulary_uri}")
                vocabulary_graph = load_graph_from_source(download_uri or vocabulary_uri)
                rdf_store.insert_rdf_data(vocabulary_graph) 
                log.info(f"{method_log_prefix} Updated vocabulary {vocabulary_uri}")
                messages.append(f"{vocabulary_uri} was stored successfully.")
            except (RuntimeError, HTTPError, RDFStoreException) as e:
                log.error(f"{method_log_prefix} Error updating vocabulary {vocabulary_uri}")
                messages.append(f"{vocabulary_uri} was not be stored: {str(e)}.")
    return "\n".join(messages)

def dge_harvest_get_vocabulary_element_labels(vocabulary_element_uri:str, havester_config_file_path:str=None) -> dict[str,str]:
    """
    Retrieve the labels (prefLabel) of a vocabulary element from the RDF graph.

    If the labels are not already stored in the graph, they are fetched from the vocabulary element's URI
    and inserted into the graph.

    :param vocabulary_element_uri: The URI of the vocabulary element whose labels are to be retrieved.
    :type vocabulary_element_uri: str
    :param havester_config_file_path: Path to the harvester configuration file. If not provided, it will use
                                      the default configuration path from the CKAN configuration.
    :type havester_config_file_path: str, optional
    :return: A dictionary where the keys are language codes (e.g., "en", "es") and the values are the labels
             in those languages.
    :rtype: dict[str, str]
    """
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    labels = {}
    graph_name = None
    try:
        graph_name = _get_graph_name(havester_config_file_path)
        log.info(f"{method_log_prefix} Labels are going to be got from {graph_name}")
        rdf_store = RDFStoreQuery(graph_name)
        if not rdf_store or not vocabulary_element_uri:
            return labels

        query = f"SELECT DISTINCT ?o FROM {safe_n3_uriref(graph_name)} WHERE {{ {safe_n3_uriref(vocabulary_element_uri)} {safe_n3_uriref(SKOS_NAMESPACE.prefLabel)} ?o }}"
        results = rdf_store._get_results_by_query(query)
        for result in results or []:
            _type = result['o'].get('type', None)
            _lang = result['o'].get('xml:lang', None)
            _value = result['o'].get('value', None)
            if _type and _type == 'literal' and _lang and _value:
                labels[_lang] = _value
        if not labels:
            labels = dge_harvest_insert_vocabulary_element_labels(vocabulary_element_uri, havester_config_file_path)
        log.info(f"{method_log_prefix} Labels = {labels}")
    except Exception as e:
        log.error(f"{method_log_prefix} Exception getting labels of {vocabulary_element_uri} from graph {graph_name or ''} {type(e)}: {str(e)}", exc_info=True)
        labels = None
    return labels

def dge_harvest_insert_vocabulary_element_labels(vocabulary_element_uri:str, havester_config_file_path:str=None):
    """
    Fetch and insert the labels (prefLabel) of a vocabulary element into the RDF graph.

    This method retrieves the labels from the vocabulary element's URI, filters them based on the offered
    languages configured in CKAN, and inserts the valid labels into the RDF graph.

    :param vocabulary_element_uri: The URI of the vocabulary element whose labels are to be fetched and inserted.
    :type vocabulary_element_uri: str
    :param havester_config_file_path: Path to the harvester configuration file. If not provided, it will use
                                      the default configuration path from the CKAN configuration.
    :type havester_config_file_path: str, optional
    :return: A dictionary where the keys are language codes (e.g., "en", "es") and the values are the labels
             in those languages.
    :rtype: dict[str, str]
    """
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    labels = {}
    try:
        offered_languages = config.get('ckan.locales_offered', '').split()
        element_uris, predicate, ckeck_stored_vocabulary = _dge_harvest_get_config_element(vocabulary_element_uri, offered_languages)
        if not element_uris or not offered_languages:
            return labels
        if not predicate:
            log.info(f'{method_log_prefix} {vocabulary_element_uri} has not a RDF where ask label')
            return labels
        graph_name = _get_graph_name(havester_config_file_path)
        rdf_store = RDFStoreInsertOrUpdate(graph_name)
        if ckeck_stored_vocabulary:
            query = f'''ASK WHERE {{ GRAPH {safe_n3_uriref(graph_name)} {{ {safe_n3_uriref(vocabulary_element_uri)} {safe_n3_uriref(SKOS_NAMESPACE.inScheme)} ?o . }} }}'''
            stored_element_vocabulary = rdf_store.get_result_of_ask_query(query)
            if not stored_element_vocabulary:
                log.info(f'{method_log_prefix} {vocabulary_element_uri} is not an element vocabulary in graph {graph_name}')
                return labels
        labels = _dge_harvest_get_and_insert_labels(element_uris, vocabulary_element_uri, predicate, offered_languages, graph_name, rdf_store)
    except Exception as e:
        log.error(f'{method_log_prefix} Exception adding labels of {vocabulary_element_uri} in graph {graph_name or ""} {type(e)}: {str(e)}', exc_info=True)
        labels = None
    return labels

def _dge_harvest_get_config_element(vocabulary_element_uri, offered_languages):
    _element_uri = [vocabulary_element_uri]
    _predicate = SKOS_NAMESPACE.prefLabel
    ckeck_stored_vocabulary = True
    if vocabulary_element_uri:
        if _is_geonames_vocabulary_element(vocabulary_element_uri):
            _element_uri = [vocabulary_element_uri.replace('https://', 'http://') + 'about.rdf']
            _predicate = "http://www.geonames.org/ontology#alternateName"
            ckeck_stored_vocabulary = False
        elif _is_inspire_vocabulary_element(vocabulary_element_uri):
            _element_uri.clear()
            term = vocabulary_element_uri.rsplit("/", 1)[-1]
            if offered_languages:
                for lang in offered_languages:
                    _element_uri.append(f'{vocabulary_element_uri}/{term}.{lang}.rdf')
            _predicate = SKOS_NAMESPACE.prefLabel
            ckeck_stored_vocabulary = False
        elif _is_iana_vocabulary_element(vocabulary_element_uri):
            _predicate = None
            ckeck_stored_vocabulary= None
    return _element_uri, _predicate, ckeck_stored_vocabulary

def _dge_harvest_get_and_insert_labels(element_uris, vocabulary_element_uri, predicate, offered_languages, graph_name, rdf_store):
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    labels = {}
    if not element_uris:
        log.info(f'{method_log_prefix} No RDFs founded for {vocabulary_element_uri}  where search labels ')
        return labels
    triples_to_add, labels = _dge_harvest_get_label_triples(vocabulary_element_uri, element_uris, predicate, offered_languages)
    if triples_to_add:
        log.info(f'{method_log_prefix} Adding labels: {labels} of {vocabulary_element_uri} in graph {graph_name or ""}')
        rdf_store.insert_triples_list_into_graph(triples_to_add)
        log.info(f'{method_log_prefix} Added labels: {labels} of {vocabulary_element_uri} in graph {graph_name or ""}')
    else:
        log.info(f'{method_log_prefix} No labels founded for {vocabulary_element_uri}')
    return labels

def _dge_harvest_get_label_triples(vocabulary_element_uri, element_uris, predicate, offered_languages):
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    triples_to_add = []
    labels = {}
    for element_uri in element_uris:
        log.info(f'Trying go get {element_uri}')
        vocabulary_element_graph = None
        try:
            vocabulary_element_graph = load_graph_from_source(element_uri)
        except Exception as e:
            log.info(f'{method_log_prefix} Exception {type(e)} trying getting content of {element_uri}: {str(e)}')
            continue
        if not vocabulary_element_graph:
            log.info(f'{method_log_prefix} No recovered labels for {vocabulary_element_uri}')
            continue
        vocabulary_element_uri_to_search_in_graph = vocabulary_element_uri
        if _is_geonames_vocabulary_element(vocabulary_element_uri):
            vocabulary_element_uri_to_search_in_graph = vocabulary_element_uri.replace('http://', 'https://')
        pref_label_triples = vocabulary_element_graph.triples((from_str_to_uriref(vocabulary_element_uri_to_search_in_graph), from_str_to_uriref(predicate), None))
        for s, p, o in pref_label_triples or []:
            if (isinstance(o, Literal) and o.language and 
                o.language in offered_languages and str(o)):
                triples_to_add.append((from_str_to_uriref(vocabulary_element_uri), from_str_to_uriref(SKOS_NAMESPACE.prefLabel), o))
                labels[o.language] = str(o)
    return triples_to_add, labels

def dge_harvest_delete_vocabulary_element_labels(vocabulary_element_uri:str, havester_config_file_path:str=None):
    """
    Delete all labels (prefLabel) of a vocabulary element from the RDF graph.

    This method removes all triples in the RDF graph where the subject is the vocabulary element's URI,
    the predicate is `skos:prefLabel`, and the object is any value.

    :param vocabulary_element_uri: The URI of the vocabulary element whose labels are to be deleted.
    :type vocabulary_element_uri: str
    :param havester_config_file_path: Path to the harvester configuration file. If not provided, it will use
                                      the default configuration path from the CKAN configuration.
    :type havester_config_file_path: str, optional
    """
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    try:
        graph_name = _get_graph_name(havester_config_file_path)
        rdf_store = RDFStoreHelper(graph_name)
        query = f'''DELETE  WHERE {{ GRAPH {safe_n3_uriref(graph_name)} 
                {{ {safe_n3_uriref(vocabulary_element_uri)} {safe_n3_uriref(SKOS_NAMESPACE.prefLabel)} ?o }} }}'''
        log.info(f'{method_log_prefix} Deleting triples prefLabel of {vocabulary_element_uri}')
        rdf_store._get_results_by_query(query)
        log.info(f'{method_log_prefix} Deleted triples prefLabel of {vocabulary_element_uri}')
    except Exception as e:
        log.error(f"{method_log_prefix} Exception deleting labels of {vocabulary_element_uri} from graph {graph_name or ''} {type(e)}: {str(e)}", exc_info=True)

def dge_harvest_update_vocabulary_element_labels(vocabulary_element_uri:str, havester_config_file_path:str=None): 
    """
    Delete all labels (prefLabel) of a vocabulary element from the RDF graph.

    This method removes all triples in the RDF graph where the subject is the vocabulary element's URI,
    the predicate is `skos:prefLabel`, and the object is any value.

    :param vocabulary_element_uri: The URI of the vocabulary element whose labels are to be deleted.
    :type vocabulary_element_uri: str
    :param havester_config_file_path: Path to the harvester configuration file. If not provided, it will use
                                      the default configuration path from the CKAN configuration.
    :type havester_config_file_path: str, optional
    """
    dge_harvest_delete_vocabulary_element_labels(vocabulary_element_uri, havester_config_file_path)
    return dge_harvest_insert_vocabulary_element_labels(vocabulary_element_uri, havester_config_file_path)

def _get_graph_name(havester_config_file_path:str=None):
    havester_config_file_path = havester_config_file_path or config.get('ckanext.dge_harvest.dcat_ap_es_1_0_0.config.filepath', '')
    harvester_config_reader = HarvesterConfigReader(havester_config_file_path)
    _property = 'vocabularies.graph_name'
    graph_name = harvester_config_reader.get_property(CC.SECTION_BASIC, _property, None)
    if not graph_name:
        raise ValueError(f"Graph name not found in property {_property} in {havester_config_file_path}")
    return graph_name

def _is_inspire_vocabulary_element(vocabulary_element_uri):
    return vocabulary_element_uri.startswith((PrefixConstants.INSPIRE_PREFIX))

def _is_geonames_vocabulary_element(vocabulary_element_uri):
    return vocabulary_element_uri.startswith((PrefixConstants.SPATIAL_GEONAMES_PREFIX, PrefixConstants.SPATIAL_GEONAMES_HTTPS_PREFIX))

def _is_iana_vocabulary_element(vocabulary_element_uri):
    return vocabulary_element_uri.startswith((PrefixConstants.FORMAT_PREFIX_EDP_IANA, PrefixConstants.FORMAT_PREFIX_EDP_IANA_HTTP))
