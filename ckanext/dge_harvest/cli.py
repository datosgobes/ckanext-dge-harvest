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

# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
import click
import time

from ckan import model
import ckan.plugins.toolkit as tk
import ckanext.dge_harvest.utils as utils
from .rdf_store  import RDFStoreException

def get_commands():
    return [dge_harvester]

@click.group("dge_harvester")
def dge_harvester():
    '''Harvests remotely mastered metadata

    Usage:

      dge_harvester catalog_rdf [{limit_num_datasets}]
        - create a RDF serialization of the catalog.
          Create a file specified in config property 'ckanext.dge_harvest.rdf.filepath'
          or in '/tmp/catalog.rdf' if not exists the property.
          A limit number of datastets can be specified in args. All datasets by default.

      dge_harvester catalog_csv [{limit_num_datasets}]
        - create a RDF serialization of the catalog.
          Create a file specified in config property 'ckanext.dge_harvest.csv.filepath'
          or in '/tmp/catalog.csv' if not exists the property.
          A limit number of datastets can be specified in args. All datasets by default.

      dge_harvester clear_old_harvest_jobs [{source-id}]
        - If no source id is given the history for all jobs that have finished over one month ago
          except the last job by source if it has finished makes more than one month will be cleared.
          Clears the jobs, objects, object_errors and gather_error related to a harvest job.
          If a source id is given, it only clears the history of the harvest source with the given source id.
          The datasets imported from the harvest source will NOT be deleted!!!

     dge_harvester get_running_harvest_jobs [{minutes}]
        - Gets running harvest_jobs that were created more than {minutes} minutes ago
          and send and email

    The commands should be run from the ckanext-dge-harvest directory and expect
    a development.ini file to be present. Most of the time you will
    specify the config explicitly though:
        ckan -c .../default/ckan.ini dge_harvester catalog_rdf [{limit_num_datasets}]
        ckan -c .../default/ckan.ini dge_harvester catalog_rdf_EDP [{limit_num_datasets}]
        ckan -c .../default/ckan.ini dge_harvester catalog_csv [{limit_num_datasets}]
        ckan -c .../default/ckan.ini dge_harvester [{source-id}]
        ckan -c .../default/ckan.ini dge_harvester {minutes}

    '''
    pass
def _set_context():
    context = {'model': model, 'session': model.Session, 'ignore_auth': True}
    admin_user = tk.get_action('get_site_user')(context, {})
    return {
        'model': model,
        'session': model.Session,
        'user': admin_user['name'],
        'ignore_auth': True,
    }

@dge_harvester.command("catalog_rdf")
@click.option("--filename", type=click.STRING, default=None, help='Filename in which the export is generated')
@click.option("--compress", is_flag = True, type=click.BOOL, help='If is included, the file will be compress in .gz')
@click.pass_context
def catalog_rdf(ctx, filename, compress):

    method_log_prefix = '[CliDgeHarvest][generate_catalog]'
    click.secho('{0} Init method. Inputs: _format={1}'.format(method_log_prefix,'rdf'))

    flask_app = ctx.meta["flask_app"]

    with flask_app.test_request_context():
        context = _set_context()
        data_dict = {
            'format': 'rdf',
            'filename': filename,
            'compress' : compress
        }
        catalog = tk.get_action('dge_harvest_catalog_show')(context,data_dict)

    click.secho('{0} End method'.format(method_log_prefix))

@dge_harvester.command("catalog_csv")
@click.option("--filename", type=click.STRING, default=None, help='Filename in which the export is generated')
@click.option("--compress", is_flag = True, type=click.BOOL, help='If is included, the file will be compress in .gz')
@click.pass_context
def catalog_csv(ctx, filename, compress):

    method_log_prefix = '[CliDgeHarvest][generate_catalog]'
    click.secho('{0} Init method. Inputs: _format={1}'.format(method_log_prefix,'csv'))

    flask_app = ctx.meta["flask_app"]

    with flask_app.test_request_context():
        context = _set_context()
        data_dict = {
            'format': 'csv',
            'filename': filename,
            'compress' : compress
        }
        catalog = tk.get_action('dge_harvest_catalog_show_csv')(context,data_dict)

    click.secho('{0} End method'.format(method_log_prefix))

@dge_harvester.command("catalog_rdf_EDP")
@click.option("--filename", type=click.STRING, default=None, help='Filename in which the export is generated')
@click.option("--compress", is_flag = True, type=click.BOOL, help='If is included, the file will be compress in .gz')
@click.pass_context
def catalog_rdf_EDP(ctx, filename, compress):

    method_log_prefix = '[CliDgeHarvest][generate_catalog]'
    click.secho('{0} Init method. Inputs: _format={1}'.format(method_log_prefix,'rdf'))

    flask_app = ctx.meta["flask_app"]

    with flask_app.test_request_context():
        context = _set_context()
        data_dict = {
            'format': 'rdf',
            'filename': filename,
            'compress' : compress
        }
        catalog = tk.get_action('dge_harvest_catalog_show_edp')(context,data_dict)

    click.secho('{0} End method'.format(method_log_prefix))

@dge_harvester.command("clear_old_harvest_jobs")
@click.argument(u"source_id", default=None, required=False)
@click.pass_context
def clear_old_harvest_jobs(ctx, source_id):
    method_log_prefix = '[CliDgeHarvest][clear_old_harvest_jobs]'
    click.secho('{0} Init method'.format(method_log_prefix))

    flask_app = ctx.meta["flask_app"]

    with flask_app.test_request_context():
        context = _set_context()

        if source_id is not None:
            cleared_sources = tk.get_action('dge_harvest_clear_old_harvest_jobs')(context,{'id':source_id})
        else:
            cleared_sources = tk.get_action('dge_harvest_clear_old_harvest_jobs')(context,{})

        if cleared_sources:
            sources = ''
            for item in cleared_sources:
                click.secho('Cleared job history for harvest source: {0}'.format(item.get('name', item.get('id', ''))))
        else:
            click.echo('Cleared job history for any harvest source')

    click.secho('{0} End method'.format(method_log_prefix))

@dge_harvester.command("get_running_harvest_jobs")
@click.argument(u"minutes", type=click.INT, default=-1)
@click.pass_context
def get_running_harvest_jobs(ctx, minutes):
    method_log_prefix = '[CliDgeHarvest][get_running_harvest_job]'
    click.secho('{0} Init method'.format(method_log_prefix))

    flask_app = ctx.meta["flask_app"]

    with flask_app.test_request_context():

        context = _set_context()

        if minutes <= 0:
            click.secho('{0} Please provide a valid value for minutes'.format(method_log_prefix))
            sys.exit(1)

        harvest_jobs = tk.get_action('dge_harvest_get_running_harvest_jobs')(context,{'minutes':minutes})
        if harvest_jobs:
            for job in harvest_jobs:
                click.secho('''Job with id {0} for harvest source {1} has been running longer than the configured threshold.
                            '''.format(job.get('job_id'), job.get('source_name')))
        else:
            click.echo('''No job has been running longer than the configured threshold.''')

    click.secho('{0} End method'.format(method_log_prefix))

@dge_harvester.command("update_dge_harvester_vocabularies")
@click.argument(u"havester_config_file_path", metavar=u"HAVERTER_CONIG_FILE_PATH", required=True)
def update_dge_harvester_vocabularies(havester_config_file_path):
    """Remove the vocabularies graph and creates it again with the updated vocabularies
    Args:
        havester_config_file_path: harvester config file path for all properties related to this federation. 
        The command use three properties of this file:
            - vocabularies.graph_name: roperty that contains the graph name where the vocabularies will be stores
            - vocabularies.uris: property that contains the list of vocabularies URIs
            - vocabularies.uris.different_download_uri: property that contains the vocabularies whose download uri is different from the vocabulary URI. Format <vocabulary_uri>|<download_uri>
    """
    method_log_prefix = '[CliDgeHarvest][update_dge_harvester_vocabularies]'
    from .vocabulary_utils import dge_harvester_update_vocabularies
    click.secho('{0} Init method'.format(method_log_prefix))
    ini = time.time()
    try:
        result = dge_harvester_update_vocabularies(havester_config_file_path)
    except (ValueError, RDFStoreException) as e:
        click.secho(str(e))
        sys.exit(1)
    
    click.secho(f'{method_log_prefix} End method in {(time.time() - ini)} segundos. Result: \n{result}')
    
@dge_harvester.command("dge_harvest_update_vocabulary_element_labels")
@click.argument(u"vocabulary_element_uri", metavar=u"VOCABULARY_ELEMENT_URI", required=True)
@click.argument(u"havester_config_file_path", metavar=u"HAVERTER_CONIG_FILE_PATH", required=False)
def dge_harvest_update_vocabulary_element_labels(vocabulary_element_uri, havester_config_file_path=None):
    """Remove first and then add the skos:prefLabel of a vocabulary element 
    Args:
        havester_config_file_path: harvester config file path for all properties related to this federation. 
        The command use one properties of this file:
            - vocabularies.graph_name: roperty that contains the graph name where the vocabularies will be stores
    """
    from .vocabulary_utils import dge_harvest_update_vocabulary_element_labels
    method_log_prefix = '[CliDgeHarvest][get_dge_harvester_vocabulary_element_labels]'
    click.secho('{0} Init method'.format(method_log_prefix))
    ini = time.time()
    try:
        result = dge_harvest_update_vocabulary_element_labels(vocabulary_element_uri, havester_config_file_path,)
    except (ValueError, RDFStoreException) as e:
        click.secho(str(e))
        sys.exit(1)
    click.secho(f'{method_log_prefix} End method in {(time.time() - ini)} segundos.Result: \n{result}')

@dge_harvester.command("dge_harvest_delete_vocabulary_element_labels")
@click.argument(u"vocabulary_element_uri", metavar=u"VOCABULARY_ELEMENT_URI", required=True)
@click.argument(u"havester_config_file_path", metavar=u"HAVERTER_CONIG_FILE_PATH", required=False)
def dge_harvest_delete_vocabulary_element_labels(vocabulary_element_uri, havester_config_file_path=None):
    """Remove add the skos:prefLabel of a vocabulary element 
    Args:
        havester_config_file_path: harvester config file path for all properties related to this federation. 
        The command use one properties of this file:
            - vocabularies.graph_name: roperty that contains the graph name where the vocabularies will be stores
    """
    from .vocabulary_utils import dge_harvest_delete_vocabulary_element_labels
    method_log_prefix = '[CliDgeHarvest][get_dge_harvester_vocabulary_element_labels]'
    click.secho('{0} Init method'.format(method_log_prefix))
    ini = time.time()
    try:
        dge_harvest_delete_vocabulary_element_labels(vocabulary_element_uri, havester_config_file_path)
    except (ValueError, RDFStoreException) as e:
        click.secho(str(e))
        sys.exit(1)
    click.secho(f'{method_log_prefix} End method in {(time.time() - ini)} segundos.')