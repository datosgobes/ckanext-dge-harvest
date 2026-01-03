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

import logging

from ckan import model
from ckan.common import _
from ckan.plugins.toolkit import config
from ckan.plugins import toolkit
from ckan.lib.search.common import SearchIndexError, make_connection
from ckan.logic import NotFound, check_access, get_action

from ckanext.harvest.model import HarvestSource, HarvestJob

from .rdf_store import RDFStoreDelete
import sqlalchemy as sa
from .constants import HarvesterConstants
from .utils import generate_graph_uri_and_catalog_uri_from_source_id, generate_graph_uri_from_source_and_job

log = logging.getLogger(__name__)

def harvest_source_clear_task(*args, **kwargs):
    '''
    Clears all datasets, jobs and objects related to a harvest source, but
    keeps the source itself. It also clears all graphs in virtuoso if source
    type is dcatapes. This is useful to clean history of long running
    harvest sources to start again fresh.

    :param args: args
    :param kwargs: kwargs
    '''
    context = kwargs.get('data')
    data_dict = context.get('id')
    check_access('harvest_source_clear', context, data_dict)

    harvest_source_id = data_dict.get('id')

    source = HarvestSource.get(harvest_source_id)
    if not source:
        log.error('Harvest source %s does not exist', harvest_source_id)
        raise NotFound('Harvest source %s does not exist' % harvest_source_id)

    harvest_source_id = source.id
    model = context['model']
    
    harvest_job_ids = []
    harvest_job_ids = _get_harvest_job_ids(model, harvest_source_id)

    sql = "BEGIN;"

    sql += f"""
    UPDATE package set state = 'deleted' WHERE id IN (
        SELECT package_id FROM harvest_object
        WHERE harvest_source_id = '{harvest_source_id}'
        and current = true);"""
    sql += f"""
    UPDATE harvest_object set package_id = null
        WHERE harvest_source_id = '{harvest_source_id}';
    """
    sql += """
    COMMIT;
    """
    model.Session.execute(sa.text(sql))
    
    result_clear = get_action('harvest_source_clear')(context, data_dict)

    results = _drop_source_graphs_from_virtuoso(harvest_source_id, harvest_job_ids)

    return result_clear

def harvest_source_graph_clear_task(*args, **kwargs):
    '''
    Clears all graphs in virtuoso if source type is dcatapes.

    :param args: args
    :param kwargs: kwargs
    '''
    context = kwargs.get('data')
    data_dict = context.get('id')
    check_access('harvest_source_clear', context, data_dict)

    harvest_source_id = data_dict.get('id')

    source = HarvestSource.get(harvest_source_id)
    if not source:
        log.error('Harvest source %s does not exist', harvest_source_id)
        raise NotFound('Harvest source %s does not exist' % harvest_source_id)

    harvest_source_id = source.id
    model = context['model']
    
    
    harvest_job_ids = _get_harvest_job_ids(model, harvest_source_id)
    
    results = _drop_source_graphs_from_virtuoso(harvest_source_id, harvest_job_ids)
        
    return {'id': harvest_source_id}

def _drop_source_graphs_from_virtuoso(harvest_source_id, harvest_job_ids):
    '''
    :param harvest_source_id: Harvest source id
    :param harvest_job_ids: List of harvest job ids
    
    Drops all graphs from virtuoso related to the harvest source.
    '''
    if harvest_source_id:
        rdf_store = RDFStoreDelete(None)
        
        source_graph_names_to_delete = _generate_source_graph_names_to_delete(harvest_source_id, harvest_job_ids)
        
        if source_graph_names_to_delete:
            results = []
            for source_graph_name in source_graph_names_to_delete or []:
                rdf_store.update_graph_uri(source_graph_name)
                result = rdf_store.drop_graph()
                if result:
                    results.append(result)
            return results
        return []

def _generate_source_graph_names_to_delete(harvest_source_id, harvest_job_ids):
    '''
    :param harvest_source_id: Harvest source id
    :param harvest_job_ids: List of harvest job ids
    
    Returns generated names for graphs to delete with harvest source id and harvest job ids. Empty list otherwise
    '''
    if harvest_source_id:
        source_graph_uri, _ = generate_graph_uri_and_catalog_uri_from_source_id(harvest_source_id)
        old_source_graph_uri = f'{source_graph_uri}{HarvesterConstants.SUFFIX_GRAPH_NAME_OF_PREVIOUS_HARVEST}'
        source_graph_names_to_delete = []
        source_graph_names_to_delete.append(source_graph_uri)
        source_graph_names_to_delete.append(old_source_graph_uri)
        if harvest_job_ids:
            for harvest_job_id in harvest_job_ids:
                source_graph_names_to_delete.append(generate_graph_uri_from_source_and_job(harvest_source_id, harvest_job_id))
        return source_graph_names_to_delete
    return []

def _get_harvest_job_ids(model, harvest_source_id):
    '''
    :param model: model
    :param harvest_source_id: Harvest source id
    
    Returns a list of job ids if source has them. Empty list otherwise
    '''
    if not model or not harvest_source_id:
        return []
    result = model.Session.query(HarvestJob.id) \
        .filter(HarvestJob.source_id == harvest_source_id) \
        .all()
    return [row[0] for row in result]

def harvest_source_index_clear(context, data_dict):
    '''
    Clears all datasets, jobs and objects related to a harvest source, but
    keeps the source itself.  This is useful to clean history of long running
    harvest sources to start again fresh.

    :param id: the id of the harvest source to clear
    :type id: string
    '''

    check_access('harvest_source_clear', context, data_dict)
    harvest_source_id = data_dict.get('id')

    source = HarvestSource.get(harvest_source_id)
    if not source:
        log.error('Harvest source %s does not exist', harvest_source_id)
        raise NotFound('Harvest source %s does not exist' % harvest_source_id)

    harvest_source_id = source.id

    conn = make_connection()
    query = ''' +%s:"%s" +site_id:"%s" ''' % (
        'harvest_source_id', harvest_source_id, config.get('ckan.site_id'))

    solr_commit = toolkit.asbool(config.get('ckan.search.solr_commit', 'true'))
    if toolkit.check_ckan_version(max_version='2.5.99'):
        try:
            conn.delete_query(query)
            if solr_commit:
                conn.commit()
        except Exception as e:
            log.exception(e)
            raise SearchIndexError(e)
        finally:
            conn.close()
    else:
        try:
            conn.delete(q=query, commit=solr_commit)
        except Exception as e:
            log.exception(e)
            raise SearchIndexError(e)

    return {'id': harvest_source_id}
