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
import iso8601
import re
import logging

from pytz import timezone
from ckan.plugins import toolkit
from ckan.plugins.toolkit import config

import ckanext.scheming.helpers as sh
import ckan.lib.helpers as h
import ckan.model as model

import ckanext.dge_harvest.helpers as dhh
import ckanext.dge_harvest.losser as losser
from ..utils import dge_harvest_dataset_uri, dge_harvest_dataservice_uri, get_extra_value
from ..constants import (ConfigConstants, CommonPackageConstants, DCATAPESConfigConstants,
                        DCATAPESDataserviceConstants, DCATAPESDatasetConstants, 
                        DCATAPESDistributionConstants, NTIDatasetConstants,
                        DcatClassNameEnum)
from ..export import export_utils
from ..harvester_config_reader import HarvesterConfigReader
from ..decorators import log_info

log = logging.getLogger(__name__)

CSV_FORMAT = 'csv'
MAIN_SEPARATOR = '//'
SECONDARY_SEPARATOR = ';'

@log_info
def dge_harvest_catalog_show_csv(context, data_dict, config_filepath):
    method_log_prefix = f'[{__name__}][dge_harvest_catalog_show_csv]' 
    output = None
    try:
        _init_time = datetime.datetime.now()
        toolkit.check_access('dge_harvest_catalog_show', context, data_dict)
        _format=data_dict.get('format')
        harvester_config_reader = _get_harvester_config_reader(config_filepath) 
        _filepath = export_utils.get_filepath(_format, data_dict.get('filename', None), False, harvester_config_reader)
        columnsfilepath = _get_columnsfilepath(harvester_config_reader)
        # Datasets
        log.info(f'{method_log_prefix} #### Getting datasets ###')
        _dataset_dicts = export_utils.get_first_page_data_dicts(context, data_dict, DcatClassNameEnum.DATASET, False)
        _output = _serialize_packages(_format, _dataset_dicts.get('data_dicts'), columnsfilepath)
        _write_datasets_file(_filepath, _output)
        _total_datasets = _dataset_dicts.get('total_entities')
        limit = data_dict.get('limit', -1)
        if limit > -1 and limit < _total_datasets:
            _total_datasets = limit
        _total_datasets_left_to_process = _total_datasets - len(_dataset_dicts.get('data_dicts'))
        _page = 1
        while (_total_datasets_left_to_process > 0):
            _page += 1
            _dataset_dicts = export_utils.get_data_dicts_by_page(context, data_dict, DcatClassNameEnum.DATASET, _page, _total_datasets_left_to_process, False)
            _output = _append_serialize_packages(_dataset_dicts.get('data_dicts'), columnsfilepath)
            _append_datasets_file(_filepath, _output)
            _total_datasets_left_to_process = _total_datasets_left_to_process - len(_dataset_dicts.get('data_dicts'))
            log.debug(f'{method_log_prefix} Datasets query get: {len(_dataset_dicts.get("data_dicts"))}' )
            log.debug(f'{method_log_prefix} Total_datasets to left: {_total_datasets_left_to_process}')
        _end_time = datetime.datetime.now()
        log.debug(f"{method_log_prefix} Time in serialize {_total_datasets} datasets ... {int((_end_time - _init_time).total_seconds() * 1000)} milliseconds")

        # Dataservices
        log.info(f'{method_log_prefix} #### Getting dataservices ###')
        _dataservice_dicts = export_utils.get_first_page_data_dicts(context, data_dict, DcatClassNameEnum.DATASERVICE, False)
        _output = _append_serialize_packages(_dataservice_dicts.get('data_dicts'), columnsfilepath)
        _append_datasets_file(_filepath, _output)
        _total_dataservices = _dataservice_dicts.get('total_entities')
        limit = data_dict.get('limit', -1)
        if limit > -1 and limit < _total_dataservices:
            _total_dataservices = limit
        _total_dataservices_left_to_process = _total_dataservices - len(_dataservice_dicts.get('data_dicts'))
        _page = 1
        while (_total_dataservices_left_to_process > 0):
            _page += 1
            _dataservice_dicts = export_utils.get_data_dicts_by_page(context, data_dict, DcatClassNameEnum.DATASERVICE, _page, _total_dataservices_left_to_process, False)
            _output = _append_serialize_packages(_dataservice_dicts.get('data_dicts'), columnsfilepath)
            _append_datasets_file(_filepath, _output)
            _total_dataservices_left_to_process = _total_dataservices_left_to_process - len(_dataservice_dicts.get('data_dicts'))
            log.debug(f'{method_log_prefix} Dataservices query get: {len(_dataservice_dicts.get("data_dicts"))}' )
            log.debug(f'{method_log_prefix} Total_dataservices to left: {_total_dataservices_left_to_process}')
        _end_time = datetime.datetime.now()
        log.debug(f"{method_log_prefix} Time in serialize {_total_dataservices} dataservices ... {int((_end_time - _init_time).total_seconds() * 1000)} milliseconds")
        # Compress in .gz
        if data_dict.get('compress'):
            export_utils.compress_file_in_gzip(_filepath)
        log.debug(f"{method_log_prefix} Serialized catalog (CSV format) in {_filepath} with {_total_datasets} datasets and {_total_dataservices} dataservices ... {int((_end_time - _init_time).total_seconds() * 1000)} milliseconds")
    except Exception as e:
        log.error(f"{method_log_prefix} Exception {type(e).__name__}: {e}", exc_info=True)
        output = None
    return output

def _serialize_packages(format, dataset_dicts, columnsfilepath):
    output = None
    if format == CSV_FORMAT and columnsfilepath:
        output = _dge_csv_serialize_packages(dataset_dicts, columnsfilepath, None)
    return output

def _write_datasets_file(filepath, output):
    if not isinstance(output, str):
        output = output.decode('utf-8')
    _write_file(filepath, output, "w")

def _append_datasets_file(filepath, output):
    _write_file(filepath, output, "a")

def _write_file(filepath, output, mode):
    if filepath:
        file = None
        try:
            file = open(filepath, mode)
            file.write(output)
            file.close()
        except Exception as e:
            log.error(f'Error writting file. Exception {type(e)}: {str(e)}', exc_info=True)
            if file and not file.closed:
                file.close()

def _get_harvester_config_reader(config_filepath):
    harvester_config_filepath =  config_filepath if config_filepath else config.get('ckanext.dge_harvest.dcat_ap_es_1_0_0.config.filepath', '')
    return HarvesterConfigReader(harvester_config_filepath)

def _append_serialize_packages(dataset_dicts, columnsfilepath):
    return _append_dge_csv_serialize_packages(dataset_dicts, columnsfilepath)

def _get_columnsfilepath(harvester_config_reader):
    columns_filepath = None
    if not harvester_config_reader:
        harvester_config_reader = _get_harvester_config_reader(None)
    if harvester_config_reader:
        columns_filepath = harvester_config_reader.get_property(DCATAPESConfigConstants.SECTION_CSV_EXPORT, DCATAPESConfigConstants.PROP_CSV_COLUMNS)
    return columns_filepath

def _append_dge_csv_serialize_packages(dataset_dicts, columnsfilepath):
    output = _dge_csv_serialize_packages(dataset_dicts, columnsfilepath, None)
    if output:
        _output_without_header = output.decode('utf-8').split("\n",1)[1]
    return _output_without_header

def _dge_csv_serialize_packages(package_dicts, columnsfilepath, config_filepath):
    method_log_prefix = f'[{__name__}][_dge_csv_serialize_packages]'
    if not columnsfilepath and config_filepath:
        harvester_config_reader = _get_harvester_config_reader(config_filepath)
        columnsfilepath = _get_columnsfilepath(harvester_config_reader)
    output = None
    log.debug(f'{method_log_prefix} Init method.')

    if not (package_dicts and columnsfilepath):
        return None

    organizations = {}
    nti_risp_themes = dhh.dge_harvest_dict_theme_option_label()
    nti_risp_spatial_coverages = dhh.dge_harvest_dict_spatial_coverage_option_label()
    _dataset = sh.scheming_get_schema('dataset', 'dataset')
    res_format = sh.scheming_field_by_name(_dataset.get('resource_fields'), 'format')
    format_values = res_format['choices']
    formats = {}
    packages = []
    num = 0
    for package in package_dicts:
        _package_type = package.get('type')
        _is_dataset = _package_type == CommonPackageConstants.KEY_TYPE_DATASET_VALUE
        _is_dataservice = _package_type == CommonPackageConstants.KEY_TYPE_DATASERVICE_VALUE
        if not (_is_dataset or _is_dataservice):
            continue
        if _is_dataset:
            ds = _csv_serialize_dataset(package, nti_risp_themes, organizations, nti_risp_spatial_coverages, formats, format_values)
        else:
            ds = _csv_serialize_dataservice(package, nti_risp_themes, organizations)
        num += 1
        packages.append(ds)
    log.debug(f'{method_log_prefix} Numero de packages con datos a exportar...{num}')
    output = losser.table(
        packages, columnsfilepath, csv=True, pretty=False)
    log.debug(f'{method_log_prefix} End method.')
    return output

def _csv_serialize_dataset(dataset, nti_risp_themes, organizations, nti_risp_spatial_coverages, formats, format_values):
    ds = {}
    
    application_profile = get_extra_value(DCATAPESDatasetConstants.KEY_EXTRAS_APPLICATION_PROFILE, dataset)
    _is_dcatapes = application_profile and application_profile == DCATAPESDatasetConstants.KEY_EXTRAS_APPLICATION_PROFILE_DCAT_AP_ES_100_VALUE

    # ulr
    ds['url'] = dge_harvest_dataset_uri(dataset)
        
    ds['entity_type'] = 'dataset'

    # Description
    ds['description'] = _encode_value(_from_dict_to_string(dataset.get(DCATAPESDatasetConstants.KEY_DATASET_DESCRIPTION, None)), True)

    # Title
    ds['title'] = _encode_value(_from_dict_to_string(dataset.get(DCATAPESDatasetConstants.KEY_DATASET_TITLE_TRANSLATED, None)), True)

    # Theme
    ds['theme'] = _get_encode_nti_risp_theme_values(dataset.get(DCATAPESDatasetConstants.KEY_DATASET_THEME, None), nti_risp_themes)

    # Tags 
    ds['tags'] = _get_encode_tags(dataset.get(DCATAPESDatasetConstants.KEY_DATASET_MULTILINGUAL_TAGS))

    # Identifier
    ds['identifier'] = _encode_value(_from_list_to_string(dataset.get(DCATAPESDatasetConstants.KEY_DATASET_IDENTIFIER, None)), True)

    # Created
    if _is_dcatapes:
        ds['issued_date'] = _encode_value(dataset.get(DCATAPESDatasetConstants.KEY_DATASET_ISSUED_DATE, None))
    else:
        ds['issued_date'] = _encode_value(_from_iso8601_date_to_string(dataset.get(DCATAPESDatasetConstants.KEY_DATASET_ISSUED_DATE, None)))
    
    # Modified
    if _is_dcatapes:
        ds['modified_date'] = _encode_value(dataset.get(DCATAPESDatasetConstants.KEY_DATASET_MODIFIED_DATE, None))
    else:
        ds['modified_date'] = _encode_value(_from_iso8601_date_to_string(dataset.get(DCATAPESDatasetConstants.KEY_DATASET_MODIFIED_DATE, None)))

    # Accrual Periodicity
    ds['frequency'] = _get_encode_frequency(dataset.get(DCATAPESDatasetConstants.KEY_DATASET_FREQUENCY))

    # Language
    ds['language'] = _encode_value( _from_list_to_string(dataset.get(DCATAPESDatasetConstants.KEY_DATASET_LANGUAGE)), True)

    # Publisher
    ds['publisher'] = _get_encode_publisher(dataset.get(DCATAPESDatasetConstants.KEY_PUBLISHER, None), organizations)

    # License
    if not _is_dcatapes:
        ds['license_id'] = _encode_value(dataset.get(NTIDatasetConstants.KEY_DATASET_LICENSE), True)

    # Spatial
    ds['spatial'] = _get_encode_spatial(dataset.get(DCATAPESDatasetConstants.KEY_DATASET_SPATIAL, None), nti_risp_spatial_coverages)

    # Temporal
    ds['coverage_new'] = _get_encode_temporal(dataset.get(DCATAPESDatasetConstants.KEY_DATASET_TEMPORAL_COVERAGE, None), _is_dcatapes )

    # Valid
    if not _is_dcatapes:
        ds['valid'] = _encode_value(_from_iso8601_date_to_string(dataset.get(NTIDatasetConstants.KEY_DATASET_VALID, None)), True)

    # References
    if not _is_dcatapes:
        ds['references'] = _encode_value(_from_list_to_string(dataset.get(NTIDatasetConstants.KEY_DATASET_REFERENCE, None)), True)

    # Normative
    ds['conforms_to'] = _encode_value(_from_list_to_string(dataset.get(DCATAPESDatasetConstants.KEY_DATASET_NORMATIVE, None)), True)

    # Resources
    ds['resources'] = _csv_serialize_resources(dataset.get(DCATAPESDatasetConstants.KEY_RESOURCES, []), formats, format_values)

    # EndpointURL
    ds['endpoint_url'] = None
    return ds

def _csv_serialize_resources(resources, formats, format_values):
    result = None
    if not resources:
        return result
    sresources = []
    for resource in resources:
        sresource = _csv_serialize_resource(resource, formats, format_values)
        if sresource and len(sresource) > 0:
            sresources.append(sresource)
    if len(sresources) > 0:
        value = None
        for item in sresources:
            if value:
                value = f'{value}{MAIN_SEPARATOR}{item}'
            else:
                value = item
        result = _encode_value(value, True)
    return result

def _csv_serialize_resource(resource, formats, format_values):
    if not resource:
        return None
    #title
    name = _from_dict_to_string(resource.get(DCATAPESDistributionConstants.KEY_DISTRIBUTION_TITLE_TRANSLATED, None), 'TITLE_')
    name = name or ''

    # access_url
    access_urls = resource.get(DCATAPESDistributionConstants.KEY_DISTRIBUTION_ACCESS_URL, [])
    url = access_urls[0] if access_urls else None
    access_url = f'[ACCESS_URL]{url}' if url else ''

    # format
    format_value = resource.get(DCATAPESDistributionConstants.KEY_DISTRIBUTION_FORMAT, None)
    _format = None
    if format_value:
        if format_value in formats:
            _format = formats.get(format_value, None)
        else:
            formats[format_value] = sh.scheming_choices_label(format_values, format_value)
            _format = formats.get(format_value, None)
        if _format:
            _format = f'[MEDIA_TYPE]{_format}'

    # byte size
    size = resource.get(DCATAPESDistributionConstants.KEY_DISTRIBUTION_BYTE_SIZE, '')
    size = f'[BYTE_SIZE]{size}' if size else ''

    # relation
    relation = _from_list_to_string(resource.get(NTIDatasetConstants.KEY_DATASET_RESOURCE_RELATION, None), SECONDARY_SEPARATOR)
    relations = f'[RELATION]{relation}' if relation else ''

    return  f'{name}{access_url}{_format}{size}{relations}'

def _csv_serialize_dataservice(dataservice, nti_risp_themes, organizations):
    if not dataservice:
        return {}
    ds = {}

    # ulr
    ds['url'] = dge_harvest_dataservice_uri(dataservice)
    
    #entity_type
    ds['entity_type'] = 'dataservice'

    # Description
    ds['description'] = _encode_value(_from_dict_to_string(dataservice.get(DCATAPESDataserviceConstants.KEY_DATASERVICE_DESCRIPTION, None)), True)

    # Title
    ds['title'] = _encode_value(_from_dict_to_string(dataservice.get(DCATAPESDataserviceConstants.KEY_DATASERVICE_TITLE_TRANSLATED, None)), True)

    # Theme
    ds['theme'] =_get_encode_nti_risp_theme_values(dataservice.get(DCATAPESDataserviceConstants.KEY_DATASERVICE_THEME, None), nti_risp_themes)

    # Tags
    ds['tags'] = _get_encode_tags(dataservice.get(DCATAPESDataserviceConstants.KEY_DATASERVICE_MULTILINGUAL_TAGS))

    # Publisher
    ds['publisher'] = _get_encode_publisher(dataservice.get(DCATAPESDataserviceConstants.KEY_PUBLISHER), organizations)

    # License
    ds['license_id'] = _encode_value(dataservice.get(DCATAPESDataserviceConstants.KEY_DATASERVICE_LICENSE), True)

    # EndpointURL
    ds['endpoint_url'] = _encode_value(_from_list_to_string(dataservice.get(DCATAPESDataserviceConstants.KEY_DATASERVICE_ENDPOINT_URL, None)), True)

    return ds

def _get_encode_nti_risp_theme_values(package_theme_values, nti_risp_themes):
    theme_labels = []
    theme_value = None
    if package_theme_values:
        for value in package_theme_values:
            theme = nti_risp_themes.get(value)
            if theme and theme.get('label'):
                theme_labels.append(theme.get('label').get('es'))
        theme_value = _encode_value(_from_list_to_string(theme_labels), True)
    return theme_value

def _get_encode_tags(tags):
    value = None
    encode_tags = None
    if tags and len(tags) > 0:
        tags_field = None
        for key, value in list(tags.items()):
            if value and len(value) > 0:
                if tags_field:
                    tags_field = f'{tags_field}[{key}]{_from_list_to_string(value)}'
                else:
                    tags_field = f'[{key}]{_from_list_to_string(value)}'
        if tags_field:
            encode_tags = _encode_value(tags_field, True)
    return encode_tags

def _get_encode_publisher(publisher, organizations):
    encode_publisher = None
    if not publisher:
        return encode_publisher
    if publisher in organizations:
        encode_publisher = _encode_value(organizations.get(publisher, None), True)
    else:
        organization = h.get_organization(publisher, False)
        if organization:
            organizations[publisher] = organization.get(
                'title', organization.get('display_name', None))
            encode_publisher = _encode_value(organizations.get(publisher), True)
        else:
            organization = model.Group.get(publisher)
            if organization:
                organizations[publisher] = organization.title if organization.title else organization.name
                encode_publisher = _encode_value(organizations.get(publisher), True)
    return encode_publisher

def _get_encode_temporal(temporal_coverage, is_dcatapes_entity):
    value = None
    if not temporal_coverage or not temporal_coverage.values():
        return None
    for tc in temporal_coverage.values():
        str_tc = _get_temporal_value(tc, is_dcatapes_entity)
        if str_tc:
            if value:
                value = f"{value}{MAIN_SEPARATOR}{str_tc}"
            else:
                value = f"{str_tc}"
    result = _encode_value(value, True)
    return result

def _get_temporal_value(temporal_coverage, is_dcatapes_entity):
    value = None
    if not temporal_coverage:
        return None
    tc_from = temporal_coverage.get('from', None) if is_dcatapes_entity else _from_iso8601_date_to_string(temporal_coverage.get('from', None)) 
    tc_to = temporal_coverage.get('to', None) if is_dcatapes_entity else _from_iso8601_date_to_string(temporal_coverage.get('to', None))
    if tc_from or tc_to:
        value = f"{(tc_from or '')}-{(tc_to or '')}"
    return value

def _get_encode_spatial(spatial_values, nti_risp_spatial_coverages):
    if not spatial_values:
        return None
    spatial_labels = []
    for value in spatial_values:
        if value and isinstance(value, dict):
            uri_value = value.get('uri')
            if uri_value:
                spatial = nti_risp_spatial_coverages.get(uri_value)
                if spatial and spatial.get('label') and spatial.get('label').get('es'):
                    spatial_labels.append(spatial.get('label').get('es'))
    spatials = _from_list_to_string(spatial_labels)
    return _encode_value(spatials, True)

def _get_encode_frequency(frequency):
    result = None
    if (frequency):
        stype = frequency.get('type', '')
        if stype and stype == 'uri':
            sfrequency = frequency.get('uri')
        elif stype and len(stype) > 0:
            stype = 'http://www.w3.org/2006/time#' + stype
            svalue = frequency.get('value', '')
            sfrequency = f'[TYPE]{stype}[VALUE]{svalue}'
        result = _encode_value(sfrequency, True)
    return result

def _encode_value(value=None, clean=False):
    if value:
        if clean and clean == True:
            value = re.sub('[\n\r]', ' ', value)
        return value

def _from_list_to_string(data_list=None, separator = MAIN_SEPARATOR):
    method_log_prefix = f'[{__name__}][_from_list_to_string]' 
    result = None
    try:
        if data_list:
            for value in data_list:
                if result:
                    result = f"{result}{separator}{value}"
                else:
                    result = f"{value}"
    except Exception as e:
        result = None
        log.error(f"{method_log_prefix} Exception {type(e).__name__}: {e}")
    return result

def _from_dict_to_string(data_dict=None, key_prefix=None):
    method_log_prefix = f'[{__name__}][_from_dict_to_string]'
    result = None
    try:
        if not data_dict:
            return result
        for key, value in list(data_dict.items()):
            if value and len(value) > 0:
                if key_prefix:
                    key = key_prefix + key
                if result:
                    result = f'{result}[{key}]{value}'
                else:
                    result = f'[{key}]{value}'
    except Exception as e:
        result = None
        log.error(f"{method_log_prefix} Exception {type(e).__name__}: {e}")
    return result

def _from_iso8601_date_to_string(datevalue):
    method_log_prefix = f'[{__name__}][_from_dict_to_string]'
    result = None
    try:
        if (datevalue):

            default_timezone = timezone(ConfigConstants.DEFAULT_TIMEZONE)
            naive = iso8601.parse_date(datevalue, None)
            local_dt = default_timezone.localize(naive, is_dst=None)
            result = local_dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    except Exception as e:
        result = datevalue
        log.error(f"{method_log_prefix} Exception {type(e).__name__}: {e}")
    return result