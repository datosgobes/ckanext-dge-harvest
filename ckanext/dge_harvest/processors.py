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

from rdflib import URIRef, Literal
from ckan.plugins.toolkit import config

from ckanext.dcat.utils import catalog_uri, url_to_rdflib_format
from ckanext.dcat.processors import RDFParser, RDFSerializer

from .constants.nti_constants import NTIHarvesterConstants
from .constants import CommonPackageConstants, DCATAPESSerializerConstants, DCATAPESConfigConstants
from .utils import dge_harvest_dataset_uri, dge_harvest_dataservice_uri, dge_harvest_build_catalog_record_uriref
from .harvester_config_reader import HarvesterConfigReader
from .constants.dcat_ap_es_constants import DCAT, DCT, XSD, HYDRA, RDF
from .decorators import log_debug, log_info

log = logging.getLogger(__name__)

class DGENTIRDFParser(RDFParser):
    '''
    An RDF to CKAN parser based on rdflib

    Supports different profiles which are the ones that will generate
    CKAN dicts from the RDF graph.
    '''



    def _copy_clean_dict(self, dict):
        '''
        Get a new dict with not empty values of dict
        
        :param dict: dictionary to get not empty values
        :type dict: dictioary
        
        :returns dictionary with not empty values
        :rtype: dictionary
        '''
        clean_dict = {}
        if dict is not None:
            for key in dict:
                value = dict.get(key, None)
                if value:
                    clean_dict[key] = value
        return clean_dict
    
    def datasets(self, dict=None):
        '''
        Generator that returns CKAN datasets parsed from the RDF graph

        Each dataset is passed to all the loaded profiles before being
        yielded, so it can be further modified by each one of them.

        Returns a dataset dict that can be passed to eg `package_create`
        or `package_update`
        '''
        for dataset_ref in self._datasets():
            dataset_dict = self._copy_clean_dict(dict)
            for profile_class in self._profiles:
                profile = profile_class(graph=self.g, dataset_type=CommonPackageConstants.KEY_TYPE_DATASET_VALUE, compatibility_mode=self.compatibility_mode)
                profile.parse_dataset(dataset_dict, dataset_ref)

            yield dataset_dict

    def _catalogs(self):
        '''
        Generator that returns all DCAT catalog on the graph

        Yields rdflib.term.URIRef objects that can be used on graph lookups
        and queries
        '''
        for catalog in self.g.subjects(RDF.type, DCAT.Catalog):
            yield catalog

    def catalogs(self):
        '''
        Generator that returns CKAN catalogs parsed from the RDF graph

        Each catalog is passed to all the loaded profiles before being
        yielded, so it can be further modified by each one of them.

        Returns a catalog dict 
        '''
        for catalog_ref in self._catalogs():
            catalog_dict = {}
            for profile_class in self._profiles:
                profile = profile_class(graph=self.g, dataset_type=self.dataset_type, compatibility_mode=self.compatibility_mode)
                profile.parse_catalog(catalog_dict, catalog_ref)
            yield catalog_dict

class DGENTIRDFSerializer(RDFSerializer):
    '''
    A CKAN to RDF serializer based on rdflib

    Supports different profiles which are the ones that will generate
    the RDF graph.
    '''
  

class DGEDCATAPESRDFParser(DGENTIRDFParser):
    '''
    An RDF to CKAN parser based on rdflib

    Supports different profiles which are the ones that will generate
    CKAN dicts from the RDF graph.
    '''

    def _get_log_prefix(self, method_name):
        return f'[{self.__class__.__name__}][{method_name}]'

    @log_debug
    def next_page(self, visited_pages=()):
        '''
        Returns the URL of the next page or None if there is no next page
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        for pagination_node in self.g.subjects(RDF.type, HYDRA.PagedCollection):
            log.debug(f'{method_log_prefix} pagination_node = {pagination_node}')
            for o in self.g.objects(pagination_node, HYDRA.next):
                log.debug(f'{method_log_prefix} object next = {o}')
                if o not in visited_pages:
                    log.debug(f'{method_log_prefix} Returns next = {o}')
                    return str(o)

            for o in self.g.objects(pagination_node, HYDRA.nextPage):
                log.debug(f'{method_log_prefix} object next = {o}')
                if o not in visited_pages:
                    log.debug(f'{method_log_prefix} Returns next = {o}')
                    return str(o)
        return None

    def datasets(self, dict=None):
        '''
        Generator that returns CKAN datasets parsed from the RDF graph

        Each dataset is passed to all the loaded profiles before being
        yielded, so it can be further modified by each one of them.

        Returns a dataset dict that can be passed to eg `package_create`
        or `package_update`
        '''
        for dataset_ref in self._datasets():
            dataset_dict = self._copy_clean_dict(dict)
            for profile_class in self._profiles:
                profile = profile_class(graph=self.g, dataset_type=CommonPackageConstants.KEY_TYPE_DATASET_VALUE, compatibility_mode=self.compatibility_mode)
                profile.parse_dataset(dataset_dict, dataset_ref)

            yield dataset_dict

    def _dataservices(self):
        '''
        Generator that returns all DCAT dataservices on the graph

        Yields rdflib.term.URIRef objects that can be used on graph lookups
        and queries
        '''
        for dataservice in self.g.subjects(RDF.type, DCAT.DataService):
            yield dataservice

    def dataservices(self, dict=None):
        '''
        Generator that returns CKAN dataservices parsed from the RDF graph

        Each dataservice is passed to all the loaded profiles before being
        yielded, so it can be further modified by each one of them.

        Returns a dataservice dict that can be passed to eg `package_create`
        or `package_update`
        '''
        for dataservice_ref in self._dataservices():
            dataservice_dict = self._copy_clean_dict(dict)
            for profile_class in self._profiles:
                profile = profile_class(graph=self.g, dataset_type=CommonPackageConstants.KEY_TYPE_DATASERVICE_VALUE, compatibility_mode=self.compatibility_mode)
                profile.parse_dataservice(dataservice_dict, dataservice_ref)

            yield dataservice_dict

    def _catalogs(self):
        '''
        Generator that returns all DCAT catalog on the graph

        Yields rdflib.term.URIRef objects that can be used on graph lookups
        and queries
        '''
        for catalog in self.g.subjects(RDF.type, DCAT.Catalog):
            yield catalog

    def catalogs(self, dict=None):
        '''
        Generator that returns CKAN catalogs parsed from the RDF graph

        Each catalog is passed to all the loaded profiles before being
        yielded, so it can be further modified by each one of them.

        Returns a catalog dict 
        '''
        for catalog_ref in self._catalogs():
            catalog_dict = self._copy_clean_dict(dict)
            for profile_class in self._profiles:
                profile = profile_class(graph=self.g, dataset_type=self.dataset_type, compatibility_mode=self.compatibility_mode)
                profile.parse_catalog(catalog_dict, catalog_ref)
            yield catalog_dict

class DGEDCAPAPESRDFSerializer(DGENTIRDFSerializer):
    '''
    A CKAN to RDF serializer based on rdflib

    Supports different profiles which are the ones that will generate
    the RDF graph.
    '''
    DEFAULT_CONFIG_FILEPATH = config.get('ckanext.dge_harvest.dcat_ap_es_1_0_0.config.filepath', '')

    def _get_log_prefix(self, method_name):
        return f'[{self.__class__.__name__}][{method_name}]'

    def _url_to_rdflib_format(self, _format):
        '''
        Translates the RDF formats used on the endpoints to rdflib ones
        '''
        _dcat_format = url_to_rdflib_format(_format)
        if _format != 'pretty-xml' and _dcat_format == 'pretty-xml':
            _format = 'xml'
        return _format

    @log_debug
    def _serialize_datasets(self, catalog_ref=None, dataset_dicts=None):
        '''
        Returns an RDF serialization of the dataservices
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        dataset_number = 0
        if dataset_dicts is None or len(dataset_dicts) == 0:
            log.debug(f'{method_log_prefix} End method. There are no dataset to process')
            return dataset_number
        
        for dataset_dict in dataset_dicts:
            ini = time.time()
            dataset_ref = self.graph_from_dataset(dataset_dict)
            dataset_number = dataset_number+1
            self.g.add((catalog_ref, DCAT.dataset, dataset_ref))
            self.g.add((catalog_ref, DCAT.record, dge_harvest_build_catalog_record_uriref(dataset_ref)))
            log.info(f'{method_log_prefix} Serialized dataset with name: {dataset_dict.get("name")} in {time.time()-ini}')
            
        return dataset_number

    @log_debug
    def _serialize_dataservices(self, catalog_ref=None, dataservice_dicts=None):
        '''
        Returns an RDF serialization of the dataservices
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        dataservice_number = 0
        if dataservice_dicts is None or len(dataservice_dicts) == 0:
            log.debug(f'{method_log_prefix} End method. There are no dataset to process')
            return dataservice_number
        
        for dataservice_dict in dataservice_dicts:
            ini = time.time()
            dataservice_ref = self.graph_from_dataservice(dataservice_dict)
            dataservice_number = dataservice_number+1
            self.g.add((catalog_ref, DCAT.service, dataservice_ref))
            self.g.add((catalog_ref, DCAT.record, dge_harvest_build_catalog_record_uriref(dataservice_ref)))
            log.info(f'{method_log_prefix} Serialized dataservice with name: {dataservice_dict.get("name")} in {time.time()-ini}')
        return dataservice_number

    def serialize_dataservice(self, dataservice_dict, _format='xml'):
        '''
        Given a CKAN dataservice dict, returns an RDF serialization

        The serialization format can be defined using the `_format` parameter.
        It must be one of the ones supported by RDFLib, defaults to `xml`.

        Returns a string with the serialized dataset
        '''

        self.graph_from_dataservice(dataservice_dict)

        if not _format:
            _format = 'xml'
        _format = url_to_rdflib_format(_format)

        if _format == 'json-ld':
            output = self.g.serialize(format=_format, auto_compact=True)
        else:
            output = self.g.serialize(format=_format)

        return output

    @log_debug
    def serialize_catalog_with_dataservices(self, catalog_dict=None, dataset_dicts=None, dataservice_dicts=None,
                          _format='xml', pagination_info=None):
        '''
        Returns an RDF serialization of the whole catalog (dataservices + datasets)

        `catalog_dict` can contain literal values for the dcat:Catalog class
        like `title`, `homepage`, etc. If not provided these would get default
        values from the CKAN config (eg from `ckan.site_title`).

        If passed a list of CKAN dataset dicts, these will be also serializsed
        as part of the catalog.
        **Note:** There is no hard limit on the number of datasets at this
        level, this should be handled upstream.
        
        If passed a list of CKAN dataservice dicts, these will be also serializsed
        as part of the catalog.
        **Note:** There is no hard limit on the number of datasets at this
        level, this should be handled upstream.

        The serialization format can be defined using the `_format` parameter.
        It must be one of the ones supported by RDFLib, defaults to `xml`.

        `pagination_info` may be a dict containing keys describing the results
        pagination. See the `_add_pagination_triples()` method for details.

        Returns a string with the serialized catalog
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        catalog_ref = self.graph_from_catalog(catalog_dict)
        dataservice_number = self._serialize_dataservices(catalog_ref, dataservice_dicts)
        dataset_number = self._serialize_datasets(catalog_ref, dataset_dicts)

        log.debug(f'{method_log_prefix} Total datasets={dataset_number}; total dataservices={dataservice_number}')
        self.g.add((catalog_ref, DCT.extent, Literal((dataset_number + dataservice_number), datatype=XSD.nonNegativeInteger)))
        
        if pagination_info:
            self._add_pagination_triples(pagination_info)
        
        _format = self._url_to_rdflib_format(_format)
        output = self.g.serialize(format=_format)
        return output

    @log_info
    def serialize_catalog(self, catalog_dict=None, dataset_dicts=None,
                          _format='xml', pagination_info=None):
        '''
        Returns an RDF serialization of the whole catalog

        `catalog_dict` can contain literal values for the dcat:Catalog class
        like `title`, `homepage`, etc. If not provided these would get default
        values from the CKAN config (eg from `ckan.site_title`).

        If passed a list of CKAN dataset dicts, these will be also serializsed
        as part of the catalog.
        **Note:** There is no hard limit on the number of datasets at this
        level, this should be handled upstream.

        The serialization format can be defined using the `_format` parameter.
        It must be one of the ones supported by RDFLib, defaults to `xml`.

        `pagination_info` may be a dict containing keys describing the results
        pagination. See the `_add_pagination_triples()` method for details.

        Returns a string with the serialized catalog
        '''
        output = ''
        if dataset_dicts:
            output = self.serialize_catalog_with_dataservices(catalog_dict, dataset_dicts, None, _format, pagination_info)
        else:
            self.graph_from_catalog(catalog_dict)
            if pagination_info:
                self._add_pagination_triples(pagination_info)
            _format = self._url_to_rdflib_format(_format)
            output = self.g.serialize(format=_format)
        return output

    def graph_from_dataset(self, dataset_dict):
        '''
        Given a CKAN dataset dict, creates a graph using the loaded profiles

        The class RDFLib graph (accessible via `serializer.g`) will be updated
        by the loaded profiles.

        Returns the reference to the dataset, which will be an rdflib URIRef.
        '''
        
        dataset_ref = URIRef(dge_harvest_dataset_uri(dataset_dict))

        for profile_class in self._profiles:
            profile = profile_class(graph=self.g, dataset_type=CommonPackageConstants.KEY_TYPE_DATASET_VALUE, compatibility_mode=self.compatibility_mode)
            profile.graph_from_dataset(dataset_dict, dataset_ref)

        return dataset_ref

    def graph_from_dataservice(self, dataservice_dict):
        '''
        Given a CKAN dataset dict, creates a graph using the loaded profiles

        The class RDFLib graph (accessible via `serializer.g`) will be updated
        by the loaded profiles.

        Returns the reference to the dataset, which will be an rdflib URIRef.
        '''
        
        dataservice_ref = URIRef(dge_harvest_dataservice_uri(dataservice_dict))

        for profile_class in self._profiles:
            profile = profile_class(graph=self.g, dataset_type=CommonPackageConstants.KEY_TYPE_DATASERVICE_VALUE, compatibility_mode=self.compatibility_mode)
            profile.graph_from_dataservice(dataservice_dict, dataservice_ref)
        
        return dataservice_ref
    
    def graph_from_catalog(self, catalog_dict=None):
        '''
        Creates a graph for the catalog (CKAN site) using the loaded profiles

        The class RDFLib graph (accessible via `serializer.g`) will be updated
        by the loaded profiles.

        Returns the reference to the catalog, which will be an rdflib URIRef.
        '''
        
        default_catalog_uri = catalog_uri()
        default_prefix_properties = DCATAPESConfigConstants.ROOT_CATALOG_EXPORT_PROPERTIES_PREFIX
        catalog_dict = catalog_dict or {}
        catalog_dict[DCATAPESSerializerConstants.CATALOG_URI_REF] = catalog_dict.get(DCATAPESSerializerConstants.CATALOG_URI_REF, default_catalog_uri) or default_catalog_uri
        catalog_dict[DCATAPESSerializerConstants.CATALOG_EXPORT_PROPERTIES_PREFIX] = catalog_dict.get(DCATAPESSerializerConstants.CATALOG_EXPORT_PROPERTIES_PREFIX, default_prefix_properties)
        catalog_dict[DCATAPESSerializerConstants.CONFIG_READER] = catalog_dict.get(DCATAPESSerializerConstants.CONFIG_READER, 
                                          HarvesterConfigReader(self.DEFAULT_CONFIG_FILEPATH))
        catalog_ref = URIRef(catalog_dict[DCATAPESSerializerConstants.CATALOG_URI_REF])
        for profile_class in self._profiles:
            profile = profile_class(graph=self.g, dataset_type=self.dataset_type, compatibility_mode=self.compatibility_mode)
            profile.graph_from_catalog(catalog_dict, catalog_ref)

        return catalog_ref