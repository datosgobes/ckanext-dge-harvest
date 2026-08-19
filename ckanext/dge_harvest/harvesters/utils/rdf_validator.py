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
from typing import List
from ...constants.dcat_ap_es_constants import DCATAPESPrefixConstants, DCT, DCATAPESConfigConstants as ConfigConstantsDCATAPES, DCATAPESHarvesterConstants as HarvesterConstants
from ...rdf_store import RDFStoreQuery
from ...decorators import log_debug
from ...harvester_config_reader import HarvesterConfigReader
from ckanext.dge_harvest.harvesters.dge_harvester_exceptions import (
    RdfValidatorException,
)
log = logging.getLogger(__name__)


class RdfValidator():

    def __init__(self, graph_uri: str, rdf_store: RDFStoreQuery) -> None:
        '''
        This is a RDFValidator of graph_uri that is stored in rdf_store
        '''
        self.graph_uri = graph_uri
        self.rdf_store = rdf_store
        if type(self) is RdfValidator:
            raise TypeError("RdfValidator is a partial implementation and cannto be instatiated directly")

class DcatApEsRdfValidator(RdfValidator): 
    def _get_log_prefix(self, method_name):
        return f'[{self.__class__.__name__}][{method_name}]'

    def _normalize_http_https_namespace(self, namespace_uri: str) -> str:
        if not namespace_uri:
            return namespace_uri
        if namespace_uri.startswith('https://'):
            return 'http://' + namespace_uri[len('https://'):]
        return namespace_uri

    @log_debug
    def check_namespaces_are_canonical(self, canonical_namespaces: List[str] = None) -> bool:
        '''
        Check if namespaces used in predicates and rdf:type objects are canonical.

        :param canonical_namespaces: list of canonical namespace URIs accepted in the graph
        :type canonical_namespaces: list[str]

        :raises RdfValidatorException if non canonical namespaces are found
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        canonical_namespaces = canonical_namespaces or []
        if not canonical_namespaces:
            log.warning(f'{method_log_prefix} No canonical namespaces configured for graph {self.graph_uri}. Validation skipped.')
            return True

        canonical_namespaces_by_normalized_uri = {
            self._normalize_http_https_namespace(namespace): namespace
            for namespace in canonical_namespaces
        }
        wrong_namespaces = {}
        for used_namespace in self.rdf_store.get_namespaces_used_in_predicates_and_types() or []:
            normalized_used_namespace = self._normalize_http_https_namespace(used_namespace)
            expected_canonical_namespace = canonical_namespaces_by_normalized_uri.get(normalized_used_namespace)
            if expected_canonical_namespace and used_namespace != expected_canonical_namespace:
                wrong_namespaces[used_namespace] = expected_canonical_namespace
        if wrong_namespaces:
            log.error(f'{method_log_prefix} End method. There are canonical namespaces with non canonical URIs in graph {self.graph_uri}: {wrong_namespaces}')
            raise RdfValidatorException(
                HarvesterConstants.NON_CANONICAL_NAMESPACES_ERROR.format(
                    sorted(wrong_namespaces.keys()),
                    sorted(wrong_namespaces.values())
                )
            )
        return True

    @log_debug
    def check_namespaces_are_canonical_from_config(self, havester_config_file_path: str) -> bool:
        '''
        Check if namespaces used in predicates and rdf:type objects are canonical,
        loading canonical namespaces from the harvester config file.

        :param havester_config_file_path: path to harvester config file
        :type havester_config_file_path: str
        '''
        harvester_config_reader = HarvesterConfigReader(havester_config_file_path)
        canonical_namespaces = harvester_config_reader.get_section_property_as_a_list(
            ConfigConstantsDCATAPES.SECTION_BASIC,
            ConfigConstantsDCATAPES.PROP_CANONICAL_NAMESPACES,
            []
        )
        if not canonical_namespaces:
            log.error(
                f'{self._get_log_prefix(inspect.currentframe().f_code.co_name)} '
                f'No se ha encontrado la propiedad '
                f'{ConfigConstantsDCATAPES.SECTION_BASIC}.{ConfigConstantsDCATAPES.PROP_CANONICAL_NAMESPACES} '
                f'en el fichero de configuración {havester_config_file_path}'
            )
            raise ValueError(HarvesterConstants.NOT_FOUND_SHACL_CONFIG_ERROR.format(self.graph_uri))
        return self.check_namespaces_are_canonical(canonical_namespaces)

    @log_debug
    def check_if_unique_root_catalog_by_graph(self) -> str:
        '''
        Check how many root catalogs are there in the graph. Only one root catalog is rigth.
        
        :raises RdfValidatorException if graph has less or more than one root catalog 
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        root_catalog_uri = self.rdf_store.get_root_catalog_uri()
        if not root_catalog_uri:
            log.error(f'{method_log_prefix} There are no root catalogs in the graph {self.graph_uri}')
            raise RdfValidatorException('No root catalogs in the graph')
        return root_catalog_uri

    @log_debug
    def check_if_publishers_are_right(self, uri_accepted_publishers:List[str] = []) -> bool:
        '''
        Check if publishers of the RDF are one of the available publisher. Raises a RdfValidatorException if not conforms
        
        :param uri_accepted_publishers: list of uris of accepted publisher
        :type uri_accepted_publishers: list[str]
        
        :raises RdfValidatorException if the graph has publishers not accepted
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        uri_publishers = self.rdf_store.get_distinct_objects_by_predicate(DCT.publisher)
        wrong_uri_publishers = []
        if not uri_accepted_publishers:
            wrong_uri_publishers = uri_publishers
        else:
            wrong_uri_publishers = [uri_publisher for uri_publisher in uri_publishers or [] if uri_publisher not in uri_accepted_publishers]
        if wrong_uri_publishers:
            log.error(f'{method_log_prefix} End method. There are publishers values does not accepted in graph {self.graph_uri}: Values not accepted: {wrong_uri_publishers}')
            #raise  RdfValidatorException(f'There are publishers values does not accepted. Publisher must be an IRI from http://datos.gob.es/recurso/sector-publico/org/Organismo. Values not accepted: {wrong_uri_publishers}')
            raise  RdfValidatorException(f'Hay valores de publicadores no aceptados. Los valores de publicadores deben ser una IRI de http://datos.gob.es/recurso/sector-publico/org/Organismo. Valores no aceptados: {wrong_uri_publishers}')
        return True

    @log_debug
    def check_if_creators_are_right(self, uri_accepted_creators:List[str] = []) -> bool:
        '''
        Check if creators of the RDF that starts with http://datos.gob.es/recurso/sector-publico/org/Org are one of the available publisher. Raises a RdfValidatorException if not conforms
        
        :param uri_accepted_creators: list of uris of accepted creators
        :type uri_accepted_creators: list[str]
        
        :raises RdfValidatorException if the graph has creators not accepted
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        query = f"SELECT DISTINCT ?o FROM <{self.graph_uri}> WHERE {{ ?s <{DCT.creator}> ?o . FILTER(isIRI(?o) && STRSTARTS(STR(?o), '{DCATAPESPrefixConstants.PUBLISHER_PREFIX}'))}}"
        uri_creators = self.rdf_store.get_objects_by_query(query, 'o')
        wrong_uri_creators = []
        if not uri_accepted_creators:
            wrong_uri_creators = uri_creators
        else:
            wrong_uri_creators = [uri_creator for uri_creator in uri_creators or [] if uri_creator not in uri_accepted_creators]
        if wrong_uri_creators:
            log.error(f'{method_log_prefix} End method. There are creators values does not accepted in graph {self.graph_uri}: Values not accepted: {wrong_uri_creators}')
            #raise  RdfValidatorException(f'There are creators values does not accepted. Creators with prefix {DCATAPESPrefixConstants.PUBLISHER_PREFIX}  must be IRI from http://datos.gob.es/recurso/sector-publico/org/Organismo. Values not accepted: {wrong_uri_creators}')
            raise  RdfValidatorException(f'Hay valores de autores no aceptados. Los valores e autores con prefijo {DCATAPESPrefixConstants.PUBLISHER_PREFIX} deben ser una IRI de http://datos.gob.es/recurso/sector-publico/org/Organismo. Valores no aceptados: {wrong_uri_creators}')
        return True