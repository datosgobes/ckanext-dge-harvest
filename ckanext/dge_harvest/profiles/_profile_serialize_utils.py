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
import json
import inspect
import re
import ast
from functools import partial
from typing import List
from rdflib import URIRef, BNode, Literal, Graph
from ckantoolkit import h, config
from ckanext.scheming import helpers as sh
from ..constants import (DCATAPESPrefixConstants, DCATAPESConfigConstants, CommonPackageConstants, 
                         NTIDatasetConstants, NTIHarvesterConstants, DCATAPESHarvesterConstants)
from ..harvester_config_reader import HarvesterConfigReader, HarvesterConfigReaderException
from ..constants.dcat_ap_es_constants import (RDF, XSD, SKOS, RDFS, DCAT, DCT, ADMS, XSD, VCARD, FOAF, 
                                              SCHEMA, SKOS, LOCN, OWL, SPDX, NAMESPACES, TIME, PROV)
from ._profile_utils import _get_organization_minhap_from_organization_uri, _get_encoded_url
from ..decorators import log_info, log_debug
from ..utils import dge_harvest_build_catalog_record_uriref

log = logging.getLogger(__name__)

@log_debug
def set_translate_fields_items(items, metadata_info, locales_offered, config_reader:HarvesterConfigReader, section:str, properties_prefix:str):
    '''
    Returns an array with metadata info for fields that can have several
    values depending on the language. For each field, as many items will be
    created as there are languages
    '''
    for info in metadata_info:
        key, predicate, default, default_locale = info
        for locale in locales_offered:
            items.append((f'{key}_{locale}', 
                          predicate,
                          get_str_value_of_property_from_config_reader(config_reader, properties_prefix, f'{key}_{locale}', default, section),
                          locale))
    return items

@log_debug
def set_translate_fields_metadata(items, catalog_dict, subject, g):
    '''
    Obtains an array of items with several translations and sets
    metadata for the graph passed as a parameter
    '''
    if items:
        for item in items:
            key, predicate, fallback, locale = item
            if catalog_dict:
                value = catalog_dict.get(key, fallback)
            else:
                value = fallback
            if value:
                g.add((subject, predicate, Literal(value, lang=locale)))

@log_debug
def set_multiple_basic_fields_metadata(items, catalog_dict, subject, g):
    '''
    Sets URI fields metadata for the graph passed as a parameter
    '''
    if items:
        for item in items:
            key, predicate, fallback = item
            if catalog_dict:
                value = catalog_dict.get(key, fallback)
            else:
                value = fallback
            if value:
                multivalues = value.split(',')
                if multivalues and len(multivalues) > 0:
                    for multivalue in multivalues:
                        g.add((subject, predicate, URIRef(multivalue)))
                else:
                    g.add((subject, predicate, URIRef(value)))

@log_debug
def set_publisher_metadata(publisher, organizations, g, default_locale):
    '''
    Sets extended information for the dct:publisher metadata and
    adds it to the graph passed as a parameter. The info would be
    different depending on whether the graph is from the EDP or not
    '''
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    uriref_publisher = URIRef(publisher)
    organization_minhap, org = _get_organization_minhap_from_organization_uri(publisher, organizations)
    if org:
        publisher = [org[1], DCATAPESPrefixConstants.PUBLISHER_PREFIX + organization_minhap, organization_minhap]
        publisher_data = {
                DCATAPESHarvesterConstants.CREATOR_NAME: {default_locale: publisher[0]},
                DCATAPESHarvesterConstants.CREATOR_IDENTIFIER: organization_minhap
            }
        
        g.add((uriref_publisher, RDF.type, FOAF.Agent))
        _add_foaf_agent(uriref_publisher, publisher_data, g, False)
    else:
        log.debug(f'{method_log_prefix} No agent nor name')

@log_debug
def _add_skos_concept(g, concept=None, value=None, labels=None, descriptions=None, mapping=None, notation=None):
    if concept and value and isinstance(concept, URIRef):
        g.add((concept, RDF.type, SKOS.Concept))
        if labels:
            if isinstance(labels, dict):
                for key, value in list(labels.items()):
                    if value and value != '':
                        g.add((concept, SKOS.prefLabel, Literal(value, lang=key)))
            else:
                if labels and labels != '':
                    g.add((concept, SKOS.prefLabel, Literal(labels)))
        if descriptions:
            if isinstance(descriptions, dict):
                for key, value in list(descriptions.items()):
                    if value and value != '':
                        g.add((concept, SKOS.definition, Literal(value, lang=key)))
            else:
                if descriptions and descriptions != '':
                    g.add((concept, SKOS.definition, Literal(descriptions)))
        if mapping:
            g.add((concept, SKOS.broadMatch, URIRef(mapping)))
        if notation:
            g.add((concept, SKOS.notation, Literal(notation)))

@log_debug
def _set_creator_metadata(creator_uri, creator_name, creator_identifier, default_locale, g, catalog_ref, organizations):
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    if creator_uri.startswith(DCATAPESPrefixConstants.PUBLISHER_PREFIX):
        creator_minhap, creator_org_data = _get_organization_minhap_from_organization_uri(creator_uri, organizations)
        if creator_minhap and creator_org_data:
            g.add((catalog_ref, DCT.creator, URIRef(creator_uri)))
            creator = {
                DCATAPESHarvesterConstants.CREATOR_NAME: {default_locale: creator_org_data[1]},
                DCATAPESHarvesterConstants.CREATOR_IDENTIFIER: creator_minhap
            }
            _add_foaf_agent( URIRef(creator_uri), creator, g, False)
        else:
            log.info(f'{method_log_prefix} There is no data for organization with dir3 = {creator_minhap}')
    elif creator_uri and creator_name and creator_identifier:
        g.add((catalog_ref, DCT.creator, URIRef(creator_uri)))
        creator = {
            DCATAPESHarvesterConstants.CREATOR_NAME: {default_locale: creator_name},
            DCATAPESHarvesterConstants.CREATOR_IDENTIFIER: creator_identifier
        }
        _add_foaf_agent( URIRef(creator_uri), creator, g, False)

@log_debug
def _set_creators_metadata(creators, default_locale, g, catalog_ref, organizations):
    '''
    Sets extended information for the dct:creator metadata
    and adds it to the graph passed as a parameter
    '''
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    for creator in creators or []:
        creator_data = creator.split('|') or []
        creator_uri = creator_data[0] if len(creator_data) > 0 else None
        creator_name = creator_data[1] if len(creator_data) > 1 else None
        creator_identifier = creator_data[2] if len(creator_data) > 2 else None
        log.debug(f'{method_log_prefix} creator_data={creator_data}.')
        _set_creator_metadata(creator_uri, creator_name, creator_identifier, default_locale, g, catalog_ref, organizations)

def add_resource_list_triple(g, subject, predicate, value, labels=None, descriptions=None, mapping=None,
                                  notation=None, encode_url=False):
    '''
    Adds as many triples to the graph as values

    Values are literal strings, if `value` is a list, one for each
    item. If `value` is a string there is an attempt to split it using
    commas, to support legacy fields.
    '''
    if not value:
        return
    for item in _get_items_from_value(value) or []:
        if item:
            concept = URIRef(_get_encoded_url(item, encode_url))
            g.add((subject, predicate, concept))
            if labels or descriptions or mapping or notation:
                _add_skos_concept(g,concept, value, labels, descriptions, mapping, notation)

def _get_items_from_value(value):
    items = []
    # List of values
    if isinstance(value, list):
        items = _normalize_list_as_a_list(value) or value
    elif isinstance(value, str):
        try:
            # JSON list
            items = json.loads(value)
        except ValueError:
            if ',' in value:
                # Comma-separated list
                items = value.split(',')
            else:
                # Normal text value
                items = [value]
    return items

def _normalize_list_as_a_list(value):
    if isinstance(value, list) and len(value) > 0:
        first_element = value[0]
        if isinstance(first_element, list):
            value = first_element
        if isinstance(first_element, str) and first_element.startswith("[") and first_element.endswith("]"):
            try:
                value = _normalize_str_as_a_list(first_element)
            except Exception:
                pass  # If an error, return original list
    return value

def _normalize_str_as_a_list(value):
    if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
        try:
            parsed_list = ast.literal_eval(value)
            if isinstance(parsed_list, list):  
                value = parsed_list  # Return corrected list
        except (SyntaxError, ValueError) as e:
            match = re.search(r'\["([\s\S]*?)"\]', value)
            if match:
                value = [match.group(1)]
    return value
            
@log_debug
def add_accrual_periodicity(g, dataset_ref, frequency):
    '''
    Adds accrual periodicity to the graph
    
    :param g: Graph where accrual periodicity will be added
    :type g: Graph
    
    :param dataset_ref: dataset URIref
    :type dataset_ref: str
    
    :param frequency: dictionary of frequency with its type and value
    :type frequency: dict[str,str]
    '''
    if frequency:
        ftypes = {'seconds': TIME.seconds,
                    'minutes': TIME.minutes,
                    'hours': TIME.hours,
                    'days': TIME.days,
                    'weeks': TIME.weeks,
                    'months': TIME.months,
                    'years': TIME.years}
        ftype = frequency.get('type')
        fvalue = frequency.get('value')
        if ftype and ftype in list(ftypes.keys()) and fvalue is not None:
            frequency = URIRef("%s/%s" % (dataset_ref, 'Frequency'))
            duration = URIRef("%s/%s" %
                                (dataset_ref, 'DurationDescription'))
            g.add((frequency, RDF.type, DCT.Frequency))
            g.add((duration, RDF.type, TIME.DurationDescription))
            g.add((dataset_ref, DCT.accrualPeriodicity, frequency))
            g.add((frequency, RDF.value, duration))
            g.add((duration, ftypes.get(ftype), Literal(
                fvalue, datatype=XSD.decimal)))

@log_debug
def add_temporal_resolution(profile, g, dataset_ref, temporal_coverage, is_nti_dataset, encode_url=False):
    '''
    Adds temporal resolution to the graph
    
    :param profile: profile used to add triples in graph
    :type profile: RDFProfile
    
    :param g: Graph where temporal resolution will be added
    :type g: Graph
    
    :param dataset_ref: dataset URIRef
    :type dataset_ref: URIRef
    
    :param temporal_coverage: dictionary with dictionaries of temporal coverage values
    :type temporal_coverage: dict[str,dict[str,str]]
    '''
    if not temporal_coverage:
        return
    i = 1
    for key, value in list(temporal_coverage.items()):
        if not value:
            continue
        start = value.get('from')
        end = value.get('to')
        if start or end:
            item_uri = f'{dataset_ref}/PeriodOfTime-{i}'
            temporal_extent = URIRef(_get_encoded_url(item_uri, encode_url))
            g.add((temporal_extent, RDF.type, DCT.PeriodOfTime))
            _add_temporal_resolution_value(profile, temporal_extent, start, end, is_nti_dataset)
            g.add((dataset_ref, DCT.temporal, temporal_extent))
            i = i + 1

def _add_temporal_resolution_value(profile, temporal_uri_ref, start, end, is_nti_dataset):
    if profile and temporal_uri_ref and (start or end) and is_nti_dataset:
        if start:
            if is_nti_dataset:
                profile._add_nti_date_triple(temporal_uri_ref, DCAT.startDate, start)
            else:
                profile._add_date_triple(temporal_uri_ref, DCAT.startDate, start, Literal)
        if end:
            if is_nti_dataset:
                profile._add_nti_date_triple(temporal_uri_ref, DCAT.endDate, end)
            else:
                profile._add_date_triple(temporal_uri_ref, DCAT.endDate, end, Literal)

@log_debug
def add_distribution_format(g, distribution, resource_ref, resource_dict, dataset_dict):
    '''
    Adds distribution format to the graph
    
    :param g: Graph where format will be added
    :type g: Graph
    
    :param distribution: distribution URIref
    :type distribution: URIRef
    
    :param resource_ref: distribution URI
    :type resource_ref: str
    
    :param dataset_ref: dataset URIref
    :type dataset_ref: URIRef
    
    :param resource_dict: The resource dict
    :type resource_dict: dict
    
    :param dataset_dict: The dataset dict
    :type dataset_dict: dict
    '''
    format = resource_dict.get(NTIDatasetConstants.KEY_DATASET_RESOURCE_FORMAT, None)
    if format:
        imt = URIRef("%s/format" % resource_ref)
        g.add((distribution, DCT['format'], imt))
        g.add((imt, RDF.type, DCT.IMT))

        formats = dataset_dict.get(NTIHarvesterConstants.EXPORT_AVAILABLE_RESOURCE_FORMATS, {}) 
        label = None
        if format and format in formats:
            label = formats.get(format, None)
        else:
            _dataset = sh.scheming_get_schema('dataset', 'dataset')
            res_format = sh.scheming_field_by_name(_dataset.get('resource_fields'),
                                                    'format')
            formats[format] = sh.scheming_choices_label(res_format['choices'], format)
            label = formats.get(format, None)
            dataset_dict[NTIHarvesterConstants.EXPORT_AVAILABLE_RESOURCE_FORMATS] = formats
        if label:
            g.add((imt, RDFS.label, Literal(label)))
        g.add((imt, RDF.value, Literal(resource_dict[NTIDatasetConstants.KEY_DATASET_RESOURCE_FORMAT])))

def get_str_value_of_property_from_config_reader(config_reader:HarvesterConfigReader, property_prefix:str, property_suffix:str, default_value:str=None, section:str=None) -> str:
    '''
    Get the value of a property of a config file as a string
    
    :param config_reader: Reader of a config file
    :type config_reader: HarvesterConfigReader
    
    :param property_prefix: Property name prefix
    :type property_prefix: str
    
    :param property_suffix: Property name suffix
    :type property_suffix: str
    
    :param default_value: Default value if property is not found or has no value. None by default
    :type default_value: str
    
    :param section: Name of the section where the property is located. None by default.
    :type section: str
    
    :return value of property
    :rtype: str
    '''
    try:
        if not section:
            section = DCATAPESConfigConstants.SECTION_RDF_EXPORT
        return config_reader.get_property(section, f'{property_prefix}{property_suffix}', default_value)
    except HarvesterConfigReaderException as e:
        log.error(f'Error getting property from harvester config reader. Exception {str(e)}')
        return default_value

def get_list_of_str_values_of_property_from_config_reader(config_reader:HarvesterConfigReader, property_prefix:str, property_suffix:str, default_value:str=None, section:str=None) -> List[str]:
    '''
    Get the value of a property of a config file as a list of string
    
    :param config_reader: Reader of a config file
    :type config_reader: HarvesterConfigReader
    
    :param property_prefix: Property name prefix
    :type property_prefix: str
    
    :param property_suffix: Property name suffix
    :type property_suffix: str
    
    :param default_value: Default value if property is not found or has no value. None by default
    :type default_value: str
    
    :param section: Name of the section where the property is located. None by default.
    :type section: str
    
    :return value of property
    :rtype: List[str]
    '''
    try:
        if not section:
            section = DCATAPESConfigConstants.SECTION_RDF_EXPORT
        return config_reader.get_section_property_as_a_list(section, f'{property_prefix}{property_suffix}', default_value, '\n')
    except HarvesterConfigReaderException as e:
        log.error(f'Error getting property from harvester config reader. Exception {str(e)}')
        return default_value

def _add_catalog_record(entity_ref:URIRef, data_dict:dict[str, object], conforms_to_uri:str, g:Graph):
    '''
    Given a object URIRef, create the CatalogRecord node
    '''
    record_uri_ref = dge_harvest_build_catalog_record_uriref(entity_ref)
    g.add((record_uri_ref, RDF.type, DCAT.CatalogRecord))
    g.add((record_uri_ref, FOAF.primaryTopic, entity_ref))
    
    timezone = h.get_display_timezone()
    metadata_modified = data_dict.get(CommonPackageConstants.KEY_METADATA_MODIFIED, None)
    metadata_created = data_dict.get(CommonPackageConstants.KEY_METADATA_CREATED, None)
    if metadata_modified:
        g.add((record_uri_ref, DCT.modified, Literal(h.date_str_to_datetime(metadata_modified).astimezone(timezone).isoformat(), datatype=XSD.dateTime)))
    if metadata_created:
        g.add((record_uri_ref, DCT.issued, Literal(h.date_str_to_datetime(metadata_created).astimezone(timezone).isoformat(), datatype=XSD.dateTime)))
    if conforms_to_uri:
        g.add((record_uri_ref, DCT.conformsTo, URIRef(conforms_to_uri)))

def add_geographical_coverage(g, dataset_ref, geographical_coverage_list, encode_url = False):
    '''
    Adds geogrpahical coverage to the graph
    
    :param profile: profile used to add triples in graph
    :type profile: RDFProfile
    
    :param g: Graph where temporal resolution will be added
    :type g: Graph
    
    :param dataset_ref: dataset URIRef
    :type dataset_ref: URIRef
    
    :param geographical_coverage_list: list of dictionaries of geographcial coverage values
    :type geographical_coverage_list: List[dict[str,str,str,str]]
    '''
    index = 1
    for geographical_spatial in geographical_coverage_list or []:
        uri = geographical_spatial.get(DCATAPESHarvesterConstants.SPATIAL_URI)
        geometry = geographical_spatial.get(DCATAPESHarvesterConstants.SPATIAL_LOCATION_GEOMETRY)
        bbox = geographical_spatial.get(DCATAPESHarvesterConstants.SPATIAL_LOCATION_BBOX)
        centroid = geographical_spatial.get(DCATAPESHarvesterConstants.SPATIAL_LOCATION_CENTROID)
        _uri_spatial = f'{dataset_ref}/spatial/{index}'
        if uri:
            _uri_spatial = uri
        uri_spatial = URIRef(_get_encoded_url(_uri_spatial, encode_url))
        g.add((dataset_ref, DCT.spatial, uri_spatial))
        _add_spatial_location(bbox, centroid, geometry, g, uri_spatial)

def _add_spatial_location(bbox, centroid, geometry, g, uri_spatial):
    if geometry or bbox or centroid:
        g.add((uri_spatial, RDF.type, DCT.Location))
        if bbox:
            g.add((uri_spatial, DCAT.bbox, Literal(bbox)))
        if centroid:
            g.add((uri_spatial, DCAT.centroid, Literal(centroid)))
        if geometry:
            g.add((uri_spatial, DCAT.geometry, Literal(geometry)))

def add_vcard_kinds(g, package_ref, metadata, contact_point_list, encode_url = False):
    '''
    '''
    contact_point_index = 0
    for contact_point in contact_point_list or []:
        contact_point_index += 1
        _uri_contact_point = f'{package_ref}/contact-point/{contact_point_index}'
        uri_contact_point = URIRef(_get_encoded_url(_uri_contact_point, encode_url))
        g.add((package_ref, metadata, uri_contact_point))
        _add_vcard_kind(uri_contact_point, contact_point, g, encode_url)

def _add_vcard_kind(uri_vcard_kind, vcard_kind_item, g, encode_url):
    action_dict = {
        DCATAPESHarvesterConstants.CONTACT_POINT_VCARD_FN: partial(_add_multilanguage_literal, g=g, predicate=VCARD.fn),
        DCATAPESHarvesterConstants.CONTACT_POINT_VCARD_ORGANIZATION_NAME:partial(_add_multilanguage_literal, g=g, predicate=VCARD['organization-name']),
        DCATAPESHarvesterConstants.CONTACT_POINT_VCARD_HAS_EMAIL: partial(_add_url_list, g=g, predicate=VCARD.hasEmail, encode_url= encode_url),
        DCATAPESHarvesterConstants.CONTACT_POINT_VCARD_HAS_TELEPHONE: partial(_add_url_list, g=g, predicate=VCARD.hasTelephone, encode_url= encode_url),
        DCATAPESHarvesterConstants.CONTACT_POINT_VCARD_HAS_URL: partial(_add_url_list, g=g, predicate=VCARD.hasURL, encode_url= encode_url),
        DCATAPESHarvesterConstants.CONTACT_POINT_VCARD_HAS_UID: partial(_add_url_list, g=g, predicate=VCARD.hasUID, encode_url= encode_url),
    }
    g.add((uri_vcard_kind, RDF.type, VCARD.Kind))
    _add_triple_from_action_dict(action_dict, vcard_kind_item, uri_vcard_kind)

def add_creators(g, package_ref, creator_list, encode_url = False):
    creator_index = 0
    for creator in creator_list or []:
        creator_index += 1
        _uri_creator = f'{package_ref}/creator/{creator_index}'
        uri_creator = URIRef(_get_encoded_url(_uri_creator, encode_url))
        g.add((package_ref, DCT.creator, uri_creator))
        g.add((uri_creator, RDF.type, FOAF.Agent))
        _add_foaf_agent(uri_creator, creator, g, encode_url)

def _add_foaf_agent(uri_foaf_agent, foaf_agent_item, g, encode_url):
    action_dict = {
        DCATAPESHarvesterConstants.CREATOR_NAME: partial(_add_multilanguage_literal, g=g, predicate=FOAF.name),
        DCATAPESHarvesterConstants.CREATOR_IDENTIFIER: partial(_add_literal, g=g, predicate=DCT.identifier, datatype=None),
        DCATAPESHarvesterConstants.CREATOR_TYPE: partial(_add_url_list, g=g, predicate=DCT.type, encode_url= encode_url)
    }
    _add_triple_from_action_dict(action_dict, foaf_agent_item, uri_foaf_agent)

def add_qualified_relations(g, package_ref, metadata, qualified_relation_list, encode_url = False):
    _index = 0
    
    action_dict = {
        DCATAPESHarvesterConstants.RELATIONSHIP_HAD_ROLE: partial(_add_url_list, g=g, predicate=DCAT.hadRole, encode_url= encode_url),
        DCATAPESHarvesterConstants.RELATIONSHIP_RELATION: partial(_add_url_list, g=g, predicate=DCT.relation, encode_url= encode_url)
    }
    for item in qualified_relation_list or []:
        _index += 1
        _uri = f'{package_ref}/qualified-relation/{_index}'
        uri = URIRef(_get_encoded_url(_uri, encode_url))
        g.add((package_ref, metadata, uri))
        g.add((uri, RDF.type, DCAT.Relationship))
        _add_triple_from_action_dict(action_dict, item, uri)

def add_qualified_attributions(g, package_ref, metadata, qualified_attribution_list, encode_url = False):
    _index = 0
    
    action_dict = {
        DCATAPESHarvesterConstants.ATTRIBUTION_HAD_ROLE: partial(_add_url_list, g=g, predicate=DCAT.hadRole, encode_url= encode_url),
        DCATAPESHarvesterConstants.ATTRIBUTION_AGENT: partial(_add_url_list, g=g, predicate=PROV.agent, encode_url= encode_url)
    }
    for item in qualified_attribution_list or []:
        _index += 1
        _uri = f'{package_ref}/qualified-attribution/{_index}'
        uri = URIRef(_get_encoded_url(_uri, encode_url))
        g.add((package_ref, metadata, uri))
        g.add((uri, RDF.type, DCAT.Relationship))
        _add_triple_from_action_dict(action_dict, item, uri)

def add_checksum(g, package_ref, metadata, checksum, encode_url = False):
   
    action_dict = {
        DCATAPESHarvesterConstants.CHECKSUM_ALGORITHM: partial(_add_url_list, g=g, predicate=SPDX.algorithm, encode_url= encode_url),
        DCATAPESHarvesterConstants.CHECKSUM_CHECKSUM_VALUE: partial(_add_literal, g=g, predicate=SPDX.checksumValue, datatype=None)
    }
    if checksum:
        _uri = f'{package_ref}/checksum'
        uri = URIRef(_get_encoded_url(_uri, encode_url))
        g.add((package_ref, metadata, uri))
        g.add((uri, RDF.type, SPDX.Checksum))
        _add_triple_from_action_dict(action_dict, checksum, uri)

def _add_triple_from_action_dict(action_dict, item_dict, subject_ref):
    for key, value in item_dict.items():
        action = action_dict.get(key)
        if action and value:
            action(subject_ref=subject_ref, value=value)

def _add_literal(g, subject_ref, predicate, value, datatype = None):
    if value and isinstance(value, str):
        if datatype:
           g.add((subject_ref, predicate, Literal(value, datatype=datatype))) 
        else:
            g.add((subject_ref, predicate, Literal(value)))

def _add_multilanguage_literal(g, subject_ref, predicate, value):
    if value and isinstance(value, dict):
        for k, v in list(value.items()):
            g.add((subject_ref, predicate, Literal(v, lang=k)))

def _add_url_list(g, subject_ref, predicate, value, encode_url=False):
    if value:
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list):
            for item in value:
                g.add((subject_ref, predicate, URIRef(_get_encoded_url(item, encode_url))))
