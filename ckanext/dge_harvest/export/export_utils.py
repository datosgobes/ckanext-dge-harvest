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

import logging
import traceback
import inspect
import json
import gzip
import shutil
from pathlib import Path
from dateutil.parser import parse as dateutil_parse
from ckan.common import _
from ckan.plugins import toolkit
from ckan.plugins.toolkit import config
from rdflib import URIRef
from ..constants import (DCATAPESDataserviceConstants, DCATAPESConfigConstants,
                         DcatClassNameEnum, CommonPackageConstants)
from ..utils import dge_harvest_dataservice_uri
from ..harvester_config_reader import HarvesterConfigReader
from ..decorators import log_debug, log_info

log = logging.getLogger(__name__)

RDF_FORMAT = 'rdf'
CSV_FORMAT = 'csv'

wrong_page_exception = toolkit.ValidationError(
    'Page param must be a positive integer starting in 1')

@log_info
def get_filepath(format:str, filename:str, is_edp:bool, config_reader:HarvesterConfigReader):
    if format==RDF_FORMAT:
            if is_edp:
                filepath = config_reader.get_property(DCATAPESConfigConstants.SECTION_RDF_EXPORT, 'rdf.export.edp.filepath', '/mnt/gmv/sync/datosgobes_output_edp.rdf')
            else:
                filepath = config_reader.get_property(DCATAPESConfigConstants.SECTION_RDF_EXPORT, 'rdf.export.filepath', '/mnt/gmv/sync/datosgobes_output.rdf')
    elif format==CSV_FORMAT:
        filepath = config_reader.get_property(DCATAPESConfigConstants.SECTION_CSV_EXPORT, 'csv.export.filepath', '/tmp/catalog.csv')
    else:
        filepath = '/tmp/catalog.' + format
    return _get_final_filepath(filepath, filename)

def _get_final_filepath(filepath, filename):
    final_filepath = filepath
    if filename:
        new_path = Path(filename)
        path = Path(filepath)
        if path.suffix != new_path.suffix:
            new_filename_witouth_extension = new_path.stem
            new_filename = new_filename_witouth_extension + path.suffix
        else:
            new_filename = filename
        
        final_filepath = path.with_name(new_filename)
    return str(final_filepath)

def get_first_page_data_dicts(context, data_dict, entity_type, exclude_entities_in_rdf_store):
    return get_data_dicts_by_page(context, data_dict, entity_type, 1, None, exclude_entities_in_rdf_store)

@log_debug
def get_data_dicts_by_page(context, data_dict, entity_type, page, datasets_to_process=-1, exclude_entities_in_rdf_store=False):
    data = {}
    if entity_type and (entity_type == DcatClassNameEnum.DATASET or  DcatClassNameEnum.DATASERVICE):
        data_dict['page'] = page
        query = _dge_harvest_search_data_dict_entities(context, data_dict, datasets_to_process, entity_type, exclude_entities_in_rdf_store)
        data = {
            'data_dicts': query['results'],
            'total_entities': query['count']
            }
    return data

def _dge_harvest_search_data_dict_entities(context, data_dict, datasets_left, entity_type, exclude_entities_in_rdf_store):
    result = {}
    search_dict = {}
    datasets_left = datasets_left or -1
    exclude_entities_in_rdf_store = exclude_entities_in_rdf_store or False
    if entity_type and (entity_type == DcatClassNameEnum.DATASET or entity_type == DcatClassNameEnum.DATASERVICE):
        search_dict['fq'] = 'dataset_type:dataset'
        search_dict['fq_list'] = ['-dataset_type:dataservice']
        if entity_type == DcatClassNameEnum.DATASERVICE:
            search_dict['fq'] = 'dataset_type:dataservice'
            search_dict['fq_list'] = ['-dataset_type:dataset']
        # exclude harvested entities with dcat_ap_es profile
        if exclude_entities_in_rdf_store:
            search_dict['fq_list'].append(f'-(guid:[* TO *] AND application_profile:{CommonPackageConstants.KEY_EXTRAS_APPLICATION_PROFILE_DCAT_AP_ES_100_VALUE})')
        result = _dge_harvest_search_ckan_entities(context, data_dict, datasets_left, search_dict)
    return result

def _dge_harvest_search_ckan_entities(context, data_dict, datasets_left, search_dict):
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    page = data_dict.get('page', 1) or 1
    try:
        page = int(page)
        if page < 1:
            raise wrong_page_exception
    except ValueError:
        raise wrong_page_exception

    modified_since = data_dict.get('modified_since')
    if modified_since:
        try:
            modified_since = dateutil_parse(modified_since).isoformat() + 'Z'
        except (ValueError, AttributeError) as e:
            log.error(f'{method_log_prefix} Exception {type(e): str(e)}. Raising ValidationError')
            raise toolkit.ValidationError(
                'Wrong modified date format. Use ISO-8601 format')

    _rows = _get_rows_per_page(data_dict.get('limit', -1), datasets_left)
    _start = int(config.get('ckanext.dcat.datasets_per_page', DCATAPESConfigConstants.DATASETS_PER_PAGE)) * (page - 1)

    search_data_dict = {
        'rows': _rows,
        'start': _start,
        'sort': 'organization asc, metadata_modified desc',
    }
    
    search_data_dict['q'] = data_dict.get('q', '*:*')
    search_data_dict['fq'] = search_dict.get('fq') 
    search_data_dict['fq_list'] = []

    # Include only public and active elemnts
    search_data_dict['fq_list'].append('capacity:public')
    search_data_dict['fq_list'].append('state:active')

    # Exclude draft packages
    search_data_dict['fq_list'].append('-state:draft')

    # Exclude certain dataset types
    search_data_dict['fq_list'].append('-dataset_type:harvest')
    search_data_dict['fq_list'].append('-dataset_type:showcase')
    search_data_dict['fq_list'].extend(search_dict.get('fq_list'))

    if modified_since:
        search_data_dict['fq_list'].append(
            'metadata_modified:[{0} TO NOW]'.format(modified_since))
    
    log.info(f'{method_log_prefix} search_data_dict = {search_data_dict}')
    query = toolkit.get_action('package_search')(context, search_data_dict)
    return query

def _get_rows_per_page(limit, total_datasets_left=-1):
    _default_datasets_per_page = int(config.get('ckanext.dcat.datasets_per_page', DCATAPESConfigConstants.DATASETS_PER_PAGE))
    datasets_per_page = -1
    if _is_limit_minor_than_default_datasets_per_page(limit, _default_datasets_per_page):
        datasets_per_page = limit
    elif _is_total_datasets_left_minor_than_default_datasets_per_page(total_datasets_left, _default_datasets_per_page):
        datasets_per_page = total_datasets_left
    else:
        datasets_per_page = _default_datasets_per_page
    return datasets_per_page

def _is_limit_minor_than_default_datasets_per_page(limit, datasets_per_page):
    return limit > -1 and limit < datasets_per_page

def _is_total_datasets_left_minor_than_default_datasets_per_page(total_datasets_left, datasets_per_page):
    return total_datasets_left > -1 and total_datasets_left < datasets_per_page

@log_debug
def complete_dataservices_dict_info(dataservice_dicts, dataservices_dict):
    '''
    Complete the dataservice information with their URIRef and init a list for their servesDataset
    `dataservice_dicts` list of data service dictionaries to be processed and stored in `dataservices_dict`.
    `dataservices_dicts` dictionary storing all the data services with key the id of the data service and value a dictionary with the complete data of the data services
    Returns the dictionary `dataservices_dict` received by parameter,  once the complete information of the data services received by parameter in `dataservice_dicts` has been added.
    '''
    for dataservice_dict in dataservice_dicts:
        dataservice_id = dataservice_dict.get(DCATAPESDataserviceConstants.KEY_ID)
        uriref = URIRef(dge_harvest_dataservice_uri(dataservice_dict))
        if dataservice_id:
            dataservice_dict[DCATAPESDataserviceConstants.KEY_URI] = uriref
            dataservice_dict[DCATAPESDataserviceConstants.KEY_DATASERVICE_SERVES_DATASET] = []            
            dataservices_dict[dataservice_id] = dataservice_dict
    return dataservices_dict

@log_debug
def compress_file_in_gzip(filepath:str):
    _gzip_filepath = filepath
    if filepath:
        try:
            _gzip_filepath = filepath + ".gz"
            with open(filepath, 'rb') as f_in:
                with gzip.open(_gzip_filepath, 'wb', compresslevel=9) as f_out:
                    shutil.copyfileobj(f_in, f_out)
        except Exception as e:
            log.error(f'File {filepath} could not be compressed in gzip. Excepcion {type(e)}: {str(e)}')
            _gzip_filepath = filepath
    return _gzip_filepath
    