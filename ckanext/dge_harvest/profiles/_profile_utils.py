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
import json
import rfc3987
import inspect
import re
from typing import List

from urllib import parse as urllib_parse
from rdflib import term, URIRef, BNode, Literal, Graph

from ckan.plugins.toolkit import config
from ..constants import (DCATAPESSerializerConstants as SerializerConstants,
                         CommonPackageConstants as PackageConstants,
                         DCATAPESPrefixConstants as PrefixConstants)
from ..utils import get_value_of_an_extras_key_from_dict
log = logging.getLogger(__name__)

def _get_organization_minhap_from_organization_uri(organization_uri, organizations):
    organization_minhap = None
    organization_data = None
    if organization_uri:
        splitted_upper_organization_uri = organization_uri.upper().split('/')
        if splitted_upper_organization_uri and len(splitted_upper_organization_uri) > 0:
            organization_minhap = splitted_upper_organization_uri[-1]
    if organization_minhap and organizations:
        organization_data = organizations.get(organization_minhap, None)
    return organization_minhap, organization_data

def _get_value_of_an_extras_key_from_dict(data_dict:dict[str, object], key:str) -> str:
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
        for extra in data_dict.get(PackageConstants.KEY_EXTRAS, []):
            if extra.get('key', None) == key:
                value = extra.get('value', None)
    return value

def _is_european_export(data_dict):
    return data_dict.get(SerializerConstants.EUROPEAN_CATALOG_EXPORT, False) if data_dict else False

def _has_european_data_themes(themes):
    for theme in themes or []:
        if theme and theme.startswith(PrefixConstants.THEME_EU_PREFIX):
            return True
    return False

def _is_nti_dataset(data_dict):
    _is_nti_dataset = True
    application_profile = get_value_of_an_extras_key_from_dict(data_dict, PackageConstants.KEY_EXTRAS_APPLICATION_PROFILE)
    if application_profile and application_profile == PackageConstants.KEY_EXTRAS_APPLICATION_PROFILE_DCAT_AP_ES_100_VALUE:
        _is_nti_dataset = False
    return _is_nti_dataset

def _validate_iso8601_date(datevalue, datetype):
    '''
    Returns the date with 'YYY-MM-DDTHH:mm:ssTZD' ISO 8601 format

    Note that partial dates will be expanded to the first month / day
    value, eg '1904' -> '1904-01-01'.

    Returns a string with the date value Europe/Madrid timezone,
    or None if datevalue is None. If datetype is None, XSD.dateTime is considered
    Raise RDFParserException if the datevalue format is not as expected
    '''
    import iso8601
    import pytz
    from ckanext.dge_harvest.constants.constants import ConfigConstants
    from ckanext.dge_harvest.constants.nti_constants import NTIHarvesterConstants
    from rdflib.namespace import XSD
    from ckanext.dcat.exceptions import RDFProfileException
    result = None
    errormsg = None
    if (datevalue):
        try:
            if (not datetype):
                datetype = XSD.dateTime
            if (datetype not in [XSD.date, XSD.dateTime]):
                errormsg = NTIHarvesterConstants.UNEXPECTED_DATE_DATATYPE.format(
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
            errormsg = NTIHarvesterConstants.UNEXPECTED_DATE_FORMAT.format(datevalue)
            log.error(f"Exception {type(e)}: {str(e)}" , exc_info=True)
            raise RDFProfileException(errormsg)
        except ValueError as e:
            errormsg = NTIHarvesterConstants.UNEXPECTED_DATE_VALUE.format(datevalue, str(e))
            log.error(f"Exception {type(e)}: {str(e)}" , exc_info=True)
            raise RDFProfileException(errormsg)
        if errormsg is not None:
            raise RDFProfileException(errormsg)
    return result

def _get_encoded_url(url, encode_url = True):
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    if not encode_url:
        return url
    netloc_re = re.compile('^(?:([^:]*)[:]([^@]*)@)?([^:]+)(?:[:](\d+))?$')
    result = url
    try:
        if  (url and url.strip()):
            encoded_url = url.strip()

            prev_encoded_url = ''
            while '%' in encoded_url and prev_encoded_url != encoded_url:
                prev_encoded_url = encoded_url
                encoded_url = urllib_parse.unquote(encoded_url)

            try:
                encoded_url = encoded_url.encode('utf-8')
            except Exception as e:
                log.error(f"{method_log_prefix} Exception in method. {str(e)}")

            parsed_url = urllib_parse.urlparse(encoded_url.decode('utf-8'))

            netloc_m = netloc_re.match(parsed_url.netloc)
            netloc_m_groups = netloc_m.groups() if netloc_m else []
            username, password, host, port = (
                urllib_parse.quote(g, safe='/@') if g else g for g in netloc_m_groups or [])
            netloc = ('{}:{}@'.format(username, password) if username and password else '') + \
                host + (':' + port if port else '')

            scheme = urllib_parse.quote(urllib_parse.unquote(parsed_url.scheme), '+')
            path = urllib_parse.quote(urllib_parse.unquote(parsed_url.path), "/")
            query = urllib_parse.quote(urllib_parse.unquote(parsed_url.query),'?/&="')
            params = urllib_parse.quote(urllib_parse.unquote(parsed_url.params), "?/&=")
            fragment = urllib_parse.quote(urllib_parse.unquote(parsed_url.fragment), "?/&=")
            netloc = urllib_parse.quote(urllib_parse.unquote(netloc), safe=':@')

            result = urllib_parse.urlunparse((scheme, netloc, path,
                                        params, query, fragment))

            match_object = rfc3987.match(result, rule='URI')
            if  match_object:
                return result
            chars = config.get('ckanext.dge_harvest.rdf_edp.chars', '')
            if chars:
                for c in chars:
                    fragment.replace(c, urllib_parse.quote(c))
                    query.replace(c, urllib_parse.quote(c))

            query = [(urllib_parse.quote(k), urllib_parse.quote(v)) for k, v in urllib_parse.parse_qsl(
                parsed_url.query, keep_blank_values=True)]
            query = '&'.join(
                [qi[0] + ('=' + qi[1] if qi[1] else '') for qi in query])

            result = urllib_parse.urlunparse((scheme, netloc, path,
                                        params, query, fragment))
            log.debug(f'{method_log_prefix} 3 final url {encoded_url}')
            log.debug(f'{method_log_prefix} result {result}')
    except Exception as e:
        log.error(f"{method_log_prefix} Exception {type(e)} encoding url {url or ''} in method. {str(e)}")
    return result