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

import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import logging
import os
import ckanext.dge_harvest
from ckanext.dge_harvest import helpers
from .logic import (dge_harvest_package_show,
                                       dge_harvest_catalog_show,
                                       dge_harvest_catalog_show_edp,
                                       dge_harvest_catalog_show_csv,
                                       dge_harvest_clear_old_harvest_jobs,
                                       dge_harvest_source_email_job_finished,
                                       dge_harvest_get_running_harvest_jobs,
                                       dge_harvest_auth,
                                       dge_harvest_is_sysadmin)
from ckan.plugins.toolkit import config
from ckan.lib.plugins import DefaultTranslation
import ckanext.dge_harvest.cli as cli
import ckanext.dge_harvest.views as views
from .harvesters.utils.harvester_hooks import register_sqlalchemy_listeners
from collections import OrderedDict

log = logging.getLogger(__name__)


class DgeHarvestPlugin(plugins.SingletonPlugin, DefaultTranslation):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITemplateHelpers, inherit=True)
    plugins.implements(plugins.IActions, inherit=True)
    plugins.implements(plugins.IAuthFunctions, inherit=True)
    plugins.implements(plugins.IClick, inherit=True)
    plugins.implements(plugins.IBlueprint, inherit=True)
    plugins.implements(plugins.ITranslation, inherit=True)
    plugins.implements(plugins.IFacets)

    # ########################### IBlueprint ####################################
    def get_blueprint(self):
        return [views.dgeHarvester]
    
    # ########################### IClick ####################################
    def get_commands(self):
        return cli.get_commands()
    
    # ########################### IActions ####################################
    def get_actions(self):
        return {
            'dge_harvest_package_show': dge_harvest_package_show,
            'dge_harvest_catalog_show': dge_harvest_catalog_show,
            'dge_harvest_catalog_show_edp': dge_harvest_catalog_show_edp,
            'dge_harvest_catalog_show_csv': dge_harvest_catalog_show_csv,
            'dge_harvest_clear_old_harvest_jobs': dge_harvest_clear_old_harvest_jobs,
            'dge_harvest_source_email_job_finished': dge_harvest_source_email_job_finished,
            'dge_harvest_get_running_harvest_jobs': dge_harvest_get_running_harvest_jobs,
        }

    # ########################### IAuthFunctions ##############################
    def get_auth_functions(self):
        return {
            'dge_harvest_package_show': dge_harvest_auth,
            'dge_harvest_catalog_show': dge_harvest_auth,
            'dge_harvest_catalog_show_edp': dge_harvest_auth,
            'dge_harvest_catalog_show_csv': dge_harvest_auth,
            'dge_harvest_clear_old_harvest_jobs': dge_harvest_is_sysadmin,
            'dge_harvest_source_email_job_finished': dge_harvest_is_sysadmin,
            'dge_harvest_get_running_harvest_jobs': dge_harvest_is_sysadmin,
        }

    # ########################### IConfigurer #################################
    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_, 'public')
        toolkit.add_resource('assets', 'dge_harvest')
        register_sqlalchemy_listeners()

    # ########################### ITemplateHelpers ############################

    def get_helpers(self):
        return {
            'dge_harvest_list_spatial_coverage_option_value': helpers.dge_harvest_list_spatial_coverage_option_value,
            'dge_harvest_list_theme_option_value': helpers.dge_harvest_list_theme_option_value,
            '_dge_harvest_list_format_option_value': helpers._dge_harvest_list_format_option_value,
            'dge_harvest_organizations_available': helpers.dge_harvest_organizations_available,
            'dge_harvest_dict_theme_option_label': helpers.dge_harvest_dict_theme_option_label,
            'dge_harvest_dict_spatial_coverage_option_label': helpers.dge_harvest_dict_spatial_coverage_option_label,
            '_dge_harvest_list_nti_field_values': helpers._dge_harvest_list_nti_field_values,
            'dge_harvest_get_vocabulary_element_label_dict': helpers.dge_harvest_get_vocabulary_element_label_dict
            }

    # ########################### ITranslation ############################
    def i18n_directory(self):
        u'''Change the directory of the .mo translation files'''
        return os.path.join(
            os.path.dirname(ckanext.dge_harvest.__file__),
            'i18n'
        )
    
    # ########################### IFacets ############################
    def dataset_facets(self, facets_dict, package_type):

        if package_type != 'harvest':
            return facets_dict

        original_harvest_plugin = plugins.get_plugin('harvest')
        original_harvest_plugin.dataset_facets = lambda facets_dict, package_type: facets_dict

        facets_dict.clear()
        facets_dict['frequency'] =  plugins.toolkit._('Frequency')
        facets_dict['source_type'] = plugins.toolkit._('Source type')
        facets_dict['organization'] = plugins.toolkit._('Organization')

        return facets_dict