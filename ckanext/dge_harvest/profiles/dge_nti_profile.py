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

import traceback as tb
import re
import traceback
import sys
import json
import iso8601
import pytz

import ckantoolkit as toolkit
from ckantoolkit import config

from rdflib import term, URIRef, BNode, Literal
from rdflib.namespace import Namespace, RDF, XSD, SKOS, RDFS, DC
from _elementtree import ParseError
from isodate import isoduration, ISO8601Error, Duration
from datetime import timedelta

from ckanext.dcat.profiles import DCT, DCAT, ADMS, VCARD, FOAF, SCHEMA, LOCN, GSP, OWL
from ckanext.dcat.exceptions import RDFParserException

from ..constants.constants import ConfigConstants, CommonPackageConstants
from ..constants.nti_constants import NTIPrefixConstants, NTICatalogConstants, NTIDatasetConstants, NTIHarvesterConstants
from .. import helpers as dhh
from .base_profile import DGEProfile
from .base_profile_parse_utils_base import BaseProfileParseUtilsBase


log = logging.getLogger(__name__)

ENCODING = sys.getdefaultencoding()
TIME = Namespace('http://www.w3.org/2006/time#')
XSD = Namespace('http://www.w3.org/2001/XMLSchema#')

namespaces = {
    'dct': DCT,
    'dcat': DCAT,
    'adms': ADMS,
    'vcard': VCARD,
    'foaf': FOAF,
    'schema': SCHEMA,
    'time': TIME,
    'skos': SKOS,
    'locn': LOCN,
    'gsp': GSP,
    'owl': OWL,
    'xsd': XSD
}

european_format = {
    'atom': 'Atom',
    'csv': 'CSV',
    'dbf': 'DBF',
    'doc': 'DOC',
    'docx': 'DOCX',
    'ecw': 'ECW',
    'ePub': 'ePub',
    'gdb': 'GDB',
    'geoJSON': 'GeoJSON',
    'geoPDF': 'GeoPDF',
    'geoRSS': 'GeoRSS',
    'gml': 'GML',
    'gzip': 'GZIP',
    'html': 'HTML',
    'jpg': 'JPG',
    'json': 'JSON',
    'json-ld': 'JSON-LD',
    'kml': 'KML',
    'kmz': 'KMZ',
    'las': 'LAS',
    'mdb': 'MDB',
    'n3': 'N3',
    'netCDF,': 'NetCDF',
    'OCTET-STREAM': 'OCTET-STREAM',
    'ods': 'ODS',
    'odt': 'ODT',
    'pdf': 'PDF',
    'plain': 'plain',
    'png': 'PNG',
    'ppt': 'PPT',
    'rdf-n3': 'RDF-N3',
    'rdf-Turtle': 'RDF-Turtle',
    'rdf-xml': 'RDF-XML',
    'rss': 'RSS',
    'rtf': 'RTF',
    'shp': 'SHP',
    'sparql': 'SPARQL',
    'sparql-json': 'SPARQL-JSON',
    'sparql-xml': 'SPARQL-XML',
    'tiff': 'TIFF',
    'tmx': 'TMX',
    'tsv': 'TSV',
    'turtle': 'TURTLE',
    'vcard-texto': 'vCard-texto',
    'wfs': 'WFS',
    'wms': 'WMS',
    'xhtml': 'XHTML',
    'xls': 'XLS',
    'xlsx': 'XLSX',
    'xml': 'XML',
    'xml-app': 'XML-APP',
    'zip': 'ZIP',
    '7zip': '7ZIP'
}

iana_format = {
    'calendar': 'Calendar',
    'djvu': 'DjVu',
    'dwg': 'DWG',
    'mp4': 'MP4',
    'pgp': 'PGP',
    'postscript': 'Postscript',
    'raster': 'RASTER',
    'smil': 'SMIL',
    'soap': 'SOAP',
    'svg': 'SVG',
    'visio': 'Visio',
    'voiceXML': 'VoiceXML'
}

class DGENTIProfile(DGEProfile):
    '''
    An RDF profile based on the NTI for data portals in Spain

    More information and specification:

    https://joinup.ec.europa.eu/asset/dcat_application_profile

    '''
    catalog_errors = []
    dataset_errors = []
    catalog_warnings = []
    dataset_warnings = []

    def _initialize_parse_utils(self):
        if self.base_parse_utils == None:
            self.base_parse_utils = BaseProfileParseUtilsBase(self.g)
    
    def _add_warningmsg(self, warningmsg=None, isCatalog=False, prefix=None):
        '''
        If warningmsg... add the given warning message to catalog_warning list
        if isCatalog is True, or to dataset_wargning list in other case
        '''
        method_log_prefix = f'[{type(self).__name__}][_add_warningmsg]'
        if warningmsg is not None and warningmsg:
            if prefix and len(prefix) > 0:
                warningmsg = f"[{prefix}]{warningmsg}"
            if isCatalog and warningmsg not in self.catalog_warnings:
                self.catalog_warnings.append(warningmsg)
                log.info(f"{method_log_prefix} Adding catalog_warning... {warningmsg}")
            elif not isCatalog and warningmsg not in self.dataset_warnings:
                self.dataset_warnings.append(warningmsg)
                log.info(f"{method_log_prefix} Adding dataset_warning... {warningmsg}")

    def _add_errormsg(self, errormsg=None, isCatalog=False, prefix=None):
        '''
        If errosmsg... add the given error message to catalog_errors list
        if isCatalog is True, or to dataset_errors in other case
        '''
        method_log_prefix = f'[{type(self).__name__}][_add_errormsg]'
        if errormsg is not None and errormsg:
            if prefix and len(prefix) > 0:
                errormsg = f"[{prefix}]{errormsg}"
            if isCatalog and errormsg not in self.catalog_errors:
                self.catalog_errors.append(errormsg)
                log.info(f"{method_log_prefix} Adding catalog_error... {errormsg}")
            elif not isCatalog and errormsg not in self.dataset_errors:
                self.dataset_errors.append(errormsg)
                log.info(f"{method_log_prefix} Adding dataset_error... {errormsg}")

    def _time_interval_coverage(self, interval):
        '''
        Returns the start and end date for a time interval object

        Both subject and predicate must be rdflib URIRef or BNode objects

        It checks for time intervals defined with both schema.org startDate &
        endDate and W3C Time hasBeginning & hasEnd or period of time defined
        with http://purl.org/dc/terms/PeriodOfTime.

        Note that partial dates will be expanded to the first month / day
        value, eg '1904' -> '1904-01-01'.

        Returns a tuple with the start and end date values, both of which
        can be None if not found. Raise RDFParserException if the definition
        format is not as expected
        '''
        method_log_prefix = f'[{type(self).__name__}][_time_interval_coverage]'
        log.debug(f"{method_log_prefix} Init method. Input: interval={interval}")
        start_date = end_date = None
        start_date_type = end_date_type = None
        final_start_date = final_end_date = None
        valid_data_types = [XSD.date, XSD.dateTime]
        errormsgs = []

        try:
            if interval:
                isInterval = (interval, RDF.type, TIME.Interval) in self.g
                isPeriodOfTime = (interval, RDF.type,
                                  DCT.PeriodOfTime) in self.g

                '''Fist try the schema.org way
                <dct:temporal>
                    <dct:PeriodOfTime>
                        <shema:startDate rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">@@FechaHoraInicio@@</schema:startDate>
                        <shema:endDate rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">@@FechaHoraFin@@</schema:endDate>
                    </dct:PeriodOfTime>
                </dct:temporal>
                '''
                if (isPeriodOfTime):
                    try:
                        start_date, start_date_type = self._object_value_datatype(
                            interval, SCHEMA.startDate)
                    except RDFParserException as e:
                        errormsgs.append(
                            NTIHarvesterConstants.UNEXPECTED_MULTIPLE_SUBOBJECTS.format(SCHEMA.startDate))
                    try:
                        end_date, end_date_type = self._object_value_datatype(
                            interval, SCHEMA.endDate)
                    except RDFParserException as e:
                        errormsgs.append(
                            NTIHarvesterConstants.UNEXPECTED_MULTIPLE_SUBOBJECTS.format(SCHEMA.endDate))

                ''' If no luck, try the w3 time way
                <dct:temporal>
                    <time:Interval>
                        <rdf:type rdf:resource="http://purl.org/dc/terms/PeriodOfTime" />
                        <time:hasBeginning>
                            <time:Instant>
                                <time:inXSDDateTime rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">@@FechaHoraInicio@@</time:inXSDDateTime>
                            </time:Instant>
                        </time:hasBeginning>
                        <time:hasEnd>
                            <time:Instant>
                                <time:inXSDDateTime rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">@@FechaHoraFin@@</time:inXSDDateTime>
                            </time:Instant>
                        </time:hasEnd>
                    </time:Interval>
                </dct:temporal>
                '''
                if isPeriodOfTime and isInterval:
                    start_nodes = [t for t in self.g.objects(
                        interval, TIME.hasBeginning)]
                    end_nodes = [t for t in self.g.objects(
                        interval, TIME.hasEnd)]
                    if start_nodes and len(start_nodes) > 1:
                        errormsgs.append(
                            NTIHarvesterConstants.UNEXPECTED_MULTIPLE_SUBOBJECTS.format(TIME.hasBeginning))
                    elif start_nodes and len(start_nodes) == 1 and (start_nodes[0], RDF.type, TIME.Instant) in self.g:
                        try:
                            start_date, start_date_type = self._object_value_datatype(start_nodes[0],
                                                                                      TIME.inXSDDateTime)
                        except:
                            errormsgs.append(
                                NTIHarvesterConstants.UNEXPECTED_MULTIPLE_SUBOBJECTS.format((TIME.hasBeginning + "-" + TIME.inXSDDateTime)))
                    if end_nodes and len(end_nodes) > 1:
                        errormsgs.append(
                            NTIHarvesterConstants.UNEXPECTED_MULTIPLE_SUBOBJECTS.format(TIME.hasEnd))
                    elif end_nodes and (end_nodes[0], RDF.type, TIME.Instant) in self.g:
                        try:
                            end_date, end_date_type = self._object_value_datatype(
                                end_nodes[0], TIME.inXSDDateTime)
                        except:
                            errormsgs.append(
                                NTIHarvesterConstants.UNEXPECTED_MULTIPLE_SUBOBJECTS.format((TIME.hasEnd + "-" + TIME.inXSDDateTime)))

                ''' If no luck...
                <dct:temporal>
                    <dct:PeriodOfTime>
                        <rdf:value rdf:datatype="http://www.w3.org/2001/XMLSchema#string">@@FechaHoraInicio@@/@@FechaHoraFin@@</rdf:value>
                    </dct:PeriodOfTime>
                </dct:temporal>
                '''
                if isPeriodOfTime:
                    try:
                        period_value, period_type = self._object_value_datatype(
                            interval, RDF.value)
                        if (period_value and period_type == XSD.string):
                            nodes = period_value.split('/')
                            if (nodes and len(nodes) >= 1 and len(nodes) <= 2):
                                if (len(nodes) >= 1):
                                    start_date = nodes[0]
                                if (len(nodes) == 2):
                                    end_date = nodes[1]
                    except:
                        errormsgs.append(
                            NTIHarvesterConstants.UNEXPECTED_MULTIPLE_SUBOBJECTS.format(RDF.value))

                if len(errormsgs) == 0:
                    if start_date or end_date:
                        if start_date and start_date_type and start_date_type not in valid_data_types:
                            errormsgs.append(
                                NTIHarvesterConstants.UNEXPECTED_DATE_DATATYPE.format(start_date_type, start_date, valid_data_types))
                        else:
                            try:
                                start_date = self._validate_iso8601_date(
                                    start_date, start_date_type)
                            except RDFParserException as e:
                                errormsgs.append(str(e))
                        if end_date and end_date_type and end_date_type not in valid_data_types:
                            errormsgs.append(NTIHarvesterConstants.UNEXPECTED_DATE_DATATYPE.format(
                                end_date_type, end_date))
                        else:
                            try:
                                end_date = self._validate_iso8601_date(
                                    end_date, end_date_type)
                            except RDFParserException as e:
                                errormsgs.append(str(e))
                    else:
                        errormsgs.append(NTIHarvesterConstants.UNEXPECTED_DEFINITION)
        except:
            errormsgs.append(NTIHarvesterConstants.UNEXPECTED_DEFINITION)
            log.debug(traceback.format_exc())
        if len(errormsgs) > 0:
            raise RDFParserException(", ".join(errormsgs))
        log.debug(f"{method_log_prefix} End method. Returns start_date={start_date}, end_date={end_date}")
        return start_date, end_date

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
                    errormsg = NTIHarvesterConstants.UNEXPECTED_MULTIPLE_OBJECTS
                    raise RDFParserException(errormsg)
        return result

    def _object_value_int(self, subject, predicate):
        '''
        Given a subject and a predicate, returns the value of the object as an
        integer. Decimal values are not rounded.

        Both subject and predicate must be rdflib URIRef or BNode objects

        If the value can not be parsed as integer, returns None
        '''
        object_value = self._strip_value(
            self._object_value(subject, predicate))
        if object_value:
            try:
                return int(float(object_value))
            except ValueError as e:
                raise RDFParserException(
                    NTIHarvesterConstants.UNEXPECTED_INTEGER_VALUE.format(object_value))
        return None

    def _get_languages(self, data_ref):
        '''
            Returns valid and wrong languages found in the data_ref

            Give a data_ref, searches predicates DC.language and DCT.language.
            Create a list of valid values (values that matches with a language
            in ckan.locales_offered configuration property) and other list of
            wrong values (not in ckan.locales_offered)

            Returns two lists:
             - list of valid languages or [].
             - list of wrong languages or []
        '''
        method_log_prefix = f'[{type(self).__name__}][_get_languages]'
        log.debug(f"{method_log_prefix} Init method. Input: data_ref={data_ref}")
        languages = []
        wrong_languages = []
        if data_ref:
            dc_languages = self._object_value_list(data_ref, DC.language)
            dct_languages = self._object_value_list(data_ref, DCT.language)
            languages = []
            locales_offered = self._get_ckan_locales_offered()
            if dc_languages is not None and len(dc_languages) > 0:
                for language in dc_languages:
                    language = self._strip_value(language)
                    if language not in locales_offered:
                        wrong_languages.append(language)
                    elif language not in languages:
                        languages.append(language)

            if dct_languages is not None and len(dct_languages) > 0:
                for language in dct_languages:
                    language = self._strip_value(language)
                    if language not in locales_offered:
                        wrong_languages.append(language)
                    elif language not in languages:
                        languages.append(language)
        log.debug(f"{method_log_prefix} End method. Returns languages={languages}, wrong_languages={wrong_languages}")
        return languages, wrong_languages

    def _get_field_translates(self, catalog_languages, subject, predicate, required, field_name, isCatalog,
                              prefix_msg=None):
        '''
        Returns a dictionary with translates of the objects found
        from given the subject and predicate

        Given a subject, predicate and catalog_languages,
        search their objects in the graph and
        get the translates of this objects in the catalog_languages

        Returns a dictionary with translates;
        None if required is false and no object is found;
        RDFParserException if required is true and all translates
        do not found
        '''
        method_log_prefix = f'[{type(self).__name__}][_get_field_translates]'
        log.debug(
            f"{method_log_prefix} Init method. Inputs: catalog_languages={catalog_languages}, subject={subject}, predicate={predicate}, required={required}, field_name={field_name}, isCatalog={isCatalog}, prefix_msg={prefix_msg if prefix_msg else ''}")
        if (field_name is None):
            field_name = predicate
        result = None
        wrong_definition = False
        field_in_default_language = False
        default_language = self._get_ckan_default_locale()
        if catalog_languages is None or len(catalog_languages) == 0:
            self._add_warningmsg(NTICatalogConstants.METADATA_CATALOG_NO_LANGUAGES, prefix_msg)
        elif subject is not None and predicate is not None:
            objects = self.g.objects(subject, predicate)
            if objects is None:
                if required:
                    self._add_errormsg(NTIHarvesterConstants.REQUIRED_FIELD_NOT_FOUND.format(field_name), isCatalog, prefix_msg)
            else:
                translates = {}  # objects with language
                no_translate = None  # object without language
                no_translate_number = 0
                languages = []  # languages found
                unexpected_languages = []
                multiples_same_language = []
                multiples_no_language = False
                empty_value_for_languages = []
                empty_value_no_languages = False
                total = 0
                num_objects = 0
                for object in objects:
                    num_objects += 1
                    if object and isinstance(object, Literal):
                        value = self._strip_value(str(object))
                        if not self._check_empty_field(value, field_name, isCatalog, True, False):
                            if hasattr(object, 'language') and object.language:
                                if object.language in catalog_languages:
                                    if object.language not in translates:
                                        translates[object.language] = value
                                        total += 1
                                        if object.language == default_language:
                                            field_in_default_language = True
                                        languages.append(object.language)
                                    else:
                                        if (object.language not in multiples_same_language):
                                            multiples_same_language.append(
                                                object.language)
                                else:
                                    if (object.language not in unexpected_languages):
                                        unexpected_languages.append(
                                            object.language)
                            else:
                                no_translate_number += 1
                                if no_translate is None:
                                    no_translate = value
                                    total += 1
                                else:
                                    multiples_no_language = True
                        else:
                            if hasattr(object, 'language') and object.language:
                                if (object.language not in empty_value_for_languages):
                                    empty_value_for_languages.append(
                                        object.language)
                            else:
                                empty_value_no_languages = True
                    else:
                        self._add_errormsg(NTIHarvesterConstants.REQUIRED_LITERAL_OBJECTS.format(
                            field_name), isCatalog, prefix_msg)
                        wrong_definition = True
                        break
                if num_objects == 0 and required:
                    self._add_errormsg(NTIHarvesterConstants.REQUIRED_FIELD_NOT_FOUND.format(
                        field_name), isCatalog, prefix_msg)
                    return None
                if wrong_definition:
                    return None
                warn_msgs = []
                error_msgs = []
                # Warnings for empty values
                if len(empty_value_for_languages) > 0:
                    warn_msgs.append(NTIHarvesterConstants.EMPTY_VALUE_IN_LANGUAGE.format(
                        field_name, ", ".join(empty_value_for_languages)))
                if empty_value_no_languages:
                    warn_msgs.append(
                        NTIHarvesterConstants.EMPTY_VALUE_NO_LANGUAGE.format(field_name))
                # Errors multiples values in the same language or no language
                if multiples_no_language:
                    error_msgs.append(
                        NTIHarvesterConstants.UNEXPECTED_MULTIPLES_VALUES_WITHOUT_LANGUAGE.format(field_name))
                if len(multiples_same_language) > 0:
                    error_msgs.append(
                        NTIHarvesterConstants.UNEXPECTED_MULTIPLES_VALUES_SAME_LANGUAGE.format(field_name, ",".join(multiples_same_language)))
                # Warnings for values in unexpected language
                if len(unexpected_languages) > 0:
                    warn_msgs.append(NTIHarvesterConstants.VALUE_IN_UNEXPECTED_LANGUAGE.format(
                        field_name, ",".join(unexpected_languages)))
                if total == 0:
                    # no allowed objects
                    if required and isCatalog:
                        error_msgs.append(
                            NTIHarvesterConstants.EXPECTED_IN_ALL_CATALOG_LANGUAGE.format(field_name))
                    elif required and not isCatalog:
                        error_msgs.append(NTIHarvesterConstants.EXPECTED_IN_DEFAULT_CATALOG_LANGUAGE.format(
                            field_name, default_language))
                else:
                    if len(catalog_languages) == len(translates):
                        result = translates
                    else:
                        languages_not_found = []
                        if not isCatalog:
                            for lang in catalog_languages:
                                if lang not in languages:
                                    languages_not_found.append(lang)
                            if len(languages_not_found) > 1 or \
                                    (len(languages_not_found) == 1 and languages_not_found[0] != default_language):
                                warn_msgs.append(NTIHarvesterConstants.VALUE_NOT_FOUND_IN_EXPECTED_LANGUAGE.format(
                                    field_name, ", ".join(languages_not_found)))

                        if len(catalog_languages) == 1:
                            if (no_translate is not None and no_translate_number == 1):
                                if result is None:
                                    result = {}
                                result[catalog_languages[0]] = no_translate
                            else:
                                if isCatalog:
                                    error_msgs.append(
                                        NTIHarvesterConstants.EXPECTED_IN_ALL_CATALOG_LANGUAGE.format(field_name))
                                elif not field_in_default_language:
                                    error_msgs.append(
                                        NTIHarvesterConstants.EXPECTED_IN_DEFAULT_CATALOG_LANGUAGE.format(field_name, default_language))
                        else:
                            if isCatalog:
                                error_msgs.append(
                                    NTIHarvesterConstants.EXPECTED_IN_ALL_CATALOG_LANGUAGE.format(field_name))
                            else:
                                if field_in_default_language:
                                    result = translates
                                else:
                                    error_msgs.append(
                                        NTIHarvesterConstants.EXPECTED_IN_DEFAULT_CATALOG_LANGUAGE.format(field_name, default_language))

                if len(warn_msgs) > 0:
                    message = "; ".join(warn_msgs)
                    self._add_warningmsg(message, isCatalog, prefix_msg)
                if len(error_msgs) > 0:
                    message = "; ".join(error_msgs)
                    self._add_errormsg(message, isCatalog, prefix_msg)
        log.debug(f"{method_log_prefix} End method. Returns {result}")
        return result

    def _get_dataset_title(self, translated_titles, default_catalog_language):
        '''
        Returns the ckan title

        Given the default_catalog_language and all translated titles,
        get de ckan title based on settings: ckan.locale_default,
        default_catalog_language and ckan.locale_order

        Returns the first translated title found in the following order:
        ckan.locale_default, default_catalog_language and ckan.locale_order
        '''
        method_log_prefix = f'[{type(self).__name__}][_get_dataset_title]'
        log.debug(f"{method_log_prefix} Init method. Inputs: translated_titles={translated_titles}, default_catalog_language={default_catalog_language if default_catalog_language else 'None'}")
        result = None
        if translated_titles is not None and len(translated_titles) == 1:
            values = list(translated_titles.values())
            result = values[0]
        elif translated_titles is not None and len(translated_titles) > 1:
            default_locale = self._get_ckan_default_locale()
            locale_order = config.get(ConfigConstants.CKAN_PROP_LOCALE_ORDER, None).split()
            if default_locale is not None and default_locale in translated_titles:
                result = translated_titles[default_locale]
            elif default_catalog_language is not None and default_catalog_language in translated_titles:
                result = translated_titles[default_catalog_language]
            elif locale_order is not None:
                for locale in locale_order:
                    if locale is not None and locale in translated_titles:
                        result = translated_titles[locale]
                        break
        log.debug(f"{method_log_prefix} End method. Returns {result}")
        return result

    def _check_theme_in_theme_taxonomy(self, theme=None, theme_taxonomy_list=[]):
        '''
        Given a theme and a list of theme taxonomies,
        return True if theme belongs to a taxonomy given
        '''
        if theme is not None and theme_taxonomy_list != []:
            for taxonomy in theme_taxonomy_list:
                if taxonomy:
                    if (theme.lower()).find(taxonomy.lower()) == 0:
                        return True
        return False

    def _get_publisher_id_minhap(self, publisher, fieldname, isCatalog):
        '''
        Returns idminhap of publisher url or add an error if idminhap nos exists
        '''
        idminhap = None
        upper_publisher = publisher.upper()
        if (upper_publisher.find(NTIPrefixConstants.PUBLISHER_PREFIX.upper()) == 0 and len(publisher) > len(NTIPrefixConstants.PUBLISHER_PREFIX)):
            idminhap = publisher[len(NTIPrefixConstants.PUBLISHER_PREFIX):]
        if not idminhap:
            self._add_errormsg(NTIHarvesterConstants.UNEXPECTED_VALUE.format(fieldname, publisher), isCatalog)
        return idminhap

    def parse_dataset(self, dataset_dict, dataset_ref):
        method_log_prefix = f'[{type(self).__name__}][parse_dataset]'
        if not dataset_dict:
            dataset_dict = {}
        self.dataset_errors = []
        self.dataset_warnings = []
        isCatalog = False
        actual_field = None
        dataset_license_tmp = ''
        self._initialize_parse_utils()
        

        try:
            log.debug(f'{method_log_prefix} Init method.')

            locales_offered = self._get_ckan_locales_offered()
            default_locale = self._get_ckan_default_locale()
            catalog_language = None
            default_catalog_language = None
            valid_dict_themes = {}
            valid_dict_spatials = {}
            valid_dict_formats = {}
            publisher_organizations = {}

            if NTICatalogConstants.KEY_CATALOG_LANGUAGE in dataset_dict and dataset_dict[NTICatalogConstants.KEY_CATALOG_LANGUAGE] is not None:
                catalog_language = dataset_dict[NTICatalogConstants.KEY_CATALOG_LANGUAGE]
            if NTIDatasetConstants.KEY_DATASET_DEFAULT_CATALOG_LANGUAGE in dataset_dict and dataset_dict[
                    NTIDatasetConstants.KEY_DATASET_DEFAULT_CATALOG_LANGUAGE] is not None:
                default_catalog_language = dataset_dict[NTIDatasetConstants.KEY_DATASET_DEFAULT_CATALOG_LANGUAGE]

            if (dataset_dict.get(NTICatalogConstants.KEY_CATALOG_AVAILABLE_DATA)):
                valid_dict_themes = dataset_dict.get(
                    NTICatalogConstants.KEY_CATALOG_AVAILABLE_DATA, {}).get(NTICatalogConstants.KEY_CATALOG_AVAILABLE_THEMES, {})
                valid_dict_spatials = dataset_dict.get(NTICatalogConstants.KEY_CATALOG_AVAILABLE_DATA, {}).get(
                    NTICatalogConstants.KEY_CATALOG_AVAILABLE_SPATIAL_COVERAGES, {})
                valid_dict_formats = dataset_dict.get(NTICatalogConstants.KEY_CATALOG_AVAILABLE_DATA, {}).get(
                    NTICatalogConstants.KEY_CATALOG_AVAILABLE_RESOURCE_FORMATS, {})
                publisher_organizations = dataset_dict.get(NTICatalogConstants.KEY_CATALOG_AVAILABLE_DATA, {}).get(NTICatalogConstants.KEY_CATALOG_AVAILABLE_PUBLISHERS,
                                                                                           {})
                del dataset_dict[NTICatalogConstants.KEY_CATALOG_AVAILABLE_DATA]

            log.debug(f'{method_log_prefix} Inputs: dataset_dict={dataset_dict}, dataset_ref={dataset_ref}')
            dataset_dict[NTIDatasetConstants.KEY_EXTRAS] = []
            dataset_dict[CommonPackageConstants.KEY_EXTRAS].append({'key': CommonPackageConstants.KEY_EXTRAS_APPLICATION_PROFILE, 'value': CommonPackageConstants.KEY_EXTRAS_APPLICATION_PROFILE_NTI_VALUE})
            dataset_dict[CommonPackageConstants.KEY_EXTRAS].append({'key': CommonPackageConstants.KEY_EXTRAS_HVD, 'value': False})
            dataset_dict[NTIDatasetConstants.KEY_RESOURCES] = []
            dataset_dict[NTIDatasetConstants.KEY_TYPE] = CommonPackageConstants.KEY_TYPE_DATASET_VALUE
            dataset_dict[NTIDatasetConstants.KEY_ERRORS] = []
            dataset_dict[NTIDatasetConstants.KEY_WARNINGS] = []

            do_parsing = True
            # check leng dataset_ref
            if (dataset_ref and len(dataset_ref) > 0):
                # Dataset URI (explicitly show the missing ones)
                dataset_dict[NTIDatasetConstants.KEY_URI] = (str(dataset_ref)
                                            if isinstance(dataset_ref, term.URIRef)
                                            else None)
            else:
                do_parsing = False
                self._add_errormsg(NTIHarvesterConstants.DATASET_WRONG_DEFINITION, isCatalog)

            # check if distribution with the same dataset rdf:About
            if do_parsing and \
                    (dataset_ref, DCAT.distribution, dataset_ref) in self.g:
                do_parsing = False
                self._add_errormsg(
                    NTIHarvesterConstants.DATASET_SAME_ABOUT_DISTRIBUTION.format(dataset_ref), isCatalog)

            if do_parsing:

                log.debug(f"{method_log_prefix} Parsing dataset DCT.title...")
                actual_field = NTIDatasetConstants.METADATA_DATASET_TITLE
                dataset_dict[NTIDatasetConstants.KEY_TITLE] = ''
                translates = self._get_field_translates(catalog_language, dataset_ref, DCT.title, True, actual_field,
                                                        isCatalog)
                if translates:
                    dataset_dict[NTIDatasetConstants.KEY_DATASET_TITLE_TRANSLATED] = translates
                    title = self._get_dataset_title(
                        translates, default_catalog_language)
                    log.debug(f"{method_log_prefix} Title ckan={title}")
                    if title is None or len(title) == 0:
                        log.warning(NTIHarvesterConstants.UNEXPECTED_EMPTY_VALUE.format(NTIDatasetConstants.METADATA_DATASET_CKAN_TITLE))
                    else:
                        dataset_dict[NTIDatasetConstants.KEY_TITLE] = title
                log.debug(f"{method_log_prefix} Parsed dataset DCT.title...{dataset_dict.get(NTIDatasetConstants.KEY_DATASET_TITLE_TRANSLATED, 'None')}")
                log.debug(f"{method_log_prefix} Parsed dataset DCT.title(CKAN)...{dataset_dict.get(NTIDatasetConstants.KEY_TITLE, 'None')}")

                log.debug(f"{method_log_prefix} Parsing dataset DCT.description...")
                actual_field = NTIDatasetConstants.METADATA_DATASET_DESCRIPTION
                translates = self._get_field_translates(catalog_language, dataset_ref, DCT.description, True,
                                                        actual_field, isCatalog)
                if translates:
                    dataset_dict[NTIDatasetConstants.KEY_DATASET_DESCRIPTION] = translates
                log.debug(f"{method_log_prefix} Parsed dataset DCT.description...{dataset_dict.get(NTIDatasetConstants.KEY_DATASET_DESCRIPTION, 'None')}")

                log.debug(f"{method_log_prefix} Parsing dataset DCAT.theme...")
                actual_field = NTIDatasetConstants.METADATA_DATASET_THEME
                themes = self._object_value_list(dataset_ref, DCAT.theme)
                finalThemes = []
                warnThemes = []
                if themes:
                    expected_theme = False
                    # Remove duplicates
                    for theme in themes:
                        theme = self._strip_value(theme)
                        theme = theme.replace('https://', 'http://')
                        if not self._check_empty_field(theme, actual_field, isCatalog, True, False):
                            if dhh.dge_harvest_is_url(theme):
                                lower_theme = theme.lower()  # no case sensitive
                                if self._check_theme_in_theme_taxonomy(lower_theme,
                                                                       dataset_dict[NTICatalogConstants.KEY_CATALOG_THEME_TAXONOMY]):
                                    if lower_theme.find(NTIPrefixConstants.THEME_PREFIX_SLASH.lower()) == 0:
                                        expected_theme = True
                                        final_value = valid_dict_themes.get(
                                            lower_theme, None)
                                        if final_value:
                                            finalThemes.append(final_value)
                                            if theme != final_value:
                                                warnThemes.append(theme)
                                        else:
                                            self._add_errormsg(NTIHarvesterConstants.UNEXPECTED_VALUE.format(
                                                actual_field, theme), isCatalog)
                                else:
                                    self._add_errormsg(NTIHarvesterConstants.UNEXPECTED_THEME_TAXONOMY_NOT_IN_CALOG.format(
                                        actual_field, NTIPrefixConstants.THEME_PREFIX_SLASH), isCatalog)
                            else:
                                self._add_errormsg(NTIHarvesterConstants.WRONG_URL.format(
                                    actual_field, theme), isCatalog)
                    if finalThemes and len(finalThemes) > 0:
                        dataset_dict[NTIDatasetConstants.KEY_DATASET_THEME] = finalThemes
                    if warnThemes and len(warnThemes) > 0:
                        self._add_warningmsg(NTIHarvesterConstants.VALUE_NO_CASE_SENSITIVE.format(actual_field, ", ".join(warnThemes)),
                                             isCatalog)
                    if not expected_theme:
                        self._add_errormsg(NTIHarvesterConstants.UNEXPECTED_THEME_VALUE.format(actual_field, NTIPrefixConstants.THEME_PREFIX_SLASH),
                                           isCatalog)
                else:
                    self._add_errormsg(NTIHarvesterConstants.REQUIRED_FIELD_NOT_FOUND.format(actual_field), isCatalog)
                log.debug(f"{method_log_prefix} Parsed dataset DCAT.theme...{dataset_dict.get(NTIDatasetConstants.KEY_DATASET_THEME, 'None')}")
                log.debug(f"{method_log_prefix} Parsing dataset DCAT.keyword...")
                metadata = DCAT.keyword
                if not self._are_literal_objects(dataset_ref, metadata):
                    self._add_errormsg(NTIHarvesterConstants.REQUIRED_LITERAL_OBJECTS.format(metadata), False)
                else:
                    multilingual_tags, wrong_languages, wrong_names = self._get_multilingual_tags(dataset_ref, metadata, locales_offered, default_locale, False)
                    if len(multilingual_tags) > 0:
                        dataset_dict[NTIDatasetConstants.KEY_DATASET_MULTILINGUAL_TAGS] = multilingual_tags
                    # Warnings for values in unexpected language
                    if len(wrong_languages) > 0:
                        self._add_warningmsg(NTIHarvesterConstants.VALUE_IN_UNEXPECTED_PORTAL_LANGUAGE.format(
                            metadata, ",".join(wrong_languages)))
                    if len(wrong_names) > 0:
                        for wrong_name in wrong_names:
                            self._add_warningmsg(
                                NTIHarvesterConstants.UNEXPECTED_KEYWORD_FORMAT.format(NTIDatasetConstants.METADATA_DATASET_KEYWORD, wrong_name), isCatalog)
                log.debug(f"{method_log_prefix} Parsed dataset DCAT.keywords...{dataset_dict.get(NTIDatasetConstants.KEY_DATASET_MULTILINGUAL_TAGS, 'None')}")

                log.debug(f"{method_log_prefix} Parsing dataset DCT.identifier...")
                actual_field = NTIDatasetConstants.METADATA_DATASET_IDENTIFIER
                dataset_dict[NTIDatasetConstants.KEY_DATASET_IDENTIFIER] = ''
                try:
                    dsIdentifier = self._strip_value(self._object_value(dataset_ref, DCT.identifier))
                    if not self._check_empty_field(dsIdentifier, actual_field, isCatalog, False, False):
                        if self._is_uri(dsIdentifier):
                            dataset_dict[NTIDatasetConstants.KEY_DATASET_IDENTIFIER] = dsIdentifier
                        else:
                            self._add_errormsg(NTIHarvesterConstants.WRONG_URI.format(actual_field, dsIdentifier), isCatalog)
                except RDFParserException as e:
                    self._add_errormsg(NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format(actual_field, str(e)), isCatalog)
                    log.debug(traceback.format_exc())
                log.debug(f"{method_log_prefix} Parsed dataset DCT.identifier...{dataset_dict.get(NTIDatasetConstants.KEY_DATASET_IDENTIFIER, 'None')}")

                # Creation date (dct:issued) - optional, single
                log.debug(f"{method_log_prefix} Parsing dataset DCT.issued...")
                actual_field = NTIDatasetConstants.METADATA_DATASET_ISSUED
                try:
                    cDate, cType = self._object_value_datatype(
                        dataset_ref, DCT.issued)
                    cDate = self._strip_value(cDate)
                    if not self._check_empty_field(cDate, actual_field, isCatalog, False, False):
                        dataset_dict[NTIDatasetConstants.KEY_DATASET_ISSUED_DATE] = self._validate_iso8601_date(
                            cDate, cType)
                except RDFParserException as e:
                    self._add_errormsg(NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format(actual_field, str(e)), isCatalog)
                    log.debug(traceback.format_exc())
                log.debug(f"{method_log_prefix} Parsed dataset DCT.issued...{dataset_dict.get(NTIDatasetConstants.KEY_DATASET_ISSUED_DATE, 'None')}")

                # Date of last update (dct:modified) - optional, single
                log.debug(f"{method_log_prefix} Parsing dataset DCT.modified...")
                actual_field = NTIDatasetConstants.METADATA_DATASET_MODIFIED
                try:
                    uDate, uType = self._object_value_datatype(
                        dataset_ref, DCT.modified)
                    uDate = self._strip_value(uDate)
                    if not self._check_empty_field(uDate, actual_field, isCatalog, False, False):
                        dataset_dict[NTIDatasetConstants.KEY_DATASET_MODIFIED_DATE] = self._validate_iso8601_date(
                            uDate, uType)
                except RDFParserException as e:
                    self._add_errormsg(NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format(actual_field, str(e)), isCatalog)
                    log.debug(traceback.format_exc())
                log.debug(f"{method_log_prefix} Parsed dataset DCT.modified...{dataset_dict.get(NTIDatasetConstants.KEY_DATASET_MODIFIED_DATE, 'None')}")

                log.debug(f"{method_log_prefix} Parsing dataset DCT.accrualPeriodicity...")
                actual_field = NTIDatasetConstants.METADATA_DATASET_ACCRUAL_PERIODICITY
                try:
                    f_type, f_value, f_uri = self.base_parse_utils._get_frequency(dataset_ref, DCT.accrualPeriodicity)
                    if (f_type and f_value is not None and f_uri is not None):
                        if (f_value >= 0):
                            dataset_dict[NTIDatasetConstants.KEY_DATASET_FREQUENCY] = json.dumps(
                                {'type': f_type, 'value': f_value, 'uri': f_uri})
                        else:
                            self._add_warningmsg(NTIHarvesterConstants.RECEIVED_VALUE.format(actual_field, f_value), isCatalog)
                except RDFParserException as e:
                    self._add_errormsg(NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format(actual_field, str(e)), isCatalog)
                    log.debug(traceback.format_exc())
                log.debug(f"{method_log_prefix} Parsed dataset DCT.accrualPeriodicity...{dataset_dict.get(NTIDatasetConstants.KEY_DATASET_FREQUENCY, 'None')}")

                log.debug(f"{method_log_prefix} Parsing dataset DC.language and DCT.language...")
                actual_field = NTIDatasetConstants.METADATA_DATASET_LANGUAGE
                languages, wrong_languages = self._get_languages(dataset_ref)
                langs = False
                wlangs = False
                if wrong_languages and len(wrong_languages) > 0:
                    wlangs = True
                if languages and len(languages) > 0:
                    langs = True
                if langs:
                    # In DCAT-AP-ES 1.0.0 dc:language need to be stored as an URI of the european vocabulary (http://publications.europa.eu/resource/authority/language/)
                    dcat_ap_languages = []
                    for language in languages:
                        dcat_ap_languages.append(self._from_iso_6391_to_language_DCAT_AP(language))
                    if dcat_ap_languages and len(dcat_ap_languages) > 0:
                        dataset_dict[NTIDatasetConstants.KEY_DATASET_LANGUAGE] = dcat_ap_languages
                    else:
                        self._add_warningmsg(NTIHarvesterConstants.NO_LANGUAGES.format(actual_field, locales_offered), isCatalog)
                    if wlangs:
                        self._add_warningmsg(
                            NTIHarvesterConstants.UNEXPECTED_LANGUAGES.format(actual_field, wrong_languages, locales_offered), isCatalog)
                else:
                    if wlangs:
                        self._add_warningmsg(
                            NTIHarvesterConstants.UNEXPECTED_LANGUAGES.format(actual_field, wrong_languages, locales_offered))
                    else:
                        self._add_warningmsg(NTIHarvesterConstants.NO_LANGUAGES.format(
                            actual_field, locales_offered), isCatalog)
                log.debug(f"{method_log_prefix} Parsed dataset DC.language and DCT.language...{dataset_dict.get(NTIDatasetConstants.KEY_DATASET_LANGUAGE, 'None')}")

                # Publisher (dct:publisher) - required, single
                log.debug(f"{method_log_prefix} Parsing dataset DCT.publisher...")
                actual_field = NTIDatasetConstants.METADATA_DATASET_PUBLISHER
                try:
                    publisher = self._strip_value(
                        self._object_value(dataset_ref, DCT.publisher))
                    publisher = publisher.replace('https://', 'http://')
                    if not self._check_empty_field(publisher, actual_field, isCatalog, True, False):
                        idminhap = self._get_publisher_id_minhap(
                            publisher, actual_field, isCatalog)
                        if idminhap:
                            dataset_dict[NTIDatasetConstants.KEY_PUBLISHER_ID_MINHAP] = idminhap
                            publisher_organization = publisher_organizations.get(
                                idminhap, [])
                            if publisher_organization and len(publisher_organization) == 2:
                                dataset_dict[NTIDatasetConstants.KEY_PUBLISHER] = publisher_organization[0]
                                dataset_dict[NTIDatasetConstants.KEY_PUBLISHER_NAME] = publisher_organization[1]
                            else:
                                self._add_errormsg(
                                    NTIHarvesterConstants.UNEXPECTED_PUBLISHER.format(
                                        actual_field, (NTIPrefixConstants.PUBLISHER_PREFIX + idminhap)),
                                    isCatalog)
                except RDFParserException as e:
                    self._add_errormsg(NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format(actual_field, str(e)), isCatalog)
                    log.debug(traceback.format_exc())
                log.debug(f"{method_log_prefix} Parsed dataset DCT.publisher...{dataset_dict.get(NTIDatasetConstants.KEY_PUBLISHER_ID_MINHAP, 'None')}")

                # License (dct:license) - required, single
                log.debug(f"{method_log_prefix} Parsing dataset DCT.license...")
                actual_field = NTIDatasetConstants.METADATA_DATASET_LICENSE
                try:
                    license = self._strip_value(
                        self._object_value(dataset_ref, DCT.license))
                    if not self._check_empty_field(license, actual_field, isCatalog, True, False):
                        if dhh.dge_harvest_is_url(license):
                            dataset_dict[NTIDatasetConstants.KEY_DATASET_LICENSE] = license
                        else:
                            self._add_errormsg(NTIHarvesterConstants.WRONG_URL.format(
                                actual_field, license), isCatalog)
                except RDFParserException as e:
                    self._add_errormsg(f"{actual_field}: {str(e)}", isCatalog)
                    log.debug(traceback.format_exc())
                log.debug(f"{method_log_prefix} Parsed dataset DCT.license...{dataset_dict.get(NTIDatasetConstants.KEY_DATASET_LICENSE, 'None')}")

                # Spatial coverage (dct:spatial) - optional, multiple
                log.debug(f"{method_log_prefix} Parsing dataset DCT.spatial...")
                actual_field = NTIDatasetConstants.METADATA_DATASET_SPATIAL
                spatials = self._object_value_list(dataset_ref, DCT.spatial)
                if (spatials):
                    spatialList = []
                    warnSpatials = []
                    num_expected_values = 0
                    for spatial in spatials:
                        spatial = self._strip_value(spatial)
                        spatial = spatial.replace('https://', 'http://')
                        if not self._check_empty_field(spatial, actual_field, isCatalog, False, False):
                            lower_spatial = spatial.lower()
                            if (lower_spatial.find(NTIPrefixConstants.SPATIAL_PREFIX.lower()) == 0):
                                final_value = valid_dict_spatials.get(
                                    lower_spatial, None)
                                if not final_value:
                                    self._add_errormsg(
                                        NTIHarvesterConstants.UNEXPECTED_VALUE.format(actual_field, spatial))
                                else:
                                    spatialList.append(final_value)
                                    if spatial != final_value:
                                        warnSpatials.append(spatial)
                                    if (lower_spatial.find(NTIPrefixConstants.SPATIAL_PROVINCE_PREFIX.lower()) == 0
                                            or spatial.find(NTIPrefixConstants.SPATIAL_CCAA_PREFIX.lower()) == 0):
                                        num_expected_values += 1
                    if spatialList and len(spatialList) > 0:
                        spatial_dict_list = [{'uri': spatial_value, 'geometry': '', 'bbox': '', 'centroid': ''} for spatial_value in spatialList]
                        dataset_dict[NTIDatasetConstants.KEY_DATASET_SPATIAL] = json.dumps(spatial_dict_list)
                    if warnSpatials and len(warnSpatials) > 0:
                        self._add_warningmsg(NTIHarvesterConstants.VALUE_NO_CASE_SENSITIVE.format(actual_field, ", ".join(warnSpatials)),
                                             isCatalog)
                log.debug(f"{method_log_prefix} Parsed dataset DCT.spatial...{dataset_dict.get(NTIDatasetConstants.KEY_DATASET_SPATIAL, 'None')}")

                # Temporal coverage - (dct:temporal) - optional, multiple
                log.debug(f"{method_log_prefix} Parsing dataset DCT.temporal...")
                actual_field = NTIDatasetConstants.METADATA_DATASET_TEMPORAL
                temporals = self._object_value_list(dataset_ref, DCT.temporal)
                index = 1
                try:
                    for temporal in self.g.objects(dataset_ref, DCT.temporal):
                        start, end = self._time_interval_coverage(temporal)
                        coverage = {}
                        if start or end:
                            if (NTIDatasetConstants.KEY_DATASET_TEMPORAL_COVERAGE in dataset_dict) == False:
                                dataset_dict[NTIDatasetConstants.KEY_DATASET_TEMPORAL_COVERAGE] = {}
                            if start:
                                coverage['from'] = start
                            if end:
                                coverage['to'] = end
                            dataset_dict[NTIDatasetConstants.KEY_DATASET_TEMPORAL_COVERAGE][index] = coverage
                            index += 1
                except RDFParserException as e:
                    self._add_errormsg(
                        NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format(actual_field, (str(e) if hasattr(e, 'message') else e)), isCatalog)
                log.debug(f"{method_log_prefix} Parsed dataset DCT.temporal...{dataset_dict.get(NTIDatasetConstants.KEY_DATASET_TEMPORAL_COVERAGE, 'None')}")

                # Validity of resource (dct:valid) - optional, single
                log.debug(f"{method_log_prefix} Parsing dataset DCT.valid...")
                actual_field = NTIDatasetConstants.METADATA_DATASET_VALID
                try:
                    vDate, vType = self._object_value_datatype(
                        dataset_ref, DCT.valid)
                    vDate = self._strip_value(vDate)
                    if not self._check_empty_field(vDate, actual_field, isCatalog, False, False):
                        dataset_dict[NTIDatasetConstants.KEY_DATASET_VALID] = self._validate_iso8601_date(
                            vDate, vType)
                except RDFParserException as e:
                    self._add_errormsg(NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format(actual_field, str(e)), isCatalog)
                log.debug(
                    f"{method_log_prefix} Parsed dataset DCT.valid...{dataset_dict.get(NTIDatasetConstants.KEY_DATASET_VALID, 'None')}")

                # References (dct:references) - optional, multiple
                log.debug(f"{method_log_prefix} Parsing dataset DCT.references...")
                actual_field = NTIDatasetConstants.METADATA_DATASET_REFERENCES
                references = self._object_value_list(
                    dataset_ref, DCT.references)
                if (references):
                    referenceList = []
                    for reference in references:
                        reference = self._strip_value(reference)
                        if not self._check_empty_field(reference, actual_field, isCatalog, False, False):
                            if dhh.dge_harvest_is_url(reference):
                                referenceList.append(reference)
                            else:
                                self._add_errormsg(NTIHarvesterConstants.WRONG_URL.format(
                                    actual_field, reference), isCatalog)
                    if referenceList and len(referenceList) > 0:
                        log.debug(
                            f'[multiple_url_encode] referenceList and len(referenceList) > 0 "{reference}"')
                        dataset_dict[NTIDatasetConstants.KEY_DATASET_REFERENCE] = referenceList
                log.debug(f"{method_log_prefix} Parsed dataset DCT.references...{dataset_dict.get(NTIDatasetConstants.KEY_DATASET_REFERENCE, 'None')}")

                # Normative (dct:conformsTo) - optional, multiple
                log.debug(f"{method_log_prefix} Parsing dataset DCT.conformsTo...")
                actual_field = NTIDatasetConstants.METADATA_DATASET_CONFORMS_TO
                conformsTos = self._object_value_list(dataset_ref, DCT.conformsTo)
                if (conformsTos):
                    conformsToList = []
                    for conformsTo in conformsTos:
                        conformsTo = self._strip_value(conformsTo)
                        if not self._check_empty_field(conformsTo, actual_field, isCatalog, False, False):
                            if dhh.dge_harvest_is_url(conformsTo):
                                conformsToList.append(conformsTo)
                            else:
                                self._add_errormsg(NTIHarvesterConstants.WRONG_URL.format(
                                    actual_field, conformsTo), isCatalog)
                    if conformsToList and len(conformsToList) > 0:
                        dataset_dict[NTIDatasetConstants.KEY_DATASET_NORMATIVE] = conformsToList
                log.debug(f"{method_log_prefix} Parsed dataset DCT.conformsTo...{dataset_dict.get(NTIDatasetConstants.KEY_DATASET_NORMATIVE, 'None')}")
                
                # Distributions/Resources (dct:distribution) - required, multiple
                log.debug(f"{method_log_prefix} Parsing dataset DCAT.distribution...")
                actual_field = NTIDatasetConstants.METADATA_DATASET_DISTRIBUTION
                numDistributions = 0
                for distribution in self._distributions(dataset_ref):
                    resource_dict = {}
                    if distribution:                        
                        # Identifier (dct:identifier) - optional, single
                        log.debug(f"{method_log_prefix} Parsing distribution DCT.identifier...")
                        actual_field = NTIDatasetConstants.METADATA_DISTRIBUTION_IDENTIFIER
                        prefix_msg = NTIDatasetConstants.METADATA_DISTRIBUTION_PREFIX_MESSAGE.format(
                            NTIDatasetConstants.METADATA_DISTRIBUTION_NO_IDENTIFIER)

                        resource_dict[NTIDatasetConstants.KEY_DATASET_RESOURCE_IDENTIFIER] = ''
                        try:
                            dIdentifier = self._strip_value(
                                self._object_value(distribution, DCT.identifier))
                            if not self._check_empty_field(dIdentifier, actual_field, isCatalog, False, False, prefix_msg):
                                prefix_msg = NTIDatasetConstants.METADATA_DISTRIBUTION_PREFIX_MESSAGE.format(
                                    dIdentifier)
                                if self._is_uri(dIdentifier):
                                    resource_dict[NTIDatasetConstants.KEY_DATASET_RESOURCE_IDENTIFIER] = dIdentifier
                                else:
                                    self._add_errormsg(NTIHarvesterConstants.WRONG_URI.format(actual_field, dIdentifier), isCatalog, prefix_msg)
                        except RDFParserException as e:
                            self._add_errormsg(NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format(actual_field, str(e)), isCatalog, prefix_msg)
                            log.debug(traceback.format_exc())
                        log.debug(f"{method_log_prefix} Parsed distribution DCT.identifier...{resource_dict.get(NTIDatasetConstants.KEY_DATASET_RESOURCE_IDENTIFIER, 'None')}")

                        # name (dct:title) - optional, multiple -- multilanguage
                        log.debug(f"{method_log_prefix} Parsing distribution DCT.title with langs...")
                        actual_field = NTIDatasetConstants.METADATA_DISTRIBUTION_TITLE
                        translates = self._get_field_translates(catalog_language, distribution, DCT.title, False,
                                                                actual_field, isCatalog, prefix_msg)
                        if translates is not None:
                            resource_dict[NTIDatasetConstants.KEY_DATASET_RESOURCE_NAME_TRANSLATED] = json.dumps(
                                translates)
                        log.debug(f"{method_log_prefix} Parsed distribution DCT.title...{resource_dict.get(NTIDatasetConstants.KEY_DATASET_RESOURCE_NAME_TRANSLATED, 'None')}")

                        # access url (dcat:accessURL) - required, single
                        log.debug(f"{method_log_prefix} Parsing distribution DCAT.accesURL...")
                        actual_field = NTIDatasetConstants.METADATA_DISTRIBUTION_ACCESS_URL
                        try:
                            durl = self._strip_value(
                                self._object_value(distribution, DCAT.accessURL))
                            if not self._check_empty_field(durl, actual_field, isCatalog, True, False, prefix_msg):
                                if dhh.dge_harvest_is_url(durl):
                                    resource_dict[NTIDatasetConstants.KEY_DATASET_RESOURCE_ACCESS_URL] = durl
                                    log.debug(f"{durl} Ascii code distribution DCAT.accesURL...")
                                else:
                                    self._add_errormsg(NTIHarvesterConstants.WRONG_URL.format(
                                        actual_field, durl), isCatalog, prefix_msg)
                        except RDFParserException as e:
                            self._add_errormsg(NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format(actual_field, str(e)), isCatalog,
                                               prefix_msg)
                            log.debug(traceback.format_exc())
                        log.debug(f"{method_log_prefix} Parsed distribution DCAT.accessURL...{resource_dict.get(NTIDatasetConstants.KEY_DATASET_RESOURCE_ACCESS_URL, 'None')}")

                        # distribution format (dcat:mediaType) - required, single
                        log.debug(f"{method_log_prefix} Parsing distribution DCAT.mediaType...")
                        actual_field = NTIDatasetConstants.METADATA_DISTRIBUTION_MEDIA_TYPE
                        normalize_ckan_format = config.get(
                            'ckanext.dcat.normalize_ckan_format', True)
                        imt, label = self._distribution_format(distribution,
                                                               normalize_ckan_format)
                        if imt and len(imt) > 0:
                            lower_imt = imt.lower()
                            final_value = valid_dict_formats.get(
                                lower_imt, None)
                            if final_value:
                                resource_dict[NTIDatasetConstants.KEY_DATASET_RESOURCE_MIMETYPE] = final_value
                                resource_dict[NTIDatasetConstants.KEY_DATASET_RESOURCE_FORMAT] = final_value
                                if imt != final_value:
                                    self._add_warningmsg(NTIHarvesterConstants.FORMAT_NO_CASE_SENSITIVE.format(actual_field, imt), isCatalog,
                                                         prefix_msg)
                            else:
                                self._add_errormsg(NTIHarvesterConstants.UNEXPECTED_VALUE.format(
                                    actual_field, imt), isCatalog, prefix_msg)
                        else:
                            self._add_errormsg(NTIHarvesterConstants.REQUIRED_FIELD_NOT_FOUND.format(
                                actual_field), isCatalog, prefix_msg)
                        log.debug(f"{method_log_prefix} Parsed distribution DCT.mediaType...{resource_dict.get(NTIDatasetConstants.KEY_DATASET_RESOURCE_FORMAT, 'None')}")

                        # distribution size (dcat:byteSize) - optional, single
                        log.debug(f"{method_log_prefix} Parsing distribution DCAT.byteSize...")
                        actual_field = NTIDatasetConstants.METADATA_DISTRIBUTION_BYTE_SIZE
                        try:
                            size = self._object_value_int(
                                distribution, DCAT.byteSize)
                            if size:
                                resource_dict[NTIDatasetConstants.KEY_DATASET_RESOURCE_BYTE_SIZE] = size
                        except RDFParserException as e:
                            self._add_errormsg(NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format(
                                actual_field, str(e), prefix_msg))
                            log.debug(traceback.format_exc())
                        log.debug(f"{method_log_prefix} Parsed distribution DCT.byteSize...{resource_dict.get(NTIDatasetConstants.KEY_DATASET_RESOURCE_BYTE_SIZE, 'None')}")

                        # relation (dct:relation) - optional, multiple
                        log.debug(f"{method_log_prefix} Parsing distribution DCT.relation...")
                        actual_field = NTIDatasetConstants.METADATA_DISTRIBUTION_RELATION
                        dRelations = self.g.objects(distribution, DCT.relation)
                        resource_relations = []
                        if (dRelations):
                            for dRelation in dRelations:
                                if (dRelation):
                                    try:
                                        if isinstance(dRelation, Literal):
                                            dRelationValue = self._strip_value(
                                                str(dRelation))
                                        else:
                                            dRelationValue = self._strip_value(
                                                self._object_value(dRelation, FOAF.page))
                                        if not self._check_empty_field(dRelationValue, actual_field, isCatalog, False,
                                                                       False, prefix_msg):
                                            if dhh.dge_harvest_is_url(dRelationValue):
                                                resource_relations.append(
                                                    dRelationValue)
                                            else:
                                                self._add_errormsg(NTIHarvesterConstants.WRONG_URL.format(actual_field, dRelationValue),
                                                                   isCatalog, prefix_msg)
                                    except RDFParserException as e:
                                        self._add_errormsg(NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format(actual_field, str(e)),
                                                           isCatalog, prefix_msg)
                                        log.debug(traceback.format_exc())
                        if len(resource_relations) > 0:
                            resource_dict[NTIDatasetConstants.KEY_DATASET_RESOURCE_RELATION] = resource_relations
                        dataset_dict[NTIDatasetConstants.KEY_RESOURCES].append(resource_dict)
                        log.debug(f"{method_log_prefix} Parsed distribution DCT.relation...{resource_dict.get(NTIDatasetConstants.KEY_DATASET_RESOURCE_RELATION, 'None')}")
                        numDistributions += 1
                actual_field = NTIDatasetConstants.METADATA_DATASET_DISTRIBUTIONS
                if numDistributions == 0:
                    self._add_errormsg(NTIHarvesterConstants.REQUIRED_FIELD_NOT_FOUND.format(actual_field), isCatalog)
                log.debug(
                    f"{method_log_prefix} Parsed dataset DCT....{dataset_dict.get(NTIDatasetConstants.KEY_RESOURCES, 'None')}")
                actual_field = None

        except Exception as e:
            if not actual_field:
                self._add_errormsg(NTIHarvesterConstants.UNEXPECTED_ERROR.format(type(e).__name__, e), isCatalog)
                log.debug(traceback.format_exc())
            else:
                self._add_errormsg(NTIHarvesterConstants.UNEXPECTED_FIELD_ERROR.format(
                    actual_field, type(e).__name__, e), isCatalog)
                log.debug(traceback.format_exc())

        dataset_dict[NTIDatasetConstants.KEY_ERRORS].extend(self.dataset_errors)
        dataset_dict[NTIDatasetConstants.KEY_WARNINGS].extend(self.dataset_warnings)
        return dataset_dict

    def parse_catalog(self, catalog_dict, catalog_ref):
        method_log_prefix = f'[{type(self).__name__}][parse_catalog]'
        log.debug(f'{method_log_prefix} Init method. Inputs: catalog_dict={catalog_dict}, catalog_ref={catalog_ref}')
        catalog_dict[NTICatalogConstants.KEY_CATALOG_LANGUAGE] = []
        catalog_dict[NTICatalogConstants.KEY_CATALOG_ERRORS] = []
        catalog_dict[NTICatalogConstants.KEY_CATALOG_WARNINGS] = []
        self.catalog_errors = []
        self.catalog_warnings = []
        self._initialize_parse_utils()

        isCatalog = True
        actual_field = None
        try:
            do_parsing = True
            if (do_parsing and catalog_ref and len(catalog_ref) > 0):
                # Catalog URI (explicitly show the missing ones)
                catalog_dict[NTICatalogConstants.KEY_CATALOG_URI] = (str(catalog_ref)
                                             if isinstance(catalog_ref, term.URIRef)
                                             else None)
            else:
                do_parsing = False
                self._add_errormsg(NTIHarvesterConstants.CATALOG_WRONG_DEFINITION, isCatalog)

            # check if dataset or distribution with the same catalog rdf:about
            if do_parsing:
                if (catalog_ref, DCAT.dataset, catalog_ref) in self.g:
                    do_parsing = False
                    self._add_errormsg(
                        NTIHarvesterConstants.CATALOG_SAME_ABOUT_DATASET.format(catalog_ref), isCatalog)

                if (catalog_ref, DCAT.distribution, catalog_ref) in self.g:
                    do_parsing = False
                    self._add_errormsg(
                        NTIHarvesterConstants.CATALOG_SAME_ABOUT_DISTRIBUTION.format(catalog_ref), isCatalog)
            
            if do_parsing:
                actual_field = NTIDatasetConstants.METADATA_DATASET_IDENTIFIER
                datasets_in_catalog = self._object_value_list(catalog_ref, DCAT.dataset)
                if datasets_in_catalog and len(datasets_in_catalog) > 0:
                    identifiers_in_datasets = self._get_identifiers_in_datasets(datasets_in_catalog)
                    if identifiers_in_datasets and len(identifiers_in_datasets) > 0:
                        duplicated_identifier = self._check_duplicated_identifiers(identifiers_in_datasets)
                        if duplicated_identifier:
                            self._add_warningmsg(NTIHarvesterConstants.DATASET_DUPLICATED_IDENTIFIER % (
                                actual_field, str(duplicated_identifier)), isCatalog)
            
            if do_parsing:
                # Get dict configuration
                cat_available_data = {}
                # Get valid themes
                cat_available_data[NTICatalogConstants.KEY_CATALOG_AVAILABLE_THEMES] = dhh.dge_harvest_list_theme_option_value()
                # Get valid spatial coverage
                cat_available_data[NTICatalogConstants.KEY_CATALOG_AVAILABLE_SPATIAL_COVERAGES] = dhh.dge_harvest_list_spatial_coverage_option_value()
                # Get valid resource formats
                cat_available_data[NTICatalogConstants.KEY_CATALOG_AVAILABLE_RESOURCE_FORMATS] = dhh._dge_harvest_list_format_option_value()
                # Get available organizations/publishers
                log.debug('estoy en parse_catalog')
                cat_available_data[NTICatalogConstants.KEY_CATALOG_AVAILABLE_PUBLISHERS] = dhh.dge_harvest_organizations_available()
                catalog_dict[NTICatalogConstants.KEY_CATALOG_AVAILABLE_DATA] = cat_available_data

                # dct:language - required, multiple
                log.debug(f"{method_log_prefix} Parsing catalog DC.language and DCT.language..." )
                actual_field = NTICatalogConstants.METADATA_CATALOG_LANGUAGE
                languages, wrong_languages = self._get_languages(catalog_ref)
                wlangs = (wrong_languages and len(wrong_languages) > 0)
                langs = (languages and len(languages) > 0)
                if langs:
                    if self.default_locale in languages:
                        catalog_dict[NTICatalogConstants.KEY_CATALOG_LANGUAGE] = languages
                    else:
                        self._add_errormsg(NTIHarvesterConstants.DEFAULT_LANGUAGE_NOT_FOUND.format(
                            actual_field, self.default_locale), isCatalog)
                    if wlangs:
                        self._add_warningmsg(
                            NTIHarvesterConstants.UNEXPECTED_LANGUAGES.format(actual_field, wrong_languages, self.locales_offered), isCatalog)
                else:
                    if wlangs:
                        self._add_errormsg(NTIHarvesterConstants.UNEXPECTED_LANGUAGES.format(actual_field, wrong_languages, self.locales_offered),
                                           isCatalog)
                    else:
                        self._add_errormsg(NTIHarvesterConstants.CATALOG_LANGUAGE_NOT_FOUND.format(
                            actual_field, self.locales_offered), isCatalog)
                log.debug(f"{method_log_prefix} Parsed catalog DC.language and DCT.language....{catalog_dict.get(NTICatalogConstants.KEY_CATALOG_LANGUAGE, 'None')}")

                # Name (dct:title) - required, multiple -- multilanguage
                if catalog_dict[NTICatalogConstants.KEY_CATALOG_LANGUAGE] is not None and len(catalog_dict[NTICatalogConstants.KEY_CATALOG_LANGUAGE]) > 0:
                    log.debug(f"{method_log_prefix} Parsing catalog DCT.title...")
                    actual_field = NTICatalogConstants.METADATA_CATALOG_TITLE
                    translates = self._get_field_translates(catalog_dict[NTICatalogConstants.KEY_CATALOG_LANGUAGE], catalog_ref, DCT.title,
                                                            True, NTICatalogConstants.METADATA_CATALOG_TITLE, isCatalog)
                    if translates:
                        catalog_dict[NTICatalogConstants.KEY_CATALOG_TITLE_TRANSLATE] = json.dumps(
                            translates)
                    log.debug(f"{method_log_prefix} Parsed catalog DCT.title_translated....{catalog_dict.get(NTICatalogConstants.KEY_CATALOG_TITLE_TRANSLATE, 'None')}")

                # Description (dct:description) - required, multiple -- multilanguage
                if catalog_dict[NTICatalogConstants.KEY_CATALOG_LANGUAGE] is not None and len(catalog_dict[NTICatalogConstants.KEY_CATALOG_LANGUAGE]) > 0:
                    log.debug(f"{method_log_prefix} Parsing catalog DCT.description...")
                    actual_field = NTICatalogConstants.METADATA_CATALOG_DESCRIPTION
                    translates = self._get_field_translates(catalog_dict[NTICatalogConstants.KEY_CATALOG_LANGUAGE], catalog_ref,
                                                            DCT.description, True, NTICatalogConstants.METADATA_CATALOG_DESCRIPTION, isCatalog)
                    if translates:
                        catalog_dict[NTICatalogConstants.KEY_CATALOG_DESCRIPTION] = json.dumps(
                            translates)
                    log.debug(f"{method_log_prefix} Parsed catalog DCT.description....{catalog_dict.get(NTICatalogConstants.KEY_CATALOG_DESCRIPTION, 'None')}")

                # Publisher (dct:publisher) - required, single
                log.debug(f"{method_log_prefix} Parsing catalog DCT.publisher...")
                actual_field = NTICatalogConstants.METADATA_CATALOG_PUBLISHER
                try:
                    publisher = self._strip_value(
                        self._object_value(catalog_ref, DCT.publisher))
                    publisher = publisher.replace('https://', 'http://')
                    if not self._check_empty_field(publisher, actual_field, isCatalog, True, False):
                        idminhap = self._get_publisher_id_minhap(
                            publisher, actual_field, isCatalog)
                        if idminhap:
                            catalog_dict[NTICatalogConstants.KEY_CATALOG_PUBLISHER_ID_MINHAP] = idminhap
                            publisher_organization = cat_available_data.get(NTICatalogConstants.KEY_CATALOG_AVAILABLE_PUBLISHERS, {}).get(
                                idminhap, [])
                            if publisher_organization and len(publisher_organization) == 2:
                                catalog_dict[NTICatalogConstants.KEY_CATALOG_PUBLISHER] = publisher_organization[0]
                                catalog_dict[NTICatalogConstants.KEY_CATALOG_PUBLISHER_NAME] = publisher_organization[1]
                            else:
                                self._add_errormsg(
                                    NTIHarvesterConstants.UNEXPECTED_PUBLISHER.format(actual_field, (NTIPrefixConstants.PUBLISHER_PREFIX + idminhap)),
                                    isCatalog)
                except RDFParserException as e:
                    self._add_errormsg(NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format(actual_field, str(e)))
                    log.debug(traceback.format_exc())
                log.debug(f"{method_log_prefix} Parsed catalog DCT.publisher....{catalog_dict.get(NTICatalogConstants.KEY_CATALOG_PUBLISHER_ID_MINHAP, 'None')}")

                log.debug(f"{method_log_prefix} Parsing catalog DCT.extent...")
                actual_field = NTICatalogConstants.METADATA_CATALOG_EXTENT
                try:
                    exists = False
                    for extent in self.g.objects(catalog_ref, DCT.extent):
                        if not exists:
                            if isinstance(extent, BNode) and \
                                    (extent, RDF.type, DCT.SizeOrDuration) in self.g:
                                size = self._object_value_int(
                                    extent, RDF.value)
                                if size:
                                    catalog_dict[NTICatalogConstants.KEY_CATALOG_SIZE] = size
                                exists = True
                        else:
                            self._add_errormsg(NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format(actual_field, NTIHarvesterConstants.UNEXPECTED_MULTIPLE_OBJECTS),
                                               isCatalog)
                except RDFParserException as e:
                    self._add_errormsg(NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format(actual_field, str(e)), isCatalog)
                    log.debug(traceback.format_exc())
                log.debug(
                    f"{method_log_prefix}  Parsed catalog DCT.extent....{catalog_dict.get(NTICatalogConstants.KEY_CATALOG_SIZE, 'None')}")

                log.debug(f"{method_log_prefix} Parsing catalog DCT.identifier...")
                actual_field = NTICatalogConstants.METADATA_CATALOG_IDENTIFIER
                try:
                    cIdentifier = self._strip_value(
                        self._object_value(catalog_ref, DCT.identifier))
                    if not self._check_empty_field(cIdentifier, actual_field, isCatalog, False, False):
                        if self._is_uri(cIdentifier):
                            catalog_dict[NTICatalogConstants.KEY_CATALOG_IDENTIFIER] = cIdentifier
                        else:
                            self._add_errormsg(NTIHarvesterConstants.WRONG_URI.format(
                                actual_field, cIdentifier), isCatalog)
                except RDFParserException as e:
                    self._add_errormsg(NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format
                                       (actual_field, str(e)), isCatalog)
                    log.debug(traceback.format_exc())
                log.debug(f"{method_log_prefix} Parsed catalog DCT.identifier....{catalog_dict.get(NTICatalogConstants.KEY_CATALOG_IDENTIFIER, 'None')}")

                # Creation date (dct:issued) - required, single
                log.debug(f"{method_log_prefix} Parsing catalog DCT.issued...")
                actual_field = NTICatalogConstants.METADATA_CATALOG_ISSUED
                try:
                    cDate, cType = self._object_value_datatype(
                        catalog_ref, DCT.issued)
                    cDate = self._strip_value(cDate)
                    if not self._check_empty_field(cDate, actual_field, isCatalog, True, False):
                        catalog_dict[NTICatalogConstants.KEY_CATALOG_ISSUED_DATE] = self._validate_iso8601_date(
                            cDate, cType)
                except RDFParserException as e:
                    self._add_errormsg(NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format
                                       (actual_field, str(e)), isCatalog)
                    log.debug(traceback.format_exc())
                log.debug(f"{method_log_prefix} Parsed catalog DCT.issued....{catalog_dict.get(NTICatalogConstants.KEY_CATALOG_ISSUED_DATE, 'None')}")

                # Date of last update (dct:modified) - required, single
                log.debug(f"{method_log_prefix} Parsing catalog DCT.modified...")
                actual_field = NTICatalogConstants.METADATA_CATALOG_MODIFIED
                try:
                    uDate, uType = self._object_value_datatype(
                        catalog_ref, DCT.modified)
                    uDate = self._strip_value(uDate)
                    if not self._check_empty_field(uDate, actual_field, isCatalog, True, False):
                        catalog_dict[NTICatalogConstants.KEY_CATALOG_MODIFIED_DATE] = self._validate_iso8601_date(
                            uDate, uType)
                except RDFParserException as e:
                    self._add_errormsg(f"{actual_field}, {str(e)}", isCatalog)
                    log.debug(traceback.format_exc())
                log.debug(f"{method_log_prefix} Parsed catalog DCT.modified....{catalog_dict.get(NTICatalogConstants.KEY_CATALOG_MODIFIED_DATE, 'None')}")

                log.debug(f"{method_log_prefix} Parsing catalog DCT.spatial...")
                actual_field = NTICatalogConstants.METADATA_CATALOG_SPATIAL
                spatials = self._object_value_list(catalog_ref, DCT.spatial)
                if (spatials):
                    spatialList = []
                    warnSpatials = []
                    num_expected_values = 0
                    for spatial in spatials:
                        spatial = self._strip_value(spatial)
                        spatial = spatial.replace('https://', 'http://')
                        if not self._check_empty_field(spatial, actual_field, isCatalog, False, False):
                            lower_spatial = spatial.lower()
                            if (lower_spatial.find(NTIPrefixConstants.SPATIAL_PREFIX.lower()) == 0):
                                final_value = cat_available_data.get(NTICatalogConstants.KEY_CATALOG_AVAILABLE_SPATIAL_COVERAGES, {}).get(
                                    lower_spatial, None)
                                if not final_value:
                                    self._add_errormsg(NTIHarvesterConstants.UNEXPECTED_VALUE.format(
                                        actual_field, spatial), isCatalog)
                                else:
                                    spatialList.append(final_value)
                                    if spatial != final_value:
                                        warnSpatials.append(spatial)
                                    if (lower_spatial.find(NTIPrefixConstants.SPATIAL_PROVINCE_PREFIX.lower()) == 0
                                            or spatial.find(NTIPrefixConstants.SPATIAL_CCAA_PREFIX.lower()) == 0):
                                        num_expected_values += 1
                    if spatialList and len(spatialList) > 0:
                        catalog_dict[NTICatalogConstants.KEY_CATALOG_SPATIAL] = spatialList
                    if warnSpatials and len(warnSpatials) > 0:
                        self._add_warningmsg(NTIHarvesterConstants.VALUE_NO_CASE_SENSITIVE.format(actual_field, ", ".join(warnSpatials)),
                                             isCatalog)
                log.debug(f"{method_log_prefix} Parsed catalog DCT.spatial....{catalog_dict.get(NTICatalogConstants.KEY_CATALOG_SPATIAL, 'None')}")

                log.debug(f"{method_log_prefix} Parsing catalog DCAT.themeTaxonomy...")
                actual_field = NTICatalogConstants.METADATA_CATALOG_THEME_TAXONOMY
                themes = self._object_value_list(
                    catalog_ref, DCAT.themeTaxonomy)
                finalThemes = []
                if themes:
                    expected_theme = False
                    for theme in themes:
                        theme = self._strip_value(theme)
                        theme = theme.replace('https://', 'http://')
                        if not self._check_empty_field(theme, actual_field, isCatalog, True, False):
                            if dhh.dge_harvest_is_url(theme):
                                lower_theme = theme.lower()
                                if lower_theme == NTIPrefixConstants.THEME_PREFIX_SLASH or \
                                        lower_theme == NTIPrefixConstants.THEME_PREFIX:
                                    expected_theme = True
                                    if theme != NTIPrefixConstants.THEME_PREFIX_SLASH and \
                                            theme != NTIPrefixConstants.THEME_PREFIX:
                                        self._add_warningmsg(NTIHarvesterConstants.REQUIRED_VALUE_NOT_FOUND_CASE_SENSITIVE % (
                                            actual_field, theme, NTIPrefixConstants.THEME_PREFIX_SLASH), isCatalog)
                                if lower_theme not in finalThemes:
                                    finalThemes.append(lower_theme)
                            else:
                                self._add_errormsg(NTIHarvesterConstants.WRONG_URL.format(
                                    actual_field, theme), isCatalog)
                    if not expected_theme:
                        self._add_errormsg(NTIHarvesterConstants.REQUIRED_VALUE_NOT_FOUND.format(
                            actual_field, NTIPrefixConstants.THEME_PREFIX), isCatalog)
                    if finalThemes and len(finalThemes) > 0:
                        catalog_dict[NTICatalogConstants.KEY_CATALOG_THEME_TAXONOMY] = finalThemes
                    else:
                        self._add_errormsg(
                            NTIHarvesterConstants.REQUIRED_FIELD_NOT_FOUND.format(actual_field), isCatalog)
                else:
                    self._add_errormsg(NTIHarvesterConstants.REQUIRED_FIELD_NOT_FOUND.format(actual_field), isCatalog)
                log.debug(f"{method_log_prefix} Parsed catalog DCAT.themeTaxonomy....{catalog_dict.get(NTICatalogConstants.KEY_CATALOG_THEME_TAXONOMY, 'None')}")

                # web (foaf:homepage) - required, single
                log.debug(f"{method_log_prefix} Parsing catalog FOAF.homepage...")
                actual_field = NTICatalogConstants.METADATA_CATALOG_HOMEPAGE
                try:
                    homepage = self._strip_value(
                        self._object_value(catalog_ref, FOAF.homepage))
                    if not self._check_empty_field(homepage, actual_field, isCatalog, True, False):
                        if dhh.dge_harvest_is_url(homepage):
                            catalog_dict[NTICatalogConstants.KEY_CATALOG_HOMEPAGE] = homepage
                        else:
                            self._add_errormsg(NTIHarvesterConstants.WRONG_URL.format(
                                actual_field, homepage), isCatalog)
                except RDFParserException as e:
                    self._add_errormsg(NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format
                                       (actual_field, str(e)), isCatalog)
                    log.debug(traceback.format_exc())
                log.debug(f"{method_log_prefix} Parsed catalog FOAF.homepage....{catalog_dict.get(NTICatalogConstants.KEY_CATALOG_HOMEPAGE, 'None')}")

                # License (dct:license) - required, single
                log.debug(f"{method_log_prefix} Parsing catalog DCT.license...")
                actual_field = NTICatalogConstants.METADATA_CATALOG_LICENSE
                try:
                    license = self._strip_value(
                        self._object_value(catalog_ref, DCT.license))
                    if not self._check_empty_field(license, actual_field, isCatalog, True, False):
                        if dhh.dge_harvest_is_url(license):
                            catalog_dict[NTICatalogConstants.KEY_CATALOG_LICENSE] = license
                        else:
                            self._add_errormsg(NTIHarvesterConstants.WRONG_URL.format(actual_field, license), isCatalog)
                except RDFParserException as e:
                    self._add_errormsg(NTIHarvesterConstants.FIELD_PLUS_MESSAGE.format(actual_field, str(e)), isCatalog)
                    log.debug(traceback.format_exc())
                log.debug(f"{method_log_prefix} Parsed catalog DC.license....{catalog_dict.get(NTICatalogConstants.KEY_CATALOG_LICENSE, 'None')}")

                log.debug(f"{method_log_prefix} Parsing catalog DCAT.dataset...")
                actual_field = NTICatalogConstants.METADATA_CATALOG_DATASET
                num_datasets = 0
                for o in self.g.objects(catalog_ref, DCAT.dataset):
                    num_datasets += 1
                if num_datasets == 0:
                    self._add_errormsg(NTIHarvesterConstants.REQUIRED_FIELD_NOT_FOUND.format(actual_field), isCatalog)
                log.debug(f"{method_log_prefix} Parsed catalog DCAT.dataset.... {num_datasets} datasets in catalog")

            actual_field = None

        except Exception as e:
            if not actual_field:
                self._add_errormsg(NTIHarvesterConstants.UNEXPECTED_ERROR.format(type(e).__name__, e), isCatalog)
                log.debug(traceback.format_exc())
            else:
                self._add_errormsg(NTIHarvesterConstants.UNEXPECTED_FIELD_ERROR.format(
                    actual_field, type(e).__name__, e), isCatalog)
                log.debug(traceback.format_exc())

        catalog_dict[NTICatalogConstants.KEY_CATALOG_ERRORS].extend(self.catalog_errors)
        catalog_dict[NTICatalogConstants.KEY_CATALOG_WARNINGS].extend(self.catalog_warnings)
        log.debug(f'{method_log_prefix} End method. Returns catalog_dict={catalog_dict}')
        return catalog_dict

    def graph_from_dataservice(self, dataservice_dict, dataservice_ref):
        pass
    
    def graph_from_dataservice_EDP(self, dataservice_dict, dataservice_ref):
        pass

    def graph_from_dataset(self, dataset_dict, dataset_ref):
        pass
    
    def graph_from_dataset_EDP(self, dataset_dict, dataset_ref):
        pass

    def graph_from_catalog(self, catalog_dict, catalog_ref):
        pass
    
    def graph_from_catalog_EDP(self, catalog_dict, catalog_ref):
        pass
    
    def _get_identifiers_in_datasets(self, datasets_in_catalog):
        '''
        Iterates a list of all datasets from the catalog and
        returns a list with all their identifiers or an empty
        list if there are no identifiers
        '''
        identifiers_in_datasets = []
        for dataset in datasets_in_catalog:
            identifier_in_dataset = self._object_value(URIRef(dataset), DCT.identifier)
            if identifier_in_dataset:
                identifiers_in_datasets.append(identifier_in_dataset)
        return identifiers_in_datasets

    def _check_duplicated_identifiers(self, identifiers_in_datasets):
        '''
        Iterates a list of identifiers, compares them and returns
        a duplicated identifier or None when there are not duplicities
        '''
        log.debug(f'Checking for duplicated dct:identifier')
        identifiers_aux = []
        for identifier in identifiers_in_datasets:
            if identifier in identifiers_aux:
                return identifier
            identifiers_aux.append(identifier)
        return None