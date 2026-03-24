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
from rdflib import term, URIRef, BNode, Literal, ConjunctiveGraph

from ckan.plugins.toolkit import config
from ckanext.dcat.processors import RDFParserException
from ckanext.scheming import helpers as sh

log = logging.getLogger(__name__)

from ..constants.dcat_ap_es_constants import DCATAPESPrefixConstants, DCATAPESHarvesterConstants
from ..constants.nti_constants import NTIHarvesterConstants
from ..constants.constants import CommonPackageConstants
from ..harvester_config_reader import HarvesterConfigReader, HarvesterConfigReaderException
from ..constants.dcat_ap_es_constants import (NAMESPACES, DCT, DCAT, FOAF, RDF, ADMS, PROV, XSD_NAMESPACE, TIME, VCARD, TIME_TYPES, SKOS_NAMESPACE, SPDX, LOCN)
from ._profile_utils import _get_organization_minhap_from_organization_uri, _validate_iso8601_date
from ..decorators import log_debug, log_info

class DGEDCATAPESProfileParseUtilsBase():
    '''
    class containing utility methods for the profile DCAT-AP-ES
    '''
    ALLOWED_DATATYPES = [XSD_NAMESPACE.dateTime, XSD_NAMESPACE.date, XSD_NAMESPACE.gYearMonth, XSD_NAMESPACE.gYear]
    ALLOWED_TIME_INSTANTS = [TIME.inXSDDate, TIME.inXSDDateTimeStamp, TIME.inXSDgYear, TIME.inXSDgYearMonth, TIME.inTimePosition, TIME.inDateTime]

    def _get_log_prefix(self, method_name):
        return f'[{self.__class__.__name__}][{method_name}]'

    def __init__(self, graph):
        self._g = graph

    def object_uriref_value(self,  subject, predicate):
            '''
            Given a subject and a predicate, returns the value of the object

            Both subject and predicate must be rdflib URIRef or BNode objects

            If found, the string representation is returned, else an empty string
            '''
            fallback = ''
            for o in self._g.objects(subject, predicate):
                if isinstance(o, URIRef) or isinstance(o, BNode):
                    return str(o)
            return fallback

    def object_uriref_value_list(self, subject, predicate):
        '''
        Given a subject and a predicate, returns a list with all the values of
        the objects as str

        Both subject and predicate must be rdflib URIRef or BNode  objects

        If no values found, returns an empty string
        '''
        return [str(o) for o in self._g.objects(subject, predicate) if isinstance(o, URIRef) or isinstance(o, BNode)]

    def object_value_multilanguage_literal_list_dictionary(self, subject, predicate):
        '''
        Given a subject and a predicate, returns a dcitionary with the object value in
        each language

        Both subject and predicate must be rdflib URIRef or BNode  objects

        If no values found, returns an empty dictionary
        '''
        result = {}
        for o in self._g.objects(subject, predicate):
            if isinstance(o, Literal) and o.language:
                result.setdefault(o.language, []).append(str(o))
        return result

    def object_value_multilanguage_literal_dictionary(self, subject, predicate):
        '''
        Given a subject and a predicate, returns a dcitionary with the object value in
        each language

        Both subject and predicate must be rdflib URIRef or BNode  objects

        If no values found, returns an empty dictionary
        '''
        return {o.language: str(o) for o in self._g.objects(subject, predicate) if isinstance(o, Literal) and o.language}

    def object_value_literal_value(self, subject, predicate):
        '''
        Given a subject and a predicate, returns a dcitionary with the object value in
        each language

        Both subject and predicate must be rdflib URIRef or BNode  objects

        If no values found, returns an empty dictionary
        '''
        fallback = ''
        for o in self._g.objects(subject, predicate):
            if isinstance(o, Literal):
                return str(o)
        return fallback
    
    def object_value_literal_value_with_datatype(self, subject, predicate, datatypes):
        '''
        Given a subject and a predicate, returns the object value if
        it's a Literal object with one of the specified datatypes
        Both subject and predicate must be rdflib URIRef or BNode  objects
        If no values found, returns an empty string
        '''
        fallback = ''
        for o in self._g.objects(subject, predicate):
            if isinstance(o, Literal):
                for datatype in datatypes:
                    if o.datatype == datatype:
                        return str(o)
        return fallback
    
    def object_value_literal_value_list(self, subject, predicate):
        '''
        Given a subject and a predicate, returns a list with all the values of
        the objects as str

        Both subject and predicate must be rdflib Literal objects

        If no values found, returns an empty list
        '''
        return [str(o) for o in self._g.objects(subject, predicate) if isinstance(o, Literal)]

    def object_value_literal_list(self, subject, predicate):
        '''
        Given a subject and a predicate, returns a dcitionary with the object value 

        Both subject and predicate must be rdflib URIRef or BNode  objects

        If no values found, returns an empty list
        '''
        return [str(o) for o in self._g.objects(subject, predicate) if isinstance(o, Literal)]

    def _object(self, subject, predicate):
        """
        Helper for returning the first object for this subject and predicate

        Both subject and predicate must be rdflib URIRef or BNode objects

        Returns an rdflib reference (URIRef or BNode) or None if not found
        """
        for _object in self._g.objects(subject, predicate):
            return _object
        return None
    
    @log_debug
    def _get_other_identifiers(self, subject, predicate):
        '''
        Returns a list of other identifiers (adms:identifier)
        '''
        other_identifiers = []
        for o in self._g.objects(subject, predicate):
            if isinstance(o, URIRef):
                if (o, RDF.type, ADMS.Identifier) in self._g:
                    for other_identifier in self._g.objects(o, SKOS_NAMESPACE.notation):
                        if other_identifier:
                            other_identifiers.append(str(other_identifier))
                            break
        return other_identifiers
    
    @log_debug
    def _get_qualified_relations(self, subject, predicate):
        '''
        Returns a list of dicts of qualified relations (dcat:qualifiedRelation)
        Ex: [{"had_role": ["http://xxxx"], "qualified_relation_relation": ["http://xxxx"]}]
        '''
        qualified_relations = []
        for o in self._g.objects(subject, predicate):
            if isinstance(o, URIRef):
                had_role = None
                relation = None
                if (o, RDF.type, DCAT.Relationship) in self._g:
                    for predicate in self._g.predicates(o, None): 
                        if predicate == DCAT.hadRole:
                            had_role = self.object_uriref_value_list(o, DCAT.hadRole)
                        elif predicate == DCT.relation:
                            relation = self.object_uriref_value_list(o, DCT.relation)
                    if had_role and relation:
                        qualified_relation = {DCATAPESHarvesterConstants.RELATIONSHIP_HAD_ROLE: had_role, DCATAPESHarvesterConstants.RELATIONSHIP_RELATION: relation}
                        qualified_relations.append(qualified_relation)
        return qualified_relations
    
    @log_debug
    def _get_temporal(self, subject, predicate):
        '''
        Returns a dict of dicts of temporal values (from and to)
        '''
        index = 1
        coverage = {}
        for o in self._g.objects(subject, predicate):
            if isinstance(o, URIRef):
                start_date = None
                end_date = None
                if (o, RDF.type, DCT.PeriodOfTime) in self._g:
                    for period, value in self._g.predicate_objects(o):
                        if (period == DCAT.startDate):
                            if isinstance(value, Literal) and value.datatype in self.ALLOWED_DATATYPES:
                                start_date = value
                        elif (period == DCAT.endDate):
                            if isinstance(value, Literal) and value.datatype in self.ALLOWED_DATATYPES:
                                end_date = value
                if start_date and end_date:
                    coverage[index] = {"from": start_date, "to": end_date}
                    index += 1
        return coverage
    
    @log_debug
    def _get_creators(self, subject, predicate):
        '''
        Returns a list of dict for dct:creator
        (foaf:name, dct:identifier and dct:type)
        '''
        foaf_classes = [FOAF.Agent, FOAF.Organization, FOAF.Person]
        
        creators = []
        for o in self._g.objects(subject, predicate):
            if isinstance(o, URIRef) and any((o, RDF.type, foaf_class) in self._g for foaf_class in foaf_classes):
                creator = self._get_creator(o)
                if creator:
                    creators.append(creator)
        return creators

    def _get_creator(self, creator_value):
        creator = {}
        if not creator_value:
            return creator
        creator_identifier = ''
        creator_type = ''
        creator_name = {}
        is_creator_name_filled = False
        for predicate in self._g.predicates(creator_value, None):
            if predicate == FOAF.name:
                if not is_creator_name_filled:
                    creator_name = self.object_value_multilanguage_literal_dictionary(creator_value, predicate)
                    is_creator_name_filled = True
            elif predicate == DCT.type:
                creator_type = self.object_uriref_value(creator_value, predicate)
            elif predicate == DCT.identifier:
                creator_identifier = self.object_value_literal_value(creator_value, predicate)
            creator = {DCATAPESHarvesterConstants.CREATOR_NAME: creator_name, 
                       DCATAPESHarvesterConstants.CREATOR_IDENTIFIER: creator_identifier, 
                       DCATAPESHarvesterConstants.CREATOR_TYPE: creator_type}
        return creator
    
    @log_debug
    def _get_qualified_attributions(self, subject, predicate):
        '''
        Returns a list of dicts of qualified attribution (prov:qualifiedAttribution)
        Ex: [{"had_role": ["http://xxxx"], "agent": ["http://xxxx"]}]
        '''
        qualified_attributions = []
        for o in self._g.objects(subject, predicate):
            if isinstance(o, URIRef) and  (o, RDF.type, PROV.Attribution) in self._g:
                qualified_attribution = self._get_qualified_attribution(o, self._g.predicates(o, None))
                if qualified_attribution:
                    qualified_attributions.append(qualified_attribution)
        return qualified_attributions
    
    def _get_qualified_attribution(self, qualified_attribution_ref, qualified_attribution_values):
        qualified_attribution = None
        had_role = None
        agent = None
        for predicate in qualified_attribution_values: 
            if predicate == DCAT.hadRole:
                had_role = self.object_uriref_value_list(qualified_attribution_ref, DCAT.hadRole)
            elif predicate == PROV.agent:
                agent = self.object_uriref_value_list(qualified_attribution_ref, PROV.agent)
            if had_role and agent:
                qualified_attribution = {DCATAPESHarvesterConstants.ATTRIBUTION_HAD_ROLE: had_role, DCATAPESHarvesterConstants.ATTRIBUTION_AGENT: agent}
        return qualified_attribution
    
    @log_debug
    def _get_contact_points(self, subject, predicate):
        '''
        Returns a list of dicts of contact point (dcat:contactPoint)
        Ex: [{"organization_name": "xxxx", "hasUID": "http://xxxx"
            "fn": "xxxx", "hasEmail": "mailto:xxxx", "hasURL": "http://xxxx"
            }]
        '''
        contact_points = []
        for o in self._g.objects(subject, predicate):
            contact_point = self._get_contact_point(o)
            if contact_point:
                contact_points.append(contact_point)
        return contact_points

    def _get_contact_point(self, contact_point_object):
        contact_point = None
        if (contact_point_object and 
            isinstance(contact_point_object, URIRef) and 
            any((contact_point_object, RDF.type, vcard_class) in self._g for vcard_class in DCATAPESHarvesterConstants.CONTACT_POINT_VCARD_CLASSES)):
            organization_name = {}
            has_uid = ''
            cp_fn = {}
            has_email = []
            has_telephone = []
            has_url = []
            for predicate in self._g.predicates(contact_point_object, None): 
                if predicate == VCARD['organization-name']:
                    organization_name = self.object_value_multilanguage_literal_dictionary(contact_point_object, VCARD['organization-name'])
                elif predicate == VCARD.hasUID:
                    has_uid = self.object_uriref_value(contact_point_object, VCARD.hasUID)
                elif predicate == VCARD.fn:
                    cp_fn = self.object_value_multilanguage_literal_dictionary(contact_point_object, VCARD.fn)
                elif predicate == VCARD.hasEmail:
                    has_email = self.object_uriref_value_list(contact_point_object, VCARD.hasEmail)
                elif predicate == VCARD.hasTelephone:
                    has_telephone = self.object_uriref_value_list(contact_point_object, VCARD.hasTelephone)
                elif predicate == VCARD.hasURL:
                    has_url = self.object_uriref_value_list(contact_point_object, VCARD.hasURL)

            contact_point = {DCATAPESHarvesterConstants.CONTACT_POINT_VCARD_ORGANIZATION_NAME: organization_name, 
                             DCATAPESHarvesterConstants.CONTACT_POINT_VCARD_HAS_UID: has_uid, 
                             DCATAPESHarvesterConstants.CONTACT_POINT_VCARD_FN: cp_fn, 
                             DCATAPESHarvesterConstants.CONTACT_POINT_VCARD_HAS_EMAIL: has_email,
                             DCATAPESHarvesterConstants.CONTACT_POINT_VCARD_HAS_TELEPHONE: has_telephone, 
                             DCATAPESHarvesterConstants.CONTACT_POINT_VCARD_HAS_URL: has_url}
        return contact_point
    
    @log_debug
    def _get_checksum(self, subject, predicate):
        '''
        Returns a dict with algorithm and value for spdx:checksum
        '''
        checksum = {}
        for o in self._g.objects(subject, predicate):
            checksum = self._get_checksum_value(o)
            if checksum:
                return checksum
        return checksum

    def _get_checksum_value(self, checksum_object):
        checksum = {}
        if (checksum_object and isinstance(checksum_object, URIRef) and (checksum_object, RDF.type, SPDX.Checksum) in self._g):
            checksum_algorithm = ''
            checksum_value = ''
            for predicate in self._g.predicates(checksum_object, None):
                if predicate == SPDX.algorithm:
                    checksum_algorithm = self.object_uriref_value(checksum_object, predicate)
                elif predicate == SPDX.checksumValue:
                    checksum_value = self.object_value_literal_value_with_datatype(checksum_object, predicate, [XSD_NAMESPACE.hexBinary])
            if checksum_algorithm and checksum_value:
                checksum[DCATAPESHarvesterConstants.CHECKSUM_ALGORITHM] = checksum_algorithm
                checksum[DCATAPESHarvesterConstants.CHECKSUM_CHECKSUM_VALUE] = checksum_value
                return checksum
        return checksum
        
    
    @log_debug
    def _get_spatial(self, subject, predicate):
        '''
        Return a list of dict with values from dct:spatial
        '''
        spatials = []
        spatial_dict = {}
        for o in self._g.objects(subject, predicate):
            spatial_dict = {}
            if isinstance(o, URIRef) or isinstance(o, BNode):
                if any(o.startswith(spatial_prefix) for spatial_prefix in DCATAPESPrefixConstants.SPATIAL_PREFIXES_TUPLE):
                    spatial_dict[DCATAPESHarvesterConstants.SPATIAL_URI] = str(o)
                if (o, RDF.type, DCT.Location) in self._g:
                    spatial_dict.update(self._get_spatial_location_dict(o))
            if spatial_dict:
                spatials.append(spatial_dict)
        return spatials

    def _get_spatial_location_dict(self, spatial_value):
        geometry = bbox = centroid = ''
        if spatial_value:
            for predicate in self._g.predicates(spatial_value, None):
                if predicate == LOCN.geometry:
                    geometry = self.object_value_literal_value(spatial_value, predicate)
                if predicate == DCAT.bbox:
                    bbox = self.object_value_literal_value(spatial_value, predicate)
                if predicate == DCAT.centroid:
                    centroid = self.object_value_literal_value(spatial_value, predicate)
        if geometry or bbox or centroid:
            spatial = {DCATAPESHarvesterConstants.SPATIAL_LOCATION_GEOMETRY: geometry, 
                       DCATAPESHarvesterConstants.SPATIAL_LOCATION_BBOX: bbox, 
                       DCATAPESHarvesterConstants.SPATIAL_LOCATION_CENTROID: centroid}
        return spatial

    @log_debug
    def _get_samples(self, subject, predicate):
        '''
        Return a list of URIRefs from adms:sample
        '''
        samples = []
        for o in self._g.objects(subject, predicate):
            samples.append(o)
        return samples
    
    def _get_format_str_from_format_uri(self, format_uri, prefix):
        distribution_format = ''
        if format_uri and prefix:
            distribution_format = format_uri[len(prefix):]
        return distribution_format

    def publisher(self, subject, predicate, organizations):
        '''
        Returns a dict with details about dct:publisher entity
        '''
        publisher_id = None
        publisher_name = None
        publisher_minhap = None
        publisher_uri = None
        for publisher in self._g.objects(subject, predicate):
            publisher_uri = str(publisher)
            publisher_minhap, publisher_data = _get_organization_minhap_from_organization_uri(publisher_uri, organizations)
            publisher_name = publisher_data[1] if publisher_data and len(publisher_data) >1 else None
            publisher_id = publisher_data[0] if publisher_data and len(publisher_data) > 0 else None
            break
        return publisher_uri,  publisher_name, publisher_id, publisher_minhap

    def object_datetime_value(self, subject, predicate):
        '''
        Given a subject and a predicate, returns the value of the object

        Both subject and predicate must be rdflib URIRef or BNode objects

        If found, the string representation is returned, else an empty string
        '''
        fallback = ''
        for o in self._g.objects(subject, predicate):
            if isinstance(o, Literal) and o.datatype in self.ALLOWED_DATATYPES:
                return str(o)
        return fallback
    
    @log_debug
    def _distribution_format(self, distribution_ref, metadata):
        """
        Returns the URI of an element of http://publications.europa.eu/resource/authority/file-type
        or a str

        Given a reference (URIRef or BNode) to a dcat:Distribution, it will
        try to extract the formt

        Values for the format will be checked in the following order:
        1. value of dct:format if it is an instance of dct:IMT, eg:
            <dct:format>
                <dct:IMT rdf:value="text/html" rdfs:label="HTML"/>
            </dct:format>
        2. value of dct:format if it is an URIRef and is is an element of http://publications.europa.eu/resource/authority/file-type
        
        Return None if they couldn't be found.
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        _format = self._object(distribution_ref, metadata)
        distribution_format = None
        if _format:
            log.debug(f'{method_log_prefix} _format = {_format}')
            if isinstance(_format, (BNode, URIRef)):
                if self._object(_format, RDF.type) == DCT.IMT:
                    distribution_format = self._g.value(_format, default=None)
                elif isinstance(_format, URIRef):
                    distribution_format = _format
        log.debug(f'{method_log_prefix} distribution_format = {distribution_format}')
        return str(distribution_format) if distribution_format else None
    
    @log_debug
    def _parse_format_label_to_format_value(self, format_label):
        '''
        Given a format label, returns its value using choices in schema
        Ex: PDF = application/pdf
        '''
        dataset = sh.scheming_get_schema('dataset', 'dataset')
        formats = sh.scheming_field_by_name(dataset.get('resource_fields'), 'format')        
        for choice in formats['choices']:
            if choice['label'] == format_label:
                format_value = choice.get('value', format_label)
                return format_value
        log.debug('Format label not found in Schema format choices')
        return format_label
