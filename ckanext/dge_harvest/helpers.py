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

import ckanext.dge_scheming.helpers as dsh
import ckanext.scheming.helpers as sh
from ckan.plugins.toolkit import config
from ckan.lib.i18n import get_available_locales
import pytz
import datetime
import time
import ckan.lib.helpers as h
from  .constants.constants import ConfigConstants
from ckan import model
from ckan.common import (
    _, ungettext, g, c, request, session, json
)
import ckan.plugins.toolkit as tk
from .vocabulary_utils import dge_harvest_get_vocabulary_element_labels
from .decorators import log_info, log_debug

import logging

log = logging.getLogger(__name__)

def _dge_harvest_list_dataset_field_values(name_field=None):
    '''
    Returns the available values that the given dataset name_field may have
    '''
    result = []
    if name_field is not None:
        dataset = sh.scheming_get_schema('dataset', 'dataset')
        values = sh.scheming_field_by_name(dataset.get('dataset_fields'), name_field) or []
        if values and values['choices']:
            for option in values['choices']:
                if option and option['value']:
                    result.append(option['value'])
    return result

def _dge_harvest_list_nti_field_values(name_field=None):
    '''
    Returns the available values that the given dataset name_field may have
    '''
    result = []
    if name_field is not None:
        values = dsh.dge_get_nti_field_choices(name_field) or []
        if values:
            for option in values:
                if option and option['value']:
                    result.append(option['value'])
    return result

def _dge_harvest_list_dataset_field_labels(name_field=None, value_field=None):
    '''
    Returns the available values that the given dataset name_field may have to the given value_field
    '''
    result = {}
    if name_field is not None:
        choices = dsh.dge_get_nti_field_choices(name_field)
        log.info(f'choices = {choices}')
        for option in choices or []:
            if value_field and option['value'] == value_field:
                return {option.get('value'): {'label' : option.get('label'), 'description': option.get('description'), 'dcat_ap': option.get('dcat_ap'), 'notation': option.get('notation')}}
            else:
                result[option.get('value')] = {'label' : option.get('label'), 'description': option.get('description'), 'dcat_ap': option.get('dcat_ap'), 'notation': option.get('notation')}
    return result


def _dge_harvest_list_resource_field_values(name_field=None):
    '''
    Returns the available values that the given resource name_field may have
    '''
    result = []
    if name_field is not None:
        dataset = sh.scheming_get_schema('dataset', 'dataset')
        values = sh.scheming_field_by_name(dataset.get('resource_fields'),
                name_field) or []
        if values and values['choices']:
            for option in values['choices']:
                if option and option['value']:
                    result.append(option['value'])
    return result

def dge_harvest_list_spatial_coverage_option_value():
    '''
    Returns available values for spatial coverage 
    '''
    spatial_list = []
    values = dsh.dge_get_nti_field_choices('spatial') or []
    if values and len(values) > 0:
        for option in values:
            if option and option['value']:
                spatial_list.append(option['value'])
    result = {}
    for item in spatial_list:
        if item:
            result[item.lower()] = item
    return result

def dge_harvest_dict_spatial_coverage_option_label(value=None):
    '''
    Returns available label for spatial coverage 
    '''
    result = {}
    values = dsh.dge_get_nti_field_choices('spatial') or []
    if values and len(values) > 0:
        for option in values:
            if option and option['value']:
                if value and option['value'] == value:
                    return {option.get('value'): {'label' : option.get('label')}}
                else:
                    result[option.get('value')] = {'label' : option.get('label')}
    return result

def dge_harvest_list_theme_option_value():
    '''
    Returns available values for theme 
    '''
    list = _dge_harvest_list_nti_field_values('theme')
    result = {}
    for item in list:
        if item:
            result[item.lower()] = item
    return result

def dge_harvest_dict_theme_option_label(value=None):
    '''
    Returns available label, descriptions and mappings for theme 
    '''
    result = _dge_harvest_list_dataset_field_labels('theme', value)
    return result

def _dge_harvest_list_format_option_value():
    '''
    Returns available values for format 
    '''
    list = _dge_harvest_list_resource_field_values('format')
    result = {}
    for item in list:
        if item:
            result[item.lower()] = item
    return result

def dge_harvest_is_url(url):
    ''' 
    Returns True if given url is a valid url
    '''
    return dsh.dge_is_url(url)

def dge_harvest_is_uri(uri):
    ''' 
    Returns True if given uri is a valid uri
    '''
    return dsh.dge_is_uri(uri)

def _get_extra_value(extras, key):
    value = None
    if key is None:
        return None
    for extra in extras or []:
        if extra.get('key', '') == key:
            value = extra.get('value', None)
            if value:
                break
            else:
                log.debug(f'Key {key} has not value')
                break
    return value


def dge_harvest_organizations_available():
    '''
    Get a dictionary of active organizations
    
    :returns a dict of active organizations where key is id_minhap (extra C_ID_UD_ORGANICA value) and value is a list [<org_id>, <org_name>] 
        and value is org_id
    '''
    log.info('[dge_harvest_organizations_available] Init method')
    ini = time.time()
    idminhap_organizations = {}
    context = {'ignore_auth': True}
    data_dict = {'all_fields': True, 'include_dataset_count': False, 'include_extras':True}
    organizations = tk.get_action('organization_list')(context, data_dict)
    for organization in organizations or []:
        organization_id = organization.get('id', None)
        organization_name = organization.get('title', None) or organization.get('display_name', '')
        extras = organization.get('extras')
        if organization_id and extras:
            value = _get_extra_value(extras, ConfigConstants.ORG_PROP_ID_UD_ORGANICA)
            if value and value not in idminhap_organizations:
                idminhap_organizations[value] = [organization_id, organization_name]
    log.info(f'[dge_harvest_organizations_available] End method in {time.time() - ini}')
    return idminhap_organizations

def dge_get_organization(org=None, include_datasets=False):
    context = {'model': model, 'session': model.Session, 'ignore_auth': True}
    admin_user = tk.get_action('get_site_user')(context, {})
    if org is None:
        return {}
    try:
        return tk.get_action('organization_show')(
            {'user': admin_user['name']}, {'id': org, 'include_datasets': include_datasets})
    except (logic.NotFound, logic.ValidationError, logic.NotAuthorized):
        return {}

def dge_harvest_get_vocabulary_element_label_dict(uri_element):
    return dge_harvest_get_vocabulary_element_labels(uri_element)