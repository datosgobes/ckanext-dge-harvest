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
# -*- coding: 850 -*-
# -*- coding: utf-8 -*-

import datetime
import logging
import inspect
import time
from rdflib import URIRef, Graph, Literal
from typing import List

from ckan.common import _
from ckan.plugins import toolkit
from ckan.plugins.toolkit import config
import ckan.model as model
from ckanext.harvest.model import (HarvestObject, HarvestJob, HarvestObjectExtra)
from ..constants import (DCATAPESConfigConstants as ConfigConstants,
                         DCATAPESHarvesterConstants as HarvesterConstants,
                         DCATAPESSerializerConstants as SerializerConstants,
                         DcatClassNameEnum, HarvestObjectExtraKeyConstants,
                         CommonPackageConstants, DCATAPESPrefixConstants)
from ..constants.dcat_ap_es_constants import RDF, FOAF, DCT, DCAT
from .rdf_xml_parser import RDFXmlParser
from ..rdf_store  import RDFStoreQuery
from ..processors import DGEDCAPAPESRDFSerializer
from ..export import export_utils
from ..harvester_config_reader import HarvesterConfigReader
from ..harvesters.utils.harvester_utils import remove_graphs_of_previous_harvesting_from_source_id
from ..utils import generate_graph_uri_and_catalog_uri_from_source_id, get_extra_value, dge_harvest_build_catalog_record_uriref
from ckanext.dcat.utils import catalog_uri
from ..decorators import log_debug, log_info
from rdflib.namespace import Namespace
from ..helpers import dge_harvest_organizations_available


log = logging.getLogger(__name__)

SERIALIZED_FORMAT = 'xml'
RDF_FORMAT = 'rdf'

class RDFExportGenerator():
    '''
    Carry out RDF serialize task
    '''    
    def __init__(self, config_filepath:str, is_edp:bool):
        self._config_reader = self._get_config_reader(config_filepath)
        self._is_edp = True if is_edp else False
        self.all_available_publishers = dge_harvest_organizations_available()

    def _get_log_prefix(self, method_name):
        return f'[{self.__class__.__name__}][{method_name}]'

    @log_info
    def dge_harvest_catalog_show_rdf(self, context, data_dict):
        '''
        Build the RDF of complete catalog
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        output = None
        try:
            _init_time = datetime.datetime.now()
            toolkit.check_access('dge_harvest_catalog_show', context, data_dict)
            
            _format=data_dict.get('format')
            _filepath = export_utils.get_filepath(_format, data_dict.get('filename', None), self._is_edp, self._config_reader)
            
            # get root_catalog
            _root_catalog, _ = self._serialize_catalog(_format, True)
            rdf_xml_parser = RDFXmlParser(_filepath, self._config_reader, _root_catalog, self.all_available_publishers)
            
            # add dcat-ap-es harvested catalogs
            self._add_dcat_ap_es_harvested_catalogs(rdf_xml_parser)

            # add dataservices and datasets in an internal subcatalogs
            self._add_datasets_and_dataservices_in_internal_subcatalog(context, data_dict, _format, rdf_xml_parser)

            # write final RDF
            rdf_xml_parser.write_catalog_rdf()
            
            # Compress in .gz
            if data_dict.get('compress'):
               _filepath = export_utils.compress_file_in_gzip(_filepath)
            _end_time = datetime.datetime.now()
            log.info(f"{method_log_prefix} Time in serialize {_format} catalog  in [{_filepath}]  ... {int((_end_time - _init_time).total_seconds() * 1000)} milliseconds")
        except Exception as e:
            log.error(f"{method_log_prefix} Exception {type(e).__name__}: {e}.", exc_info=True)
            output = None
        return output

    @log_debug
    def _get_harvest_sources_ids_of_a_harvester_type(self, harvester_type:str) -> List[str]:
        '''
        Get get the list of federation sources ids that have federator type harvester_type configured now 
        or have had it configured at some point because they have harvest objects with parameters unique to that federator type

        :param harvester_type: harvester type
        :type harvester_type: str
        
        :return List of harvest sources ids
        :rtype List[str]
        '''
        source_ids = set()
        if not harvester_type:
            return []

        dcat_ap_es_harvest_objects = model.Session.query(HarvestObject.harvest_source_id).distinct()\
                    .join(HarvestObjectExtra)\
                    .filter(HarvestObject.id == HarvestObjectExtra.harvest_object_id)\
                    .filter(HarvestObjectExtra.key == HarvestObjectExtraKeyConstants.HOE_HARVESTER_TYPE) \
                    .filter(HarvestObjectExtra.value == harvester_type) \
                    .filter(HarvestObject.current == True)\
                    .all()
        for harvest_source_id in dcat_ap_es_harvest_objects or []:
            if harvest_source_id and harvest_source_id[0]:
                source_ids.add(harvest_source_id[0])
        return list(source_ids)

    @log_debug
    def _clean_graph_of_harvest_sources(self, sources_ids: List[str]) -> None:
        '''
        Remove old graphs of harvest_sources
        '''
        for source_id in sources_ids or []:
            remove_graphs_of_previous_harvesting_from_source_id(source_id)

    def _add_dcat_ap_es_harvested_catalogs(self, rdf_xml_parser: RDFXmlParser):
        '''
        Add dcat-ap-es harvested catalogs, stored in a virtuoso o similar database 
        '''
        rdf_store = None
        _all_subcatalogs = set()
        
        harvest_sources_ids = self._get_harvest_sources_ids_of_a_harvester_type(HarvesterConstants.HARVESTER_TYPE)
        # clean old graphs of harvester_sources
        self._clean_graph_of_harvest_sources(harvest_sources_ids)
        for harvest_source_id in harvest_sources_ids:
            self._export_harvested_catalog(harvest_source_id, _all_subcatalogs, rdf_store, rdf_xml_parser)

    def _export_harvested_catalog(self, harvest_source_id, _all_subcatalogs, rdf_store, rdf_xml_parser):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        harvest_source_graph = self._get_graph_uri(harvest_source_id)
        log.info(f'{method_log_prefix} Exporting harvested source with id {harvest_source_id} from graph {harvest_source_graph}')
        offset = 0
        complete_graph = False
        if not rdf_store:
            rdf_store = RDFStoreQuery(harvest_source_graph)
        else:
            rdf_store.update_graph_uri(harvest_source_graph)
        
        has_graph_datasets_or_dataservices = rdf_store.check_if_there_are_entities_in_graph([DCAT.Dataset, DCAT.DataService])
        if not has_graph_datasets_or_dataservices:
            log.info(f'{method_log_prefix} Graph {harvest_source_graph} is not exported because it has no entities (datasets or dataservices)')
            return
        root_catalog_uri = rdf_store.get_root_catalog_uri()
        if not root_catalog_uri:
            log.info(f'{method_log_prefix} Graph {harvest_source_graph} is not exported because it does not have a root catalog')
            return
        _all_subcatalogs.add(root_catalog_uri)
        datasets_european_themes_dict = {}
        catalogs_with_european_theme_taxonomy = []
        datasets_and_dataservices_with_european_themes = []
        if self._is_edp:
            # get catalogs with european theme taxonomy
            catalogs_with_european_theme_taxonomy = rdf_store.get_catalogs_with_europan_theme_taxonomy()
            # get datasets/dataservices with european themes
            datasets_and_dataservices_with_european_themes = rdf_store.get_entities_with_europan_themes()
        while not complete_graph:
            # Set paginated query to get triples blocks
            page_graph = rdf_store.get_and_parse_graph(offset)
            
            offset += rdf_store.max_triples_per_query
            complete_graph = (len(page_graph) == 0)
            # Update used namespaces in graph
            self._update_namespaces_used_in_graph(page_graph, rdf_xml_parser)
            
            # Get creators or publishers to export datos.gob.es organization data if it is an datos.gob.es organization
            creators_and_publishers = {o for _, _, o in page_graph.triples((None, DCT.creator, None))}
            creators_and_publishers = creators_and_publishers.union({o for _, _, o in page_graph.triples((None, DCT.publisher, None))})
            for creator_or_publisher in creators_and_publishers:
                if isinstance(creator_or_publisher, URIRef):
                    rdf_xml_parser.check_if_is_an_available_organization(str(creator_or_publisher))

            if self._is_edp:
                self.add_european_theme_taxomony_to_catalog_in_graph(page_graph, catalogs_with_european_theme_taxonomy)
                self.add_european_theme_to_dataset_in_graph(page_graph, datasets_and_dataservices_with_european_themes, datasets_european_themes_dict)
            subcatalog_page = page_graph.serialize(format=SERIALIZED_FORMAT).encode('utf-8')
            rdf_xml_parser.append_subcatalog(subcatalog_page, root_catalog_uri)
            page_graph.remove((None, None, None))

    def _update_namespaces_used_in_graph(self,page_graph, rdf_xml_parser):
        namespaces_to_bind = {}
        namespaces = []
        for prefix, namespace_uri in page_graph.namespaces():
            _prefix, _namespace_uri = rdf_xml_parser.add_namespace(prefix, namespace_uri)
            namespaces.append(namespace_uri)
            if prefix != _prefix:
                namespaces_to_bind[_prefix] = Namespace(namespace_uri)
            
        for _, p, o in page_graph.triples((None, RDF.type, None)):
            if isinstance(o, URIRef) and str(o) not in namespaces:
                namespace_uri, _ = rdf_xml_parser.parse_namespace_and_element(str(o))
                if namespace_uri not in namespaces:
                    namespaces.append(namespace_uri)
                    _prefix, _namespace_uri = rdf_xml_parser.add_namespace(None, namespace_uri)
                    namespaces_to_bind[_prefix] = Namespace(namespace_uri)

        for prefix, namespace_uri  in namespaces_to_bind.items():
            page_graph.bind(prefix, namespace_uri)

    def _get_graph_uri(self, harvest_source_id):
        harvest_source_graph, _ = generate_graph_uri_and_catalog_uri_from_source_id(harvest_source_id)
        job = None
        if harvest_source_graph:
            job = model.Session.query(HarvestJob)\
                        .filter(HarvestJob.source_id == harvest_source_id)\
                        .filter(HarvestJob.status == 'Running')\
                        .first()
        if job and job.gather_started and not job.gather_finished:
            harvest_source_graph = f'{harvest_source_graph}{HarvesterConstants.SUFFIX_GRAPH_NAME_OF_PREVIOUS_HARVEST}'
        return harvest_source_graph

    @log_debug
    def _add_datasets_and_dataservices_in_internal_subcatalog(self, context, data_dict, format:str, rdf_xml_parser: RDFXmlParser):
        '''
        Get dataset and dataservices of internal catalogs, not stored in a virtuoso o similar database 
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
                       
        def _initialize_internal_catalog(is_internal_catalog_serialized, serialized_rdf_to_add):
            if not is_internal_catalog_serialized and serialized_rdf_to_add and len(serialized_rdf_to_add) > 0:
                self._add_internal_subcatalog(_format, rdf_xml_parser)
                is_internal_catalog_serialized = True
            return is_internal_catalog_serialized
        
        _format = format
        _dataset_dicts = {}
        _dataservice_dicts = {}
        _is_internal_catalog_serialized = False

        # Get dataservices data
        log.info(f'{method_log_prefix} Get and serialize dataservices')
        _dataservice_dicts = export_utils.get_first_page_data_dicts(context, data_dict, DcatClassNameEnum.DATASERVICE, True)
        _total_dataservices_in_this_page = len(_dataservice_dicts.get('data_dicts'))
        _total_dataservices = _dataservice_dicts.get('total_entities')
        _dataservices_to_add = self._serialize_datasets_or_dataservices(_format, None, _dataservice_dicts.get('data_dicts'))
        _is_internal_catalog_serialized = _initialize_internal_catalog(_is_internal_catalog_serialized, _dataservices_to_add)
        rdf_xml_parser.append_datasets_and_dataservices(_dataservices_to_add)
        log.info(f'{method_log_prefix} There are {_total_dataservices} dataservices.')
        _total_dataservices_left_to_process = _total_dataservices - _total_dataservices_in_this_page
        _page = 1
        while (_total_dataservices_left_to_process > 0):
            _page += 1
            _dataservice_dicts = export_utils.get_data_dicts_by_page(context, data_dict, DcatClassNameEnum.DATASERVICE, _page, _total_dataservices_left_to_process, True)
            _total_dataservices_in_this_page = len(_dataservice_dicts.get('data_dicts'))
            _dataservices_to_add = self._serialize_datasets_or_dataservices(_format, None, _dataservice_dicts.get('data_dicts'))
            _is_internal_catalog_serialized = _initialize_internal_catalog(_is_internal_catalog_serialized, _dataservices_to_add)
            rdf_xml_parser.append_datasets_and_dataservices(_dataservices_to_add)
            _total_dataservices_left_to_process = _total_dataservices_left_to_process - _total_dataservices_in_this_page
            log.info(f'{method_log_prefix} Dataservices query get: {_total_dataservices_in_this_page}. Total_dataservices to left: {_total_dataservices_left_to_process}')
        log.info(f'{method_log_prefix} Gotten and serialized dataservices')

        log.info(f'{method_log_prefix} Get and serialize datasets')
        _dataset_dicts = export_utils.get_first_page_data_dicts(context, data_dict, DcatClassNameEnum.DATASET, True)
        _total_datasets_in_this_page = len(_dataset_dicts.get('data_dicts'))
        _datasets_to_add = self._serialize_datasets_or_dataservices(_format, _dataset_dicts.get('data_dicts'), None)
        _is_internal_catalog_serialized = _initialize_internal_catalog(_is_internal_catalog_serialized, _datasets_to_add)
        rdf_xml_parser.append_datasets_and_dataservices(_datasets_to_add)
        _total_datasets = _dataset_dicts.get('total_entities')
        log.info(f'{method_log_prefix} There are {_total_datasets} datasets')
        limit = data_dict.get('limit', -1)
        if limit > -1 and limit < _total_datasets:
            _total_datasets = limit
        _total_datasets_left_to_process = _total_datasets - _total_datasets_in_this_page
        _page = 1
        while (_total_datasets_left_to_process > 0):
            _page += 1
            _dataset_dicts = export_utils.get_data_dicts_by_page(context, data_dict, DcatClassNameEnum.DATASET, _page, _total_datasets_left_to_process, True)
            _total_datasets_in_this_page = len(_dataset_dicts.get('data_dicts'))
            _datasets_to_add = self._serialize_datasets_or_dataservices(_format, _dataset_dicts.get('data_dicts'), None)
            _is_internal_catalog_serialized = _initialize_internal_catalog(_is_internal_catalog_serialized, _datasets_to_add)
            rdf_xml_parser.append_datasets_and_dataservices(_datasets_to_add)
            _total_datasets_left_to_process = _total_datasets_left_to_process - _total_datasets_in_this_page
            log.info(f"{method_log_prefix} Datasets query get: {_total_datasets_in_this_page}. Total_datasets to left: {_total_datasets_left_to_process}")

    def _add_internal_subcatalog(self, format:str, rdf_xml_parser: RDFXmlParser):
        # get internal subcatalog
        nti_subcatalog, nti_subcatalog_uri = self._serialize_catalog(format, False)
        rdf_xml_parser.initialize_internal_subcatalog_rdf_template(nti_subcatalog, nti_subcatalog_uri)

    @log_info
    def _serialize_datasets_or_dataservices(self, format, dataset_dicts, dataservice_dicts):
        output = ''
        if format == RDF_FORMAT:
            catalog_dict, _ = self._get_catalog_config(False)
            mapping_between_nti_and_european_themes = None
            if self._is_edp:
                mapping_between_nti_and_european_themes = self._get_mapping_between_nti_and_european_themes()
            # Add dataset and dataservice config
            for dataset_dict in dataset_dicts or []:
                self._get_dataset_or_dataservice_config(mapping_between_nti_and_european_themes, dataset_dict, True)
            for dataservice_dict in dataservice_dicts or []:
                self._get_dataset_or_dataservice_config(mapping_between_nti_and_european_themes, dataservice_dict, True)
            serializer = DGEDCAPAPESRDFSerializer(profiles=[HarvesterConstants.HARVESTER_PROFILE])
            output = serializer.serialize_catalog_with_dataservices(catalog_dict, dataset_dicts, dataservice_dicts, _format=RDF_FORMAT, pagination_info=None)
        return output

    def _get_dataset_or_dataservice_config(self, mapping_between_nti_and_european_themes, data_dict, is_dataset):
        data_dict = data_dict or {}
        data_dict[SerializerConstants.CONFIG_READER] = self._config_reader
        data_dict[SerializerConstants.EUROPEAN_CATALOG_EXPORT] = self._is_edp
        data_dict[SerializerConstants.AVAILABLE_ORGANIZATIONS] = self.all_available_publishers
        if is_dataset and mapping_between_nti_and_european_themes:
            data_dict[SerializerConstants.MAPPING_NTI_RISP_THEMES_EUROPEAN_THEMES] = mapping_between_nti_and_european_themes

    def _serialize_catalog(self, format, is_root_catalog):
        # Add catalog config
        catalog_dict, catalog_uri = self._get_catalog_config(is_root_catalog)
        serializer = DGEDCAPAPESRDFSerializer(profiles = [HarvesterConstants.HARVESTER_PROFILE])
        output = serializer.serialize_catalog(catalog_dict, None, _format=format, pagination_info=None)
        return output, catalog_uri

    def _get_catalog_config(self, is_root_catalog):
        _catalog_dict = {}
        _property_prefix = None
        _catalog_uri = None
        if is_root_catalog:
            _property_prefix = ConfigConstants.ROOT_CATALOG_EXPORT_PROPERTIES_PREFIX
            _catalog_uri = self._config_reader.get_property(ConfigConstants.SECTION_RDF_EXPORT, 
                                                                    f'{_property_prefix}uriref', 
                                                                    catalog_uri())
        else:
            _property_prefix = ConfigConstants.SUBCATALOG_EXPORT_PROPERTIES_PREFIX
            _catalog_uri = self._config_reader.get_property(ConfigConstants.SECTION_RDF_EXPORT, 
                                                                    f'{_property_prefix}uriref', 
                                                                    'http://datos.gob.es/subcatalog')
        _catalog_dict[SerializerConstants.CONFIG_READER] = self._config_reader
        _catalog_dict[SerializerConstants.CATALOG_EXPORT_PROPERTIES_PREFIX] = _property_prefix
        _catalog_dict[SerializerConstants.CATALOG_URI_REF] = _catalog_uri
        _catalog_dict[SerializerConstants.EUROPEAN_CATALOG_EXPORT] = self._is_edp
        _catalog_dict[SerializerConstants.AVAILABLE_ORGANIZATIONS] = self.all_available_publishers
        if self._is_edp:
            _catalog_dict[SerializerConstants.EUROPEAN_THEME_TAXONOMY] = self._get_european_theme_taxonomy()
        return _catalog_dict, _catalog_uri

    def _get_config_reader(self, harvester_config_filepath:str=None) -> HarvesterConfigReader:
        filepath = harvester_config_filepath if harvester_config_filepath else config.get('ckanext.dge_harvest.dcat_ap_es_1_0_0.config.filepath', '')
        harvester_config_reader = HarvesterConfigReader(filepath)
        return harvester_config_reader

    def _get_european_theme_taxonomy(self) -> str:
        return self._config_reader.get_property(ConfigConstants.SECTION_RDF_EXPORT, ConfigConstants.PROP_EUROPEAN_THEME_TAXONOMY )

    def _get_mapping_between_nti_and_european_themes(self) -> dict[str, str]:
        return self._config_reader.get_section_property_as_a_str_dict(ConfigConstants.SECTION_RDF_EXPORT, ConfigConstants.PROP_MAPPING_NTI_THEME_EUROPEAN_THEME, {} )

    def add_european_theme_taxomony_to_catalog_in_graph(self, graph:Graph, catalogs_with_european_theme_taxonomy) -> None:
        '''
        Add the european theme taxonomy to a catalog in a graph if the catalog does not include it
        
        :param graph: Graph to add the triple with the theme taxonomy
        :type graph: Graph
        '''
        if not graph:
            return
        theme_taxonomy_subjects = [s for s, p, _ in graph if p == DCAT.themeTaxonomy and str(s) not in catalogs_with_european_theme_taxonomy]
        european_theme_taxonomy = self._get_european_theme_taxonomy()
        for s in theme_taxonomy_subjects:
            graph.add((s, DCAT.themeTaxonomy, URIRef(european_theme_taxonomy)))

    def add_european_theme_to_dataset_in_graph(self, graph:Graph, entities_with_european_themes= None, datasets_european_themes_dict = None):
        '''
        Add the corresponding European themes to the NTI-RIPS topics list if the entity does not include any European theme
        
        :param graph: Graph to add the triples with the European themes
        :type graph: Graph
        
        :param datasets_european_themes_dict: european themes dictionary
        :type datasets_european_themes_dict: dict[str, str]
        '''
        if not graph:
            return
        if not datasets_european_themes_dict:
            datasets_european_themes_dict = {}
        if not entities_with_european_themes:
            entities_with_european_themes  = []
        mapping_nti_european_themes = self._get_mapping_between_nti_and_european_themes()
        theme_triples = [(s, o) for s, p, o in graph if p == DCAT.theme and str(s) not in entities_with_european_themes]
        
        for dataset_ref, theme in theme_triples:
            european_theme = mapping_nti_european_themes.get(str(theme), None)
            if european_theme and european_theme not in datasets_european_themes_dict.get(dataset_ref, []):
                graph.add((dataset_ref, DCAT.theme, URIRef(european_theme)))
                datasets_european_themes_dict.setdefault(dataset_ref, set()).add(european_theme)

    def dge_harvest_package_show_rdf(self, package_dict, rdf_format):
        '''
        Build the RDF of a package (dataset or datservice).
        Export rdf store data if the package has been harvester and it is in a RDF store graph. In other case, export package data in CKAN database.
        '''
        if not rdf_format:
            return
        serializer = DGEDCAPAPESRDFSerializer()
        rdf_format = serializer._url_to_rdflib_format(rdf_format)
        output = None
        _package_type = package_dict.get('type', None)
        if _package_type in [CommonPackageConstants.KEY_TYPE_DATASET_VALUE, CommonPackageConstants.KEY_TYPE_DATASERVICE_VALUE]:
            harvest_source_id = get_extra_value('harvest_source_id', package_dict)
            application_profile = get_extra_value(CommonPackageConstants.KEY_EXTRAS_APPLICATION_PROFILE, package_dict)
            ckan_uri = get_extra_value(CommonPackageConstants.KEY_EXTRAS_CKAN_URI, package_dict)
            guid = get_extra_value(CommonPackageConstants.KEY_EXTRAS_GUID, package_dict)
            if guid and ckan_uri and harvest_source_id and application_profile == CommonPackageConstants.KEY_EXTRAS_APPLICATION_PROFILE_DCAT_AP_ES_100_VALUE:
                output = self._dge_harvest_package_show_rdf_from_rdf_store(_package_type, harvest_source_id, ckan_uri,rdf_format)
                if not output:
                    output = self._dge_harvest_package_show_rdf_from_rdf_serializer(_package_type, package_dict, rdf_format)
            else:
               output =  self._dge_harvest_package_show_rdf_from_rdf_serializer(_package_type, package_dict, rdf_format)
        return output
    
    def _dge_harvest_package_show_rdf_from_rdf_store(self, package_type, harvest_source_id, ckan_uri, rdf_format, ):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        output = None
        try:
            harvest_source_graph = self._get_graph_uri(harvest_source_id)
            rdf_store = RDFStoreQuery(harvest_source_graph)
            node_classes_to_exclude = [DCAT.Catalog, DCAT.CatalogRecord, DCAT.DataService, DCAT.Dataset]
            if package_type and package_type == CommonPackageConstants.KEY_TYPE_DATASERVICE_VALUE:
                node_classes_to_exclude.append(DCAT.Distribution)
            node_graph = rdf_store.get_complete_node(ckan_uri, node_classes_to_exclude)
            if node_graph and len(node_graph) > 0:
                record_graph = rdf_store.get_complete_node(dge_harvest_build_catalog_record_uriref(ckan_uri), None)
                if record_graph and len(record_graph) > 0:
                    node_graph += record_graph

                creators_and_publishers = {o for _, p, o in node_graph.triples((None, None, None)) if p in {DCT.creator, DCT.publisher} and str(o).startswith(DCATAPESPrefixConstants.PUBLISHER_PREFIX)}
                self._add_organization_data(creators_and_publishers, node_graph)
                # Serialize graph
                output = node_graph.serialize(format=rdf_format)

        except Exception as e:
            log.error(f'{method_log_prefix} Exception {type(e)} serializing package from rdf store.: {str(e)}.', exc_info=True)
            output = None
        return output

    def _add_organization_data(self, creators_and_publishers, node_graph):
        if not (creators_and_publishers and node_graph):
            return
        for item in creators_and_publishers or []:
            splitted_upper_organization_uri = item.upper().split('/')
            organization_minhap = splitted_upper_organization_uri[-1] if splitted_upper_organization_uri and len(splitted_upper_organization_uri) > 0 else None
            available_organization = self.all_available_publishers.get(organization_minhap, None)
            available_organization_name = available_organization[1] if available_organization and len(available_organization) > 1 else None
            if available_organization_name:
                organization_uri = URIRef(f'{DCATAPESPrefixConstants.PUBLISHER_PREFIX}{organization_minhap}')
                node_graph.add((organization_uri, RDF.type, FOAF.Agent))
                node_graph.add((organization_uri, FOAF.name, Literal(available_organization_name, lang=config.get(ConfigConstants.CKAN_PROP_LOCALE_DEFAULT, 'es'))))
                node_graph.add((organization_uri, DCT.identifier, Literal(organization_minhap)))

    def _dge_harvest_package_show_rdf_from_rdf_serializer(self, package_type, package_dict, rdf_format):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        output = None
        try:
            serializer = DGEDCAPAPESRDFSerializer()
            if package_type == CommonPackageConstants.KEY_TYPE_DATASET_VALUE:
                output = serializer.serialize_dataset(package_dict, _format=rdf_format)
            else:
                output = serializer.serialize_dataservice(package_dict, _format=rdf_format)
        except Exception as e:
            log.error(f'{method_log_prefix} Exception {type(e)} serializing package from serializer: {str(e)}', exc_info=True)
            output = None
        return output