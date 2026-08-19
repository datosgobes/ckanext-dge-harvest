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

"""Helpers to persist validation messages during gather stage.

This module centralizes the repetitive reporting logic used while processing
catalog, dataset, dataservice and distribution validation results.

The helpers do not execute validations and do not classify messages. Their
responsibility is limited to adapting already known validation outcomes into
structured harvest-report messages and delegating persistence to the common
report helpers.

Keeping this logic outside the harvester reduces the size and complexity of
``gather_stage()`` while preserving a single reporting strategy for SHACL,
controlled vocabularies and other validation-related results.
"""

from ckanext.dge_harvest.services.report.harvest_report_dimensions import (
    REPORT_PHASE_VALIDATION,
    REPORT_ORIGIN_DCAT_AP_ES
)

from ckanext.dge_harvest.services.report.harvest_report_vocabulary_adapter import (
    adapt_vocabulary_result_to_report_message
)

from ckanext.dge_harvest.services.report.harvest_report_shacl_adapter import (
    adapt_shacl_result_to_report_message
)

from ckanext.dge_harvest.services.report.harvest_report_common_classifier import (
 get_common_info_message_code,
 VALIDATION_REASON_DELETED_NO_VALID_RESOURCE
)

from ckanext.dge_harvest.services.report.harvest_report_error_writer import (
    save_adapted_gather_report_message,
)

from typing import List, Dict
from dataclasses import dataclass, field
    
from ckanext.harvest.model import HarvestJob


ENTITY_TYPE_CATALOG = "catalog"
ENTITY_TYPE_DATASET = "dataset"
ENTITY_TYPE_DATASERVICE = "dataservice"
ENTITY_TYPE_DISTRIBUTION = "distribution"

ENTITY_TYPE_NAMES_ES = {
    ENTITY_TYPE_CATALOG: "catálogo",
    ENTITY_TYPE_DATASET: "conjunto de datos",
    ENTITY_TYPE_DATASERVICE: "servicio de datos",
    ENTITY_TYPE_DISTRIBUTION: "distribución",
}

ENTITY_TYPE_ARTICLES_ES = {
    ENTITY_TYPE_CATALOG: "el",
    ENTITY_TYPE_DATASET: "el",
    ENTITY_TYPE_DATASERVICE: "el",
    ENTITY_TYPE_DISTRIBUTION: "la",
}

ALLOWED_DCAT_ENTITY_TYPES = (
    ENTITY_TYPE_CATALOG,
    ENTITY_TYPE_DATASET, 
    ENTITY_TYPE_DATASERVICE,
    ENTITY_TYPE_DISTRIBUTION
)

@dataclass
class ValidationReportMessages():
    vocabulary_messages: List[str] = field(default_factory=list)
    shacl_messages: List[Dict[str, str]] = field(default_factory=dict)
    deleted_resource: bool = False


class DcatGatherStageValidationMessageHelperMixin(object):
    """Validation-result reporting helpers for gather stage.

    This mixin provides reusable methods to persist validation messages
    associated with catalogs, datasets, dataservices and distributions.

    The mixin assumes that the caller already knows:
        - the validation type (SHACL, vocabulary, etc.)
        - the affected resource
        - the structured report category
        - the message code when applicable

    The mixin does not perform validation itself.
    """
    
    
    def _save_report_message(self, entity_type:str, entity_uri:str, report_messages: ValidationReportMessages, harvest_job: HarvestJob, default_payload: dict[str,object]={}):

        if not report_messages or not entity_type or entity_type not in ALLOWED_DCAT_ENTITY_TYPES:
            return

        self._save_vocabulary_report_message(
            vocabulary_messages=report_messages.vocabulary_messages, 
            entity_type=entity_type, 
            entity_uri=entity_uri, 
            harvest_job=harvest_job, 
            default_payload=default_payload)
        
        self._save_shacl_report_message(
           shacl_messages=report_messages.shacl_messages, 
            entity_type=entity_type, 
            entity_uri=entity_uri, 
            harvest_job=harvest_job, 
            default_payload=default_payload)

        self._save_deleted_entity_report_message(
            deleted_resource=report_messages.deleted_resource,
            entity_type=entity_type, 
            entity_uri=entity_uri, 
            harvest_job=harvest_job, 
            default_payload=default_payload)


    def _save_vocabulary_report_message(self, vocabulary_messages: List[str], entity_type: str, entity_uri: str, harvest_job: HarvestJob, default_payload: dict[str,object]={}):
        if not harvest_job or not vocabulary_messages or not entity_type or not entity_uri or entity_type not in ALLOWED_DCAT_ENTITY_TYPES:
            return
        for message in vocabulary_messages or []:
            adapted_message = adapt_vocabulary_result_to_report_message(
                result = message,
                entity_type=entity_type,
                entity_uri=entity_uri,
                resource_uri=entity_uri,
                metadata_uri=None,
                extra_payload={
                    **default_payload,
                    f"{entity_type}_uri": entity_uri
                },
                origin=REPORT_ORIGIN_DCAT_AP_ES,
            )
            
            save_adapted_gather_report_message(
                harvest_job=harvest_job,
                adapted_message=adapted_message,
            )


    def _save_shacl_report_message(self, shacl_messages: List[Dict[str,str]], entity_type: str, entity_uri: str, harvest_job, default_payload: dict[str,object]={}):
        if not harvest_job or not shacl_messages or not entity_type or not entity_uri or entity_type not in ALLOWED_DCAT_ENTITY_TYPES:
            return
        for message in shacl_messages or []:
            adapted_message = adapt_shacl_result_to_report_message(
                result = message,
                entity_type=entity_type,
                resource_uri=entity_uri,
                extra_payload={
                    **default_payload,
                },
                origin=REPORT_ORIGIN_DCAT_AP_ES,
            )
            
            save_adapted_gather_report_message(
                harvest_job=harvest_job,
                adapted_message=adapted_message,
            )

    def _save_deleted_entity_report_message(self, deleted_resource: bool, entity_type: str, entity_uri: str, harvest_job, default_payload: dict[str,object]={}):
        if not harvest_job or not entity_type or not entity_uri or entity_type not in ALLOWED_DCAT_ENTITY_TYPES or not deleted_resource:
            return

        message = f"Se ha eliminado {ENTITY_TYPE_ARTICLES_ES.get(entity_type, '')} {ENTITY_TYPE_NAMES_ES.get(entity_type, entity_type)} {entity_uri} porque no cumple con las especificaciones."
        kind=f"not_conform_{entity_type}_deletion",
        reason=VALIDATION_REASON_DELETED_NO_VALID_RESOURCE,

        self._save_common_structured_gather_report_info(
            harvest_job=harvest_job,
            raw_message= message,
            display_message=message,
            phase=REPORT_PHASE_VALIDATION,
            origin=REPORT_ORIGIN_DCAT_AP_ES,
            kind=kind,
            reason=reason,
            resource_uri=entity_uri,
            payload={
                **default_payload,
                "entity_type": entity_type
            },
            message_code=get_common_info_message_code(phase=REPORT_PHASE_VALIDATION,reason=VALIDATION_REASON_DELETED_NO_VALID_RESOURCE)
        )

    def _save_catalog_report_messages(self, report_messages: ValidationReportMessages, entity_uri: str, harvest_job: HarvestJob, default_payload: dict[str,object]={}):
        self._save_report_message(
            report_messages=report_messages, 
            entity_type=ENTITY_TYPE_CATALOG, 
            entity_uri=entity_uri, 
            harvest_job=harvest_job, 
            default_payload=default_payload)

    def _save_dataservice_report_messages(self, report_messages: ValidationReportMessages, entity_uri: str, harvest_job: HarvestJob, default_payload: dict[str,object]={}):
        self._save_report_message(
            report_messages=report_messages, 
            entity_type=ENTITY_TYPE_DATASERVICE, 
            entity_uri=entity_uri, 
            harvest_job=harvest_job, 
            default_payload=default_payload)

    def _save_dataset_report_messages(self, report_messages: ValidationReportMessages, entity_uri: str, harvest_job: HarvestJob, default_payload: dict[str,object]={}):
        self._save_report_message(
            report_messages=report_messages, 
            entity_type=ENTITY_TYPE_DATASET, 
            entity_uri=entity_uri, 
            harvest_job=harvest_job, 
            default_payload=default_payload)

    def _save_distribution_report_messages(self, report_messages: ValidationReportMessages, entity_uri: str, harvest_job: HarvestJob, default_payload: dict[str,object]={}):
        """Persist validation messages owned by one distribution."""
        self._save_report_message(
            report_messages=report_messages,
            entity_type=ENTITY_TYPE_DISTRIBUTION,
            entity_uri=entity_uri,
            harvest_job=harvest_job,
            default_payload=default_payload)
