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

import iso8601
import json
import logging
import pytz
import re
import inspect

from typing import List
from urllib import parse as urllib_parse

from ckantoolkit import config
from rdflib import term
from rdflib.term import BNode, Literal, URIRef
from rdflib.namespace import XSD, SKOS, RDF, RDFS

from ckanext.dcat.profiles import RDFProfile, DCT, DCAT
from ckanext.dcat.exceptions import RDFProfileException

from ckanext.dge_harvest import helpers as dhh
from ckanext.dge_harvest.constants.constants import ConfigConstants, PrefixConstants, HarvesterConstants
from ckanext.dge_harvest.constants.nti_constants import NTIDatasetConstants, NTIHarvesterConstants

from ckan.lib import helpers
from ...dge_harvest.decorators import log_info, log_debug

log = logging.getLogger(__name__)

tagname_match = re.compile(r"[\w áàâçcoéèêëíîïóôúûùüÿñ&-æœ·\u2019\u0027]+$", re.UNICODE)

class DGEProfile(RDFProfile):

    def _get_log_prefix(self, method_name):
        return f'[{self.__class__.__name__}][{method_name}]'

    def __init__(self, graph, dataset_type="dataset", compatibility_mode=False):
        super().__init__(graph = graph, dataset_type=dataset_type, compatibility_mode=compatibility_mode)
        self.locales_offered = self._get_ckan_locales_offered()
        self.default_locale =  self._get_ckan_default_locale()
        self._default_lang = self.default_locale
        self._form_languages =  self._get_ckan_default_locale()
        self.base_parse_utils = None

    def _get_ckan_locales_offered(self) -> List[str]:
        ''' Returns locales offered '''
        locales = config.get(ConfigConstants.CKAN_PROP_LOCALES_OFFERED, None)
        return locales.split() if locales else None    

    def _get_ckan_default_locale(self):
        ''' Returns default locale '''
        return config.get(ConfigConstants.CKAN_PROP_LOCALE_DEFAULT, 'es')

    def _is_uri(self, uri):
        ''' Returns True is the given uri is a valid uri. '''
        return dhh.dge_harvest_is_uri(uri)

    @log_debug
    def _get_uri_ref(self, object_ref = None):
        '''Returns URIRef or None
        object_ref: reference to an object'''
        uri_ref = None
        if (object_ref and len(object_ref) > 0):
            #  (explicitly show the missing ones)
            uri_ref = (str(object_ref)
                    if isinstance(object_ref, term.URIRef)
                                             else None)
        return uri_ref

    def _build_error_warning_msg(self, msg=None, prefix=None):
        msg = f"{msg or ''}"
        if prefix and len(prefix) > 0:
            msg = f"[{prefix}] {msg}"
        return msg


    def _object_value(self, subject, predicate):
        '''
        Given a subject and a predicate, returns the value of the object

        Both subject and predicate must be rdflib URIRef or BNode objects

        If found, the unicode representation is returned, else None
        '''
        result = None
        for o in self.g.objects(subject, predicate):
            if o:
                if result is None:
                    result = str(o)
                else:
                    errormsg = HarvesterConstants.UNEXPECTED_MULTIPLE_OBJECTS
                    raise RDFProfileException(errormsg)
        return result

    def _object_value_list(self, subject, predicate, unicode_value=True):
        '''
        Given a subject and a predicate, returns a list with all the values of
        the objects

        Both subject and predicate must be rdflib URIRef or BNode  objects

        If no values found, returns an empty string
        '''
        return [str(o) if unicode_value else o for o in self.g.objects(subject, predicate)]

    def _strip_value(self, value):
        '''
        Returns a string without blanks at the beginning and the end of the string

        Give a value, delete [ \t\n\r] char from the beginning and the end

        Result a string without blanks or None if value is empty
        '''
        result = None
        if value:
            value = value.strip(' \t\n\r')
            if len(value) > 0:
                result = value
        return result

    def _get_value_from_dict(self, _dict, key, fallbacks=None):
        '''
        Returns the value for the given key on a CKAN dict

        The subject and predicate of the triple are passed as the relevant
        RDFLib objects (URIRef or BNode). The object is always a literal value,
        which is extracted from the dict using the provided key (see
        `_get_dict_value`). If the value for the key is not found, then
        additional fallback keys are checked.
        '''
        value = self._get_dict_value(_dict, key)
        if not value and fallbacks:
            for fallback in fallbacks:
                value = self._get_dict_value(_dict, fallback)
                if value:
                    break
        return value

    def _add_translated_triple_field_from_dict(self, _dict, subject, predicate, key, fallbacks=None):
        '''
        Adds a new triple to the graph for each language with the provided parameters

        The subject and predicate of the triple are passed as the relevant
        RDFLib objects (URIRef or BNode). The object is always a literal value,
        which is extracted from the dict using the provided key (see
        `_get_dict_value`). If the value for the key is not found, then
        additional fallback keys are checked.
        '''
        value = self._get_dict_value(_dict, key)
        if not value and fallbacks:
            for fallback in fallbacks:
                value = self._get_dict_value(_dict, fallback)
                if value:
                    break

        # List of values
        if isinstance(value, dict):
            items = value
            for k, v in list(items.items()):
                if k and v:
                    self.g.add((subject, predicate, Literal(v, lang=k)))

    def _add_translated_list_triple_field_from_dict(self, _dict, subject, predicate, key, fallbacks=None):
        '''
        Adds a new triple to the graph for each language with the provided parameters

        The subject and predicate of the triple are passed as the relevant
        RDFLib objects (URIRef or BNode). The object is always a literal list value,
        which is extracted from the dict using the provided key (see
        `_get_dict_value`). If the value for the key is not found, then
        additional fallback keys are checked.
        '''
        value = self._get_dict_value(_dict, key)
        if not value and fallbacks:
            for fallback in fallbacks:
                value = self._get_dict_value(_dict, fallback)
                if value:
                    break

        # List of values
        if isinstance(value, dict):
            items = value
            for k, v in list(items.items()):
                if k and v:
                    for i in v:
                        self.g.add((subject, predicate, Literal(i, lang=k)))

    def _add_nti_date_triple(self, subject, predicate, value):
        '''
        Adds a new triple with a date object

        Dates are parsed using iso8601, and if the date obtained is correct,
        added to the graph as an XSD.dateTime value.
        All dates are in timezone 'Europe/Madrid'

        If there are parsing errors, the literal string value is added.
        '''
        if not value:
            return
        try:
            default_timezone = pytz.timezone(ConfigConstants.DEFAULT_TIMEZONE)
            naive = iso8601.parse_date(value, None)

            try:
                local_dt = default_timezone.localize(naive, is_dst=None)
            except pytz.exceptions.AmbiguousTimeError:
                log.info(f"AmbiguousTimeError - {value}")
                local_dt = default_timezone.localize(naive, is_dst=False)
            final_local_dt = local_dt.replace(microsecond=0)
            self.g.add((subject, predicate, Literal(final_local_dt.isoformat(),
                                                    datatype=XSD.dateTime)))
        except iso8601.ParseError:
            self.g.add((subject, predicate, Literal(value)))

    def _are_literal_objects(self, subject, predicate):
        '''
        Given a subject and a predicate, returns True
        if datatype of all found objects is an instance of Literal

        Both subject and predicate must be rdflib URIRef or BNode objects
        '''
        for o in self.g.objects(subject, predicate):
            if o and not isinstance(o, Literal):
                return False
        return True

    @staticmethod
    def __get_data_type_http(data_type):
        try:
            url = urllib_parse.urlparse(str(data_type))
            if url.scheme == 'https':
                return Literal(None, datatype=urllib_parse.urlunparse(
                    ('http', url.netloc, url.path, url.params,
                     url.query, url.fragment))).datatype
        except:
            pass
        return data_type

    @log_debug
    def _object_value_datatype(self, subject, predicate):
        '''
        Given a subject and a predicate, returns the value and the datatype
        of the object

        Both subject and predicate must be rdflib URIRef or BNode objects

        If found, the unicode representation and datatype is returned, else None
        '''
        r1 = r2 = None
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        msg = f"{method_log_prefix}|PARAMS|Subject: {repr(subject)}, Predicate: {repr(predicate)}".replace('%','%%')
        log.debug(msg)
        for o in self.g.objects(subject, predicate):
            msg = f"{method_log_prefix}|OBJECT|o: {repr(o)}".replace('%', '%%')
            log.debug(msg)
            if o is not None:
                if r1 is None:
                    if isinstance(o, Literal):
                        r1 = str(o)
                        msg = f"{method_log_prefix}|BEFORE|R1: {r1}, R2: {repr(o.datatype)}".replace('%', '%%')
                        log.debug(msg)
                        r2 = self.__get_data_type_http(o.datatype)
                        msg = f"{method_log_prefix}|AFTER|R1: {r1}, R2: { repr(r2)}".replace('%', '%%')
                        log.debug(msg)
                    else:
                        r1 = str(o)
                        r2 = None
                else:
                    raise RDFProfileException(HarvesterConstants.UNEXPECTED_MULTIPLE_OBJECTS)
        msg = f"{method_log_prefix}|FINAL|R1: {r1}, R2: {r2}".replace('%', '%%')
        log.debug(msg)
        return r1, r2

    @log_debug
    def _validate_iso8601_date(self, datevalue, datetype):
        '''
        Returns the date with 'YYY-MM-DDTHH:mm:ssTZD' ISO 8601 format

        Note that partial dates will be expanded to the first month / day
        value, eg '1904' -> '1904-01-01'.

        Returns a string with the date value Europe/Madrid timezone,
        or None if datevalue is None. If datetype is None, XSD.dateTime is considered
        Raise RDFParserException if the datevalue format is not as expected
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        result = None
        errormsg = None
        if (datevalue):
            try:
                if (not datetype):
                    datetype = XSD.dateTime
                if (datetype not in [XSD.date, XSD.dateTime]):
                    errormsg = HarvesterConstants.UNEXPECTED_DATE_DATATYPE.format(
                        datetype, datevalue)
                else:
                    default_timezone = pytz.timezone(ConfigConstants.DEFAULT_TIMEZONE)
                    datetimevalue = iso8601.parse_date(
                        datevalue, default_timezone)
                    if datetype == XSD.date:
                        isoformatvalue = datetimevalue.isoformat()
                        result = datetimevalue.strftime("%Y-%m-%d")
                    elif datetype == XSD.dateTime:
                        utc1 = datetimevalue.astimezone(default_timezone)
                        isoformatvalue = utc1.isoformat()
                        result = utc1.strftime("%Y-%m-%dT%H:%M:%S")
            except iso8601.ParseError as e:
                errormsg = HarvesterConstants.UNEXPECTED_DATE_FORMAT.format(datevalue)
                log.error(f"Exception {type(e)}: {str(e)}" , exc_info=True)
                raise RDFProfileException(errormsg)
            except ValueError as e:
                errormsg = HarvesterConstants.UNEXPECTED_DATE_VALUE.format(datevalue, str(e))
                log.error(f"Exception {type(e)}: {str(e)}" , exc_info=True)
                raise RDFProfileException(errormsg)
            if errormsg is not None:
                raise RDFProfileException(errormsg)
        return result

    def _object_value_datatype_list(self, subject, predicate):
        '''
        Given a subject and a predicate, returns a list with all the values of
        the objects

        Both subject and predicate must be rdflib URIRef or BNode  objects

        If no values found, returns an empty string
        '''
        return [str(o) for o in self.g.objects(subject, predicate)]

    def _check_duplicate_catalog_uri(self, catalog_ref):
        errors = []
        if (catalog_ref, DCAT.dataset, catalog_ref) in self.g:
            errors.append(HarvesterConstants.CATALOG_SAME_ABOUT_DATASET.format(catalog_ref))

        if (catalog_ref, DCAT.distribution, catalog_ref) in self.g:
            errors.append(HarvesterConstants.CATALOG_SAME_ABOUT_DISTRIBUTION.format(catalog_ref))
        return errors

    def _from_iso_6391_to_language_DCAT_AP(self, value):
        result = None
        value_edp = None
        if value:
            if value == 'es':
                value_edp = 'SPA'
            elif value == 'en':
                value_edp = 'ENG'
            elif value == 'eu':
                value_edp = 'EUS'
            elif value == 'ca':
                value_edp = 'CAT'
            elif value == 'gl':
                value_edp = 'GLG'
            if value_edp:
                result = PrefixConstants.LANGUAGE_PREFIX_EDP + value_edp
        return result

    def _distribution_format(self, distribution, normalize_ckan_format=True):
        '''
        Returns the Internet Media Type and format label for a distribution

        Given a reference (URIRef or BNode) to a dcat:Distribution, it will
        try to extract the media type (previously knowm as MIME type), eg
        `text/csv`, and the format label, eg `CSV`

        Values for the media type will be checked in the following order:

        1. literal value of dcat:mediaType
        2. literal value of dct:format if it contains a '/' character
        3. value of dct:format if it is an instance of dct:IMT, eg:

            <dct:format>
                <dct:IMT rdf:value="text/html" rdfs:label="HTML"/>
            </dct:format>
        4. value of dct:format if it is an URIRef and appears to be an IANA type

        Values for the label will be checked in the following order:

        1. literal value of dct:format if it not contains a '/' character
        2. label of dct:format if it is an instance of dct:IMT (see above)
        3. value of dct:format if it is an URIRef and doesn't look like an IANA type

        If `normalize_ckan_format` is True the label will
        be tried to match against the standard list of formats that is included
        with CKAN core
        (https://github.com/ckan/ckan/blob/master/ckan/config/resource_formats.json)
        This allows for instance to populate the CKAN resource format field
        with a format that view plugins, etc will understand (`csv`, `xml`,
        etc.)

        Return a tuple with the media type and the label, both set to None if
        they couldn't be found.
        '''

        imt = None
        label = None

        imt = self._object_value(distribution, DCAT.mediaType)

        _format = self._object(distribution, DCT['format'])
        if isinstance(_format, Literal):
            if not imt and '/' in _format:
                imt = str(_format)
            else:
                label = str(_format)
        elif isinstance(_format, (BNode, URIRef)):
            if self._object(_format, RDF.type) == DCT.IMT:
                if not imt:
                    imt = str(self.g.value(_format, default=None))
                label = str(self.g.value(_format, RDFS.label, default=None, any=True))
            elif isinstance(_format, URIRef):
                # If the URIRef does not reference a BNode, it could reference an IANA type.
                # Otherwise, use it as label.
                format_uri = str(_format)
                if 'iana.org/assignments/media-types' in format_uri and not imt:
                    imt = format_uri
                else:
                    label = format_uri

        if ((imt or label) and normalize_ckan_format):
            format_registry = helpers.resource_formats()

            if imt in format_registry:
                label = format_registry[imt][1]
            elif label in format_registry:
                label = format_registry[label][1]

        return imt, label

    def _check_empty_field(self, value, field_name, is_catalog=False, required=False, multiple=False, prefix_msg=None):
        '''
        Returns True if value is None or empty, False in other case.
        Moreover, add an error or warning message when value is None or empty
        '''
        empty = False
        value = self._strip_value(value)
        if required:
            if value is None:
                empty = True
                if multiple:
                    self._add_errormsg(NTIHarvesterConstants.REQUIRED_MULTIPLE_FIELD_NOT_FOUND.format(field_name), is_catalog, prefix_msg)
                else:
                    self._add_errormsg(NTIHarvesterConstants.REQUIRED_FIELD_NOT_FOUND.format(field_name), is_catalog, prefix_msg)
            elif not value:
                empty = True
                self._add_errormsg(NTIHarvesterConstants.UNEXPECTED_EMPTY_VALUE.format(field_name), is_catalog, prefix_msg)
        else:
            if value is None:
                empty = True
            if value is not None and not value:
                empty = True
                self._add_warningmsg(NTIHarvesterConstants.OPTIONAL_EMPTY_VALUE.format(field_name), is_catalog, prefix_msg)
        return empty

    @log_debug
    def _get_multilingual_tags(self, dataset_ref, metadata, locales_offered, default_locale, is_dcatapes):
        multilingual_tags = {}
        wrong_languages = []
        wrong_names = []
        keywords = self._object_value_list(
            dataset_ref, metadata, unicode_value=False)
        keywords = [{
            'name': self._strip_value(o.value),
            'lang': o.language.lower() if o.language else default_locale
        } for o in keywords]
        # Split keywords with commas and semicolon
        for separator_character in [',', ';']:
            keywords_separator = [
                k for k in keywords if separator_character in (k['name'] or '')]
            for keyword in keywords_separator:
                keywords.remove(keyword)
                keywords.extend([
                    {'name': self._strip_value(
                        k), 'lang': keyword['lang']}
                    for k in keyword['name'].split(separator_character)])
        keywords = [o for o in keywords if o['name'] is not None]
        if keywords:
            sorted_keywords = sorted(
                keywords, key=lambda d: d['name'])

            for keyword in sorted_keywords:
                name = keyword['name']
                if not self._check_empty_field(name, NTIDatasetConstants.METADATA_DATASET_KEYWORD, False, False, False):
                    if not tagname_match.match(name):
                        wrong_names.append(name)
                    else:
                        lang = keyword['lang']
                        if lang is None:
                            lang = default_locale
                        if lang not in locales_offered:
                            if lang not in wrong_languages:
                                wrong_languages.append(lang)
                        else:
                            if lang not in multilingual_tags:
                                multilingual_tags[lang] = []
                            multilingual_tags[lang].append(name)
        return multilingual_tags, wrong_languages, wrong_names