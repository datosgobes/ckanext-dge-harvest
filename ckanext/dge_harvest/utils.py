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

from __future__ import print_function
import logging
import uuid
import inspect
from pathlib import Path
from io import BytesIO, UnsupportedOperation
from pyshacl.rdfutil import load
from rdflib import Graph, URIRef, BNode, Literal
from rdflib.exceptions import ParserError
from typing import Tuple
from urllib.error import HTTPError
from ckan.plugins.toolkit import config
from ckan import model
import ckan.plugins.toolkit as toolkit
from ckanext.dcat.utils import catalog_uri, dataset_id_from_resource
from ckanext.harvest.model import (HarvestJob)
from .decorators import log_debug, log_info
from .constants import CommonPackageConstants, HarvesterConstants
from ckanext.dcat.profiles import CleanedURIRef

_ = toolkit._

log = logging.getLogger(__name__)

DATASERVICE = "dataservice"
CATALOGO = "catalogo"
HTTP_SCHEME = 'http:'
HTTPS_SCHEME = 'https:'

def _build_package_uri(data_dict, subdirectory):
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    prefix_uri = f"{catalog_uri().rstrip('/')}/{subdirectory}/" if subdirectory else f"{catalog_uri().rstrip('/')}"
    data_dict = data_dict or {}
    uri = None
    if not uri and data_dict.get('name'):
        uri = f"{prefix_uri}{data_dict['name']}"
    if not uri:
        uri = data_dict.get('uri')
    if not uri:
        for extra in data_dict.get('extras', []):
            if extra['key'] == 'uri' and extra['value'] != 'None':
                uri = extra['value']
                break

    if not uri and data_dict.get('id'):
        uri = f"{prefix_uri}{data_dict['id']}"
    if not uri:
        uri = f"{prefix_uri}{str(uuid.uuid4())}"
        log.warning(f'{method_log_prefix} Using a random id for package URI')
    return uri

def dge_harvest_dataset_uri(dataset_dict):
    '''
    Returns an URI for the dataset

    This will be used to uniquely reference the dataset on the RDF
    serializations.

    The value will be the first found of:

        1. `catalog_uri()` + '/catalogo/' + `name` field
        2. The value of the `uri` field
        3. The value of an extra with key `uri`
        4. `catalog_uri()` + '/catalogo/' + `id` field
    
    Check the documentation for `catalog_uri()` for the recommended ways of
    setting it.
    
    Returns a string with the dataset URI.
    '''
    return _build_package_uri(dataset_dict, CATALOGO)

def dge_harvest_dataservice_uri(dataservice_dict):
    '''
    Returns an URI for the dataservice

    This will be used to uniquely reference the dataservice on the RDF
    serializations.

    The value will be the first found of:

        1. `catalog_uri()` + '/catalogo/' + `name` field
        2. The value of the `uri` field
        3. The value of an extra with key `uri`
        4. `catalog_uri()` + '/catalogo/' + `id` field

    Check the documentation for `catalog_uri()` for the recommended ways of
    setting it.

    Returns a string with the dataset URI.
        '''
    return _build_package_uri(dataservice_dict, CATALOGO)

def dge_harvest_resource_uri(resource_dict, dataset_dict):
    '''
    Returns an URI for the resource

    This will be used to uniquely reference the resource on the RDF
    serializations.

    The value will be the first found of:

        1. The value of the `uri` field
        2. `catalog_uri()` + '/catalogo/' + `package_id` + '/resource/'
            + `id` field

    Check the documentation for `catalog_uri()` for the recommended ways of
    setting it.

    Returns a string with the resource URI.
    '''
    uri = resource_dict.get('uri')
    if not uri or uri == 'None':
        dataset_identifier = None
        if dataset_dict:            
            dataset_id = dataset_dict.get('id', None)
            resource_dataset_id = resource_dict.get('package_id', None)
            dataset_name = dataset_dict.get('name', None)
            if dataset_id and resource_dataset_id and dataset_name and dataset_id == resource_dataset_id:
                dataset_identifier = dataset_name
        if not dataset_identifier:
            dataset_identifier = dataset_id_from_resource(resource_dict)
        
        uri = f"{catalog_uri().rstrip('/')}/{CATALOGO}/{dataset_identifier}/resource/{resource_dict['id']}"
    return uri

def dge_harvest_build_catalog_record_uriref(entity_uri_ref: URIRef) -> URIRef:
    '''
    Build the CatalogRecord URIRef for an URIRef entity
    '''
    if entity_uri_ref:
        return URIRef(f'{str(entity_uri_ref)}{CommonPackageConstants.CATALOG_RECORD_URI_SUFFIX}')
    return None

@log_debug
def load_graph_from_source(path_or_uri_source: str) -> Graph:
    '''
    Load the content of a source. Based on method load_from_source(pySHACL)

    :param path_or_uri_source: URI or path to load content
    :rtype path_or_uri_source: str
    '''
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    result_graph = None
    try:
        if not path_or_uri_source:
            return result_graph
        open_source = None
        filename = None
        rdf_format = None
        source = None
        if path_or_uri_source.startswith(HTTP_SCHEME) or path_or_uri_source.startswith(HTTPS_SCHEME):
            source, open_source, filename, rdf_format, raw_fp = _get_web_source(path_or_uri_source, source)
            if raw_fp:
                source = source.fp
        else:
            source, open_source, filename = _get_file_source(path_or_uri_source)

        if filename and not rdf_format:
            index = filename.rfind('.')
            extension = filename[index:] if index > -1 else filename
            rdf_format = get_format_from_extension(extension)

        if not open_source:
            _close_source(source)
            return result_graph
        _source = open_source
        try:
            _source.seek(0)  
        except (AttributeError, ValueError, UnsupportedOperation) as e:
            log.info(f'{method_log_prefix} Exception {type(e)} seek-0: {str(e)}')
            new_bytes = BytesIO(_source.read())
            _close_source(source)
            source = _source = new_bytes

        rdf_format = _get_rdf_format_from_source(_source, rdf_format)
        try:
            result_graph = Graph().parse(source, format = rdf_format)
        except (ParserError, TypeError) as e:
            log.debug(f'{method_log_prefix} Exception {type(e)} parsing source {source} with format {rdf_format or ""}: {str(e)}')
        _close_source(source)
    except Exception:
        _close_source(source)
    return result_graph

def _close_source(source):
    try:
        source.close()
    except Exception:
        pass

def _get_web_source(uri_source, source):
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    open_source = None
    filename = None
    rdf_format = None
    get_response_fp = False
    if uri_source and uri_source.startswith(HTTP_SCHEME) or uri_source.startswith(HTTPS_SCHEME):
        try:
            response, response_filename, web_format, raw_fp = load.get_rdf_from_web(uri_source)
        except (RuntimeError, HTTPError) as e:
            log.error(f'{method_log_prefix} Exception {type(e)} getting vocabulary {uri_source}: {str(e)}')
            raise e
        if web_format == 'graph':
            source = response
            open_source = None
        elif web_format in ('auto', None):
            if response_filename:
                filename = response_filename
            source = open_source = response
        else:
            rdf_format = web_format
            filename = response_filename
            get_response_fp = True
            source = open_source = response
    return source, open_source, filename, rdf_format, get_response_fp

def _get_file_source(path_source):
    open_source = None
    filename = None
    if path_source and not (path_source.startswith(HTTP_SCHEME) or path_source.startswith(HTTPS_SCHEME)):
        if path_source[0] == '/' and (len(path_source) > 2):
            filename = path_source
        elif path_source.startswith('file://'):
            filename = path_source[7:]
        if filename:
            filename = str(Path(filename).resolve())
            source = open_source = open(filename, mode='rb')
    return source, open_source, filename

def _get_rdf_format_from_source(rdf_source, rdf_format):
    if rdf_source and not rdf_format:
        line = _get_first_non_empty_line(rdf_source)
        if line.startswith(b"<!doctype html") or line.startswith(b"<html"):
            raise RuntimeError("Attempted to load a HTML document as RDF.")
        if line.startswith(b"<?xml") or line.startswith(b"<xml") or line.startswith(b"<rdf:"):
            rdf_format = "xml"
        if line.startswith(b"@base ") or line.startswith(b"@prefix ") or line.startswith(b"PREFIX "):
            rdf_format = "turtle"
    return rdf_format

def _get_first_non_empty_line(rdf_source):
    line = rdf_source.readline().lstrip()
    line_len = len(line) if line is not None else 0
    while (
        (line is not None and line_len == 0)
          or (line_len == 1 and line[0] == "\n")
          or (line_len == 2 and line[0:2] == "\r\n")
    ):
        line = rdf_source.readline().lstrip()
        line_len = len(line) if line is not None else 0
    if line_len > 15:
        line = line[:15]
    line = line.lower()
    return line


def get_format_from_extension(extension:str) -> str:
    '''
    Get format from extension
    
    :param extension: Extension
    :type extension: str
    
    :returns: rdf format
    :rtype: str
    '''
    rdf_format = None
    extension_to_format = {
       '.ttl':  'turtle',
       '.turtle':  'turtle',
       '.nt':  'nt',
       '.n3':  'n3',
       '.json':  'json-ld',
       '.nq':  'turtle',
       '.nquads':  'nquads',
       '.trig':  'trig',
       '.rdf':  'xml',
       '.xml':  'xml',
    }
    if extension:
        rdf_format = extension_to_format.get(extension.lower())
    return rdf_format

@log_debug
def check_hvd_entity(graph_to_check:Graph, entity_uri_to_check:str) -> bool:
    '''
    Checks if an entity is marked or should be considered as hvd entity
    
    :param graph_to_check: graph of the entity to be checked
    :type graph_to_check: Graph
    
    :param entity_uri_to_check: entity uri to be checked
    :type entity_uri_to_check: str
    
    :returns True if entity is marked as hvd entity, False in other case
    :rtype bool
    '''
    is_marked_as_hvd_entity = False
    if graph_to_check:
        is_marked_as_hvd_entity = any(graph_to_check.triples((
            from_str_to_uriref(entity_uri_to_check), 
            from_str_to_uriref("http://data.europa.eu/r5r/applicableLegislation"), 
            from_str_to_uriref("http://data.europa.eu/eli/reg_impl/2023/138/oj")
            )))
    return is_marked_as_hvd_entity

def generate_graph_uri_from_source_and_job(source_id, job_id):
    if source_id and job_id:
        return f'urn{HarvesterConstants.GRAPH_NAME_SEPARATOR_CHARACTER}job{HarvesterConstants.GRAPH_NAME_SEPARATOR_CHARACTER}{source_id}{HarvesterConstants.GRAPH_NAME_SEPARATOR_CHARACTER}{job_id}'
    return None

@log_info
def generate_graph_uri_and_catalog_uri_from_source_id(harvest_source_id: str) -> Tuple[str, str]:
    '''
    Build the graph uri associated to a harvest_source
    
    :param harvest_source_id: harvest source identifier
    :type harvest_source_id: str

    :return graph uri and catalog_uri
    :rtype: Tuple[str,str]
    '''
    graph_uri = None
    catalog_uri = None
    package_name = None
    if harvest_source_id:
        graph_uri = f'urn{HarvesterConstants.GRAPH_NAME_SEPARATOR_CHARACTER}source{HarvesterConstants.GRAPH_NAME_SEPARATOR_CHARACTER}{harvest_source_id}'
        result = model.Session.query(model.Package.name) \
            .filter(model.Package.id == harvest_source_id) \
            .filter(model.Package.type == 'harvest') \
            .first()
        if result:
            package_name, = result
        catalog_uri = package_name
    return graph_uri, catalog_uri

@log_info
def generate_graph_uri_from_job(harvest_job: HarvestJob) -> str:
    '''
    Build the graph uri associated to a harvest_job
    
    :param harvest_job: harvest job
    :type harvest_job: HarvestJob

    :return graph uri
    :rtype: str
    '''
    graph_uri = generate_graph_uri_from_source_and_job(harvest_job.source_id, harvest_job.id)
    return graph_uri

@log_debug
def get_value_of_an_extras_key_from_dict(data_dict:dict[str, object], key:str) -> str:
    """Get the key value of an extra

    :param package: Package
    :type package: model.Package

    :param key: extras key
    :type key: str

    :returns: key value
    :rtype: str
    """
    value = None
    if data_dict and key:
        for extra in data_dict.get(CommonPackageConstants.KEY_EXTRAS, []):
            if extra.get('key', None) == key:
                value = extra.get('value', None)
    return value

def from_str_to_uriref(value):
    uriref_value = None
    if value:
        if isinstance(value, BNode) or isinstance(value, Literal):
            uriref_value = value
        else:
            uri = value if isinstance(value, str) else (str(value))
            if uri.startswith("<") and uri.endswith(">"):
                uri = uri.strip("<>")
            uriref_value = CleanedURIRef(uri)
    return uriref_value

def safe_n3_uriref(value):
    uriref_value = from_str_to_uriref(value)
    if uriref_value:
        uriref_value = uriref_value.n3()
    return uriref_value

def get_extra(key, package_dict):
    for extra in package_dict.get('extras', []):
        if extra['key'] == key:
            return extra

def get_extra_value(key, package_dict):
    extra = get_extra(key, package_dict)
    if extra:
        return extra.get('value')

def get_int_value_from_ckan_property(property, default_value):
    property_value = None
    try:
        property_value = int(config.get(property, default_value))
    except Exception as e:
        log.warning(f'Exception {type(e)} initilizing RDFStore getting value of {property} property: {str(e)}. Set {default_value} by default')
        property_value = default_value
    return property_value
