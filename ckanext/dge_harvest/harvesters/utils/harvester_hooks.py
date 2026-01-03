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
# -*- coding: 850 -*-
# -*- coding: utf-8 -*-
from ...decorators import log_info

from sqlalchemy import event
from sqlalchemy.orm.attributes import get_history
import ckan.model as model
from ckantoolkit import config
from ckanext.harvest.model import HarvestObject, HarvestJob
import logging
import inspect
from .import_stage_utils import copy_from_old_harvester_graph_not_conforms_packages
from ...utils import generate_graph_uri_and_catalog_uri_from_source_id
from ...constants import DCATAPESHarvesterConstants as HarvesterConstants
from ...rdf_store import RDFStoreComplete


log = logging.getLogger(__name__)


processed_harvest_objects = set()

def register_sqlalchemy_listeners():
    
    @event.listens_for(model.Session, "before_commit")
    def before_commit_listener(session):
        global processed_harvest_objects
        #Detect only modify objects in session
        for instance in session.dirty:
            #handle_harvest_object_to_error_state_when_job_is_aborted(instance)
            if instance and isinstance(instance, HarvestObject):
                if instance.id in processed_harvest_objects:
                    # Harvest object already processes
                    return
                old_state = model.Session.query(HarvestObject.state).filter(HarvestObject.id == instance.id).scalar()
                handle_harvest_object_to_error_state(instance, old_state)

    @event.listens_for(HarvestObject, "after_update")
    def after_update_harvest_object(mapper, connection, target):
        global processed_harvest_objects
        if target.id in processed_harvest_objects:
            # Harvest object already processes
            return
        state_history = get_history(target, "state")
        if state_history.has_changes():
            previous_state = state_history.deleted[0] if state_history.deleted else None
            handle_harvest_object_to_error_state(target, previous_state)

    @event.listens_for(model.Session, "after_commit")
    def after_commit_listener(session):
        global processed_harvest_objects
        processed_harvest_objects.clear()

@log_info
def handle_harvest_object_to_error_state(harvest_object, harvest_object_previous_state):
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    if harvest_object and isinstance(harvest_object, HarvestObject) and harvest_object.state == 'ERROR':
        changed_object_due_to_max_retry_times =  harvest_object.retry_times >= 5
        harvest_job = model.Session.query(HarvestJob).filter(HarvestJob.id == harvest_object.harvest_job_id).first()
        changed_object_due_to_aborted_harvest_job = harvest_job and harvest_job.status == 'Finished' and not harvest_job.finished and harvest_object_previous_state != 'ERROR'
        if (changed_object_due_to_aborted_harvest_job or changed_object_due_to_max_retry_times):
            target_graph_name, catalog_uri_in_target_graph = generate_graph_uri_and_catalog_uri_from_source_id(harvest_object.harvest_source_id)
            source_graph_name = f'{target_graph_name}{HarvesterConstants.SUFFIX_GRAPH_NAME_OF_PREVIOUS_HARVEST}'
            conforms_to_uri = config.get('ckanext.dge_harvest.dcat_ap_es_1_0_0.conforms_to.uri', None)
            rdf_store = rdf_store = RDFStoreComplete(source_graph_name)
            message = f' job {harvest_job.id} has been aborted' if changed_object_due_to_aborted_harvest_job else ' max retry number has been reached'
            log.info(f'{method_log_prefix} Harvest_object with guid = {harvest_object.guid} y current = {harvest_object.current} will be copied from {source_graph_name} to {target_graph_name} because {message}')
            copy_from_old_harvester_graph_not_conforms_packages([harvest_object.guid], source_graph_name, target_graph_name, catalog_uri_in_target_graph, conforms_to_uri, rdf_store)
            del rdf_store
