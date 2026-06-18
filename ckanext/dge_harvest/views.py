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

import logging
import ckantoolkit as toolkit
from flask import Blueprint, make_response
from ckan.plugins.toolkit import enqueue_job
from ckan import model
from ckan import plugins as p
import ckan.lib.helpers as h

from ckanext.dge_harvest import tasks
from .constants.constants import ViewsConstants

_ = toolkit._

log = logging.getLogger(__name__)

dgeHarvester = Blueprint("dgeHarvester", __name__,url_prefix=u'/harvest')

def _not_auth_message():
    return _('Not authorized to see this page')

def delete(id):
    try:
        context = {'model': model, 'user': toolkit.c.user}
        context['clear_source'] = toolkit.request.params.get('clear', '').lower() in (u'true', u'1',)
        if context.get('clear_source', False):
            data_dict = {'id': id}
            log.info('Deleting harvest source: %r', data_dict)
            p.toolkit.check_access('harvest_source_delete', context, data_dict)

            p.toolkit.get_action('package_delete')(context, data_dict)
            # We need the id. The name won't work.
            package_dict = p.toolkit.get_action('package_show')(context, data_dict)

            context['id'] = {'id':package_dict['id']}
            del context['model']
            del context['session']

            enqueue_job(tasks.harvest_source_clear_task, queue=ViewsConstants.QUEUE_DELETE_DATASETS, kwargs={"data": context})            
        else:
            return toolkit.abort(403, _not_auth_message())

        return h.redirect_to(
            h.url_for('{0}_search'.format(ViewsConstants.DATASET_TYPE_NAME)))
    except toolkit.ObjectNotFound:
        return toolkit.abort(404, _('Harvest source not found'))
    except toolkit.NotAuthorized:
        return toolkit.abort(401, _not_auth_message())

def clear(id):
    try:
        context = {'model': model, 'user': toolkit.c.user, 'session': model.Session}
        context['id'] = {'id':id}
        del context['model']
        del context['session']
        enqueue_job(tasks.harvest_source_clear_task, queue=ViewsConstants.QUEUE_DELETE_DATASETS, kwargs={"data": context})
        
        return h.redirect_to(
            h.url_for('{0}_search'.format(ViewsConstants.DATASET_TYPE_NAME)))
    
    except toolkit.ObjectNotFound:
        return toolkit.abort(404, _('Harvest source not found'))
    except toolkit.NotAuthorized:
        return toolkit.abort(403, _not_auth_message())
    except Exception as e:
        msg = 'An error occurred: [%s]' % str(e)
        h.flash_error(msg)
    
    return h.redirect_to(
        h.url_for('harvester.admin', id=id))

dgeHarvester.add_url_rule(
    "/delete/<id>",
    view_func=delete, methods=(u'POST', )
)

dgeHarvester.add_url_rule(
    "/clear/<id>",
    view_func=clear, methods=(u'POST', )
)
