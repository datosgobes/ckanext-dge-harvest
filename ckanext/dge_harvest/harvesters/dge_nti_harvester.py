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

import json
import logging
import hashlib
import uuid
import inspect

import ckan.logic as logic
import ckan.model as model
import ckan.plugins as p

from ckanext.dcat.processors import RDFParserException
from ckanext.harvest.model import HarvestObject, HarvestJob

from .dge_harvester import DGERDFHarvester, GatherRdfFormatConfigError, PrepareGatherContextError, HarvesterConstants
from .dge_harvester_exceptions import (
    GatherConnectionError,
    GatherFileNotFoundError,
    GatherFileTooLargeError,
    GatherHTTPError,
    GatherHookError,
    GatherParserError,
    GatherTimeoutError,
)
from ckanext.dge_harvest.processors import DGENTIRDFParser
from ckanext.dge_harvest.constants.nti_constants import NTICatalogConstants, NTIHarvesterConstants, NTIDatasetConstants
from ckanext.dge_harvest.decorators import log_debug, log_info
from ckanext.dge_harvest.constants import (
    CommonPackageConstants,
    HarvestMessageDetailConstants,
)
from ckanext.dge_harvest.services.report.harvest_report_dimensions import (
    REPORT_PHASE_SETUP,
    REPORT_PHASE_DOWNLOAD,
    REPORT_PHASE_VALIDATION,
    REPORT_PHASE_FALLBACK,
    REPORT_PHASE_IMPORT,
    REPORT_CATEGORY_TECHNICAL
)
from ckanext.dge_harvest.services.report.harvest_report_technical_classifier import (
    get_technical_error_message_code,
    get_technical_warning_message_code,
    get_technical_info_message_code,
    IMPORT_REASON_EMPTY_OBJECT_CONTENT, 
    IMPORT_REASON_WRONG_PARSE_LOAD_OBJECT_CONTENT, 
)
from ckanext.dge_harvest.services.report.harvest_report_common_classifier import (
    get_common_error_message_code,
    get_common_info_message_code,
    get_common_warning_message_code,
    COMMON_REASON_JOB_RENEWED_BEFORE_FINISH,
    COMMON_REASON_ABORTED_JOB,
    VALIDATION_REASON_WARNING_PARSE_CATALOG,
    VALIDATION_REASON_INVALID_PARSE_CATALOG,
    VALIDATION_REASON_WARNING_PARSE_DATASET,
    VALIDATION_REASON_INVALID_PARSE_DATASET,
)
from ckanext.dge_harvest.harvesters.utils.report.gather_stage_report_helper import (
    NtiGatherStageReportHelperMixin,
)
from ckanext.dge_harvest.harvesters.utils.report.import_stage_report_helper import (
    NtiImportStageReportHelperMixin,
)
from .constants.harvest_report_constants import (
    GATHER_JOB_ABORTED_RAW_MESSAGE,
    GATHER_JOB_RENEWED_RAW_MESSAGE
)
from ckanext.dge_harvest.services.report.harvest_report_catalog_messages import(
    append_support_message
)
log = logging.getLogger(__name__)

class DGENTIRDFHarvester(NtiGatherStageReportHelperMixin,
                         NtiImportStageReportHelperMixin,
                         DGERDFHarvester):

    def info(self):
        return {
            'name': 'dge_rdf',
            'title': 'dge_rdf',
            'description': 'Harvester for DGE datasets from an RDF graph',
            'order': 20
        }
    
    def _check_has_job_been_aborted(self, harvest_job:HarvestJob, reason:str, phase:str) -> bool:
        if harvest_job and self._has_job_been_aborted(harvest_job):
            log.info(f'Harvest_job with {harvest_job.id} has been aborted before its gather_stage started or finished.')
            current_reason = reason or COMMON_REASON_ABORTED_JOB
            self._save_common_structured_gather_report_info(
                harvest_job=harvest_job,
                raw_message=GATHER_JOB_ABORTED_RAW_MESSAGE,
                phase=phase or REPORT_PHASE_FALLBACK,
                kind="gather_job_aborted",
                reason=current_reason,
                message_code = get_common_info_message_code(phase=phase, reason=current_reason),
                payload=None,
            )
            return True
        return False

    def _resolve_gather_stage_context_and_handle_early_exit(
        self,
        harvest_job,
        method_log_prefix,
    ):
        """Freeze gather context and stop early for renewed or aborted jobs."""
        current_phase = REPORT_PHASE_SETUP
        source_url = harvest_job.source.url
        try:
            gather_stage_context = self._prepare_gather_context(harvest_job)
            source_url = gather_stage_context.get(HarvesterConstants.SOURCE_URL_AT_RUN, source_url)
        except PrepareGatherContextError as exc:
            log.error(
                '%s Error preparing gather context for harvest job %s: %s',
                method_log_prefix,
                harvest_job.id,
                exc,
            )
            self._save_technical_structured_gather_report_error(
                exception = exc,
                harvest_job=harvest_job,
                raw_message="Error al preparar el contexto del job.",
                phase=current_phase,
                kind="gather_context_error",
                reason=None,
                message_code=get_technical_error_message_code(phase=current_phase, reason=None, exception=exc),
                payload=None,
            )
            return None

        if harvest_job.gather_finished is not None:
            log.info(f'{method_log_prefix} End method 0. The gathering stage took more than 2 hours, and the harvest job was renewed before it was finished. Returns: []')
            self._save_common_structured_gather_report_info(
                harvest_job=harvest_job,
                raw_message=GATHER_JOB_RENEWED_RAW_MESSAGE,
                phase=current_phase,
                kind="gather_job_renewed",
                reason=COMMON_REASON_JOB_RENEWED_BEFORE_FINISH,
                message_code = get_common_info_message_code(phase=current_phase, reason=COMMON_REASON_JOB_RENEWED_BEFORE_FINISH),
                payload=None,
            )
            return None

        if self._check_has_job_been_aborted(harvest_job, "aborted_before_start", current_phase):
            return None

        return gather_stage_context

    @log_info
    def gather_stage(self, harvest_job):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        effective_url = None
        current_phase = REPORT_PHASE_SETUP
        try:
            gather_stage_context = self._resolve_gather_stage_context_and_handle_early_exit(
                harvest_job=harvest_job,
                method_log_prefix=method_log_prefix,
            )
            if not gather_stage_context:
                return []

            effective_url = gather_stage_context[HarvesterConstants.SOURCE_URL_AT_RUN]

            try:
                rdf_format, default_catalog_language = self._get_rdf_format_config(gather_stage_context[HarvesterConstants.SOURCE_CONFIG_AT_RUN])
            except GatherRdfFormatConfigError as e:
                self._save_technical_structured_gather_report_error(
                    exception=e,
                    harvest_job=harvest_job,
                    display_message = "Error al obtener el formato de la configuración de la fuente de federación.",
                    raw_message= "Error al obtener el formato de la configuración de la fuente de federación.",
                    phase=current_phase,
                    category=REPORT_CATEGORY_TECHNICAL,
                    kind="rdf_format_config_error",
                    reason = None,
                    message_code=get_technical_error_message_code(phase=current_phase, reason=None, exception=e),
                    payload=None,
                )
                return []

            # Get file contents of first page
            next_page_url = effective_url
            log.info(f'{method_log_prefix} Init harvest for harvest_source with url {next_page_url}')

            guids_in_source = []
            object_ids = []
            last_content_hash = None
            self._names_taken = []
            visited_urls = set()
            current_phase = REPORT_PHASE_DOWNLOAD
            while next_page_url is not None and next_page_url not in visited_urls:
                try:
                    # run before_download of plugins that implements IDCATRDFHarvester
                    next_page_url = self._run_before_downloads(harvest_job, next_page_url)
                    if not next_page_url:
                        log.debug(f'{method_log_prefix} End method 1. Returns: []')
                        return []

                    content, rdf_format, result = self._get_content_and_type(next_page_url, harvest_job, 1, content_type=rdf_format)
                    if result and result.infos:
                        for info_message in result.infos:
                            self._save_structured_gather_report_info(
                                exception = info_message,
                                harvest_job=harvest_job,
                                raw_message=info_message.display_message or info_message.raw_message,
                                display_message=info_message.raw_message,
                                phase=current_phase,
                                kind=info_message.report_kind,
                                reason=info_message.report_reason,
                                payload=info_message.context,
                                category=info_message.category,
                                message_code = get_common_info_message_code(phase=current_phase, exception=info_message)
                            )
                    if result and result.warnings:
                        for warn_message in result.warnings:
                            self._save_structured_gather_report_warning(
                                exception = warn_message,
                                harvest_job=harvest_job,
                                raw_message=warn_message.display_message or warn_message.raw_message,
                                display_message=warn_message.raw_message,
                                phase=current_phase,
                                kind=warn_message.report_kind,
                                reason=warn_message.report_reason,
                                payload=warn_message.context,
                                category=warn_message.category,
                                message_code = get_common_warning_message_code(phase=current_phase, exception=warn_message)
                            )

                    content_hash = hashlib.md5()
                    if content:
                        content_hash.update(content.encode('utf8'))

                    if last_content_hash:
                        if content_hash.digest() == last_content_hash.digest():
                            log.warning('Remote content was the same even when using a paginated URL, skipping')
                            break
                    else:
                        last_content_hash = content_hash

                    # TODO: store content?
                    # run after_download of plugins that implements IDCATRDFHarvester
                    content = self._run_after_downloads(harvest_job, content, next_page_url)
                    if not content:
                        log.debug(f'{method_log_prefix} End method 2. Returns: []')
                        return []

                    parser = DGENTIRDFParser(profiles=['dge_nti_profile'])
                    parser.parse(content, _format=rdf_format)
                    # run after_download of plugins that implements IDCATRDFHarvester
                    parser = self._run_after_parsings(harvest_job, parser, next_page_url)
                    if parser is None:
                        log.debug(f'{method_log_prefix} End method 5. Returns: []')
                        return []
                except (
                    GatherFileNotFoundError,
                    GatherFileTooLargeError,
                    GatherHTTPError,
                    GatherTimeoutError,
                ) as exc:
                    log.exception(f'{method_log_prefix} Exception getting content and tpye of {next_page_url}')
                    self._save_common_structured_gather_report_error(
                        exception=exc,
                        harvest_job=harvest_job,
                        raw_message=exc.raw_message,
                        phase=current_phase,
                        kind=exc.report_kind,
                        reason=exc.report_reason,
                        message_code=get_common_error_message_code(phase=current_phase, exception=exc),
                        display_message=exc.display_message,
                        payload=exc.context,
                    )
                    return []
                except (
                    GatherConnectionError,
                    GatherHookError,
                ) as exc:
                    log.exception(f'{method_log_prefix} Exception getting content and tpye of {next_page_url}')
                    self._save_technical_structured_gather_report_error(
                        exception=exc,
                        harvest_job=harvest_job,
                        raw_message=exc.raw_message,
                        phase=current_phase,
                        kind=exc.report_kind,
                        reason=exc.report_reason,
                        message_code=get_technical_error_message_code(phase=current_phase, reason=None, exception=exc),
                        display_message=exc.display_message or "Se ha producido un error inesperado en la obtención del fichero de la federación.",
                        payload=exc.context,
                    )
                    return []
                except (RDFParserException, SyntaxError) as e:
                    log.exception(f'{method_log_prefix} Error parsing the content of {next_page_url}. Exception {type(e).__name__}: {str(e)}')
                    self._save_common_structured_gather_report_error(
                        exception=e,
                        harvest_job=harvest_job,
                        raw_message=HarvesterConstants.CATALOG_PARSER_ERROR_URL.format(next_page_url, str(e)),
                        phase=current_phase,
                        kind="catalog_parser_error",
                        message_code=get_common_error_message_code(phase=current_phase, exception=e),
                        display_message=e.display_message or "Error al parsear el contenido del RDF. Revisa que el RDF está bien formado en el formato indicado en la fuente de federación.",
                        payload=None,
                    )
                    return []
                except (GatherParserError) as e:
                    log.exception(f'{method_log_prefix} Error parsing the content of {next_page_url}. Exception {type(e).__name__}: {str(e)}')
                    self._save_common_structured_gather_report_error(
                        exception=e,
                        harvest_job=harvest_job,
                        raw_message=e.raw_message,
                        phase=current_phase,
                        kind=e.report_kind,
                        reason=e.report_reason,
                        message_code=get_common_error_message_code(phase=current_phase, exception=e),
                        display_message=e.display_message,
                        payload=e.context,
                    )
                    return []
                
                except Exception as e:
                    log.exception(f'{method_log_prefix} Unexpected error parsing the content of {next_page_url}. Unexpected exception {type(e).__name__}: {str(e)}')
                    gather_error = HarvesterConstants.CATALOG_PARSER_ERROR_URL.format(next_page_url, e)
                    self._save_technical_structured_gather_report_error(
                            exception=e,
                            harvest_job=harvest_job,
                            raw_message=gather_error,
                            phase=current_phase,
                            category=REPORT_CATEGORY_TECHNICAL,
                            kind="catalog_parser_error",
                            resource_uri=next_page_url,
                            display_message="Se ha producido un error en la obtención del fichero de la federación.",
                            message_code=get_technical_error_message_code(phase=current_phase, reason=None, exception=e),
                        )
                    return []


                # ETAPA DE VALIDACIÓN
                current_phase = REPORT_PHASE_VALIDATION
                # Finish method if job has been aborted
                if self._check_has_job_been_aborted(harvest_job, 'aborted_before_validation', REPORT_PHASE_VALIDATION):
                    return []
                
                catalog_errors = 0
                catalog_warnings = 0
                catalog_uri = None
                
                try:
                    for catalog in parser.catalogs():
                        entity_type = "catalog"
                        catalog_errors = catalog[NTICatalogConstants.KEY_CATALOG_ERRORS]
                        catalog_warnings = catalog[NTICatalogConstants.KEY_CATALOG_WARNINGS]
                        catalog_error_details = catalog.get(
                            CommonPackageConstants.KEY_ERROR_DETAILS,
                            [],
                        )
                        catalog_warning_details = catalog.get(
                            CommonPackageConstants.KEY_WARNING_DETAILS,
                            [],
                        )
                        catalog_uri = catalog.get(NTICatalogConstants.KEY_CATALOG_URI, None)

                        # get owner_org of harvest_job
                        owner_org_catalog = None
                        source_catalog = model.Package.get(harvest_job.source.id)
                        if source_catalog.owner_org:
                            owner_org_catalog = source_catalog.owner_org

                        # check if catalog_publisher is harvest_source_org
                        if catalog.get(NTICatalogConstants.KEY_CATALOG_PUBLISHER) and \
                                catalog.get(NTICatalogConstants.KEY_CATALOG_PUBLISHER) != owner_org_catalog:
                            if not catalog_errors:
                                catalog_errors = []
                            errormsg = NTIHarvesterConstants.UNEXPECTED_PUBLISHER_CATALOG_OWNER_SOURCE
                            log.info(f"{method_log_prefix} Adding catalog error {errormsg}")
                            catalog_errors.append(errormsg)

                        total_catalog_errors = len(catalog_errors) if catalog_errors else 0
                        total_catalog_warnings = len(catalog_warnings) if catalog_warnings else 0

                        if catalog_warnings and len(catalog_warnings) > 0:
                            num = 0
                            reason = VALIDATION_REASON_WARNING_PARSE_CATALOG
                            for catalog_warning in catalog_warnings:
                                num += 1
                                if (num <= DGERDFHarvester.MAX_NUM):
                                    warnmsg = NTIHarvesterConstants.CATALOG_VALIDATION_WARNING.format(catalog_warning)
                                    if next_page_url:
                                        warnmsg = NTIHarvesterConstants.CATALOG_VALIDATION_WARNING_URL.format(next_page_url, catalog_warning)
                                    warning_detail = self._get_detail_by_index(
                                        catalog_warning_details,
                                        num - 1,
                                    )
                                    log.info(f"{method_log_prefix} Saving gather_error - {warnmsg} {harvest_job}")
                                    warn_entity_type = (warning_detail or {}).get(HarvestMessageDetailConstants.KEY_SCOPE) or entity_type
                                    self._save_common_structured_gather_report_warning(
                                        exception = (warning_detail or {}).get(HarvestMessageDetailConstants.KEY_EXCEPTION),
                                        harvest_job=harvest_job,
                                        display_message=(warning_detail or {}).get(HarvestMessageDetailConstants.KEY_MESSAGE) or warn,
                                        phase=current_phase,
                                        raw_message=(warning_detail or {}).get(HarvestMessageDetailConstants.KEY_MESSAGE) or warn,
                                        kind=f"{warn_entity_type}_validation_paser_warning",
                                        reason=reason,
                                        resource_uri=(warning_detail or {}).get(HarvestMessageDetailConstants.KEY_RESOURCE_URI) or catalog_uri or next_page_url,
                                        message_code=get_common_warning_message_code(phase=current_phase, reason=reason),
                                        payload = {"entity_type": warn_entity_type}
                                    )

                        if catalog_errors and len(catalog_errors) > 0:
                            num = 0
                            reason = VALIDATION_REASON_INVALID_PARSE_CATALOG
                            for catalog_error in catalog_errors:
                                num += 1
                                if (num <= DGERDFHarvester.MAX_NUM):
                                    errormsg = NTIHarvesterConstants.CATALOG_VALIDATION_ERRORS.format(catalog_error)
                                    if next_page_url:
                                        errormsg = NTIHarvesterConstants.CATALOG_VALIDATION_ERRORS_URL.format(next_page_url, catalog_error)
                                    error_detail = self._get_detail_by_index(
                                        catalog_error_details,
                                        num - 1,
                                    )
                                    log.info(f"{method_log_prefix} Saving gather_error - {errormsg} {harvest_job}")
                                    error_entity_type = (error_detail or {}).get(HarvestMessageDetailConstants.KEY_SCOPE) or entity_type
                                    self._save_common_structured_gather_report_error(
                                        exception = (error_detail or {}).get(HarvestMessageDetailConstants.KEY_EXCEPTION),
                                        harvest_object=obj,
                                        display_message=(error_detail or {}).get(HarvestMessageDetailConstants.KEY_MESSAGE) or catalog_error,
                                        phase=current_phase,
                                        raw_message=error_detail,
                                        kind=f"{error_entity_type}_validation_paser_error",
                                        resource_uri=(error_detail or {}).get(HarvestMessageDetailConstants.KEY_RESOURCE_URI) or catalog_uri or next_page_url,
                                        reason=reason,
                                        message_code=get_common_error_message_code(phase=current_phase, reason=reason),
                                        payload = {"entity_type": error_entity_type},
                                    )
                            # Summary
                            summarymsg = NTIHarvesterConstants.LOG_CATALOG_ERROR_SUMMARY.format(catalog_uri or 'Not URIRef', total_catalog_warnings, total_catalog_errors)
                            log.info(f"{method_log_prefix} {summarymsg}")
                            log.debug(f'{method_log_prefix} End method 6. Returns: False')
                            return False
                        else:
                            error_dataset_identifier = ""
                            total_datasets = 0
                            total_error_datasets = 0
                            total_errors = 0
                            total_warnings = 0
                            try:
                                dict = {}
                                dict[NTICatalogConstants.KEY_CATALOG_LANGUAGE] = catalog[NTICatalogConstants.KEY_CATALOG_LANGUAGE]
                                dict[NTIDatasetConstants.KEY_DATASET_DEFAULT_CATALOG_LANGUAGE] = default_catalog_language
                                dict[NTICatalogConstants.KEY_CATALOG_THEME_TAXONOMY] = catalog[NTICatalogConstants.KEY_CATALOG_THEME_TAXONOMY]
                                dict[NTICatalogConstants.KEY_CATALOG_URI] = catalog[NTICatalogConstants.KEY_CATALOG_URI]
                                dict[NTICatalogConstants.KEY_CATALOG_AVAILABLE_DATA] = catalog[NTICatalogConstants.KEY_CATALOG_AVAILABLE_DATA]
                                entity_type = "dataset"
                                for dataset in parser.datasets(dict):

                                    total_datasets += 1

                                    # Unless already set by the parser, get the owner organization (if any)
                                    # from the harvest source dataset
                                    if not dataset.get(NTIDatasetConstants.KEY_OWNER_ORG):
                                        if owner_org_catalog:
                                            dataset[NTIDatasetConstants.KEY_OWNER_ORG] = owner_org_catalog

                                    if not dataset.get(NTIDatasetConstants.KEY_NAME) \
                                            and dataset.get(NTIDatasetConstants.KEY_TITLE) \
                                            and dataset.get(NTIDatasetConstants.KEY_PUBLISHER_ID_MINHAP):
                                        dataset[NTIDatasetConstants.KEY_NAME] = self._gen_new_name(
                                            dataset.get(NTIDatasetConstants.KEY_PUBLISHER_ID_MINHAP, '') + '-' + dataset.get(NTIDatasetConstants.KEY_TITLE, ''))

                                    # Try to get a unique identifier for the harvested dataset
                                    guid = self._get_guid(dataset)
                                    if not guid:
                                        log.error(f'{method_log_prefix} Could not get a unique identifier for dataset: {dataset}')
                                        continue

                                    dataset[NTIDatasetConstants.KEY_EXTRAS].append({'key': 'guid', 'value': guid})
                                    guids_in_source.append(guid)

                                    # delete unnecesary info
                                    errors = dataset.pop(NTIDatasetConstants.KEY_ERRORS, [])
                                    warnings= dataset.pop(NTIDatasetConstants.KEY_WARNINGS, [])
                                    error_details = dataset.pop(
                                        CommonPackageConstants.KEY_ERROR_DETAILS,
                                        [],
                                    )
                                    warning_details = dataset.pop(
                                        CommonPackageConstants.KEY_WARNING_DETAILS,
                                        [],
                                    )
                                    dataset.pop(NTICatalogConstants.KEY_CATALOG_AVAILABLE_DATA, None)

                                    if guid or dataset.get(NTIDatasetConstants.KEY_NAME):
                                        error_dataset_identifier = guid if guid else dataset.get(NTIDatasetConstants.KEY_NAME)

                                    if errors and len(errors) > 0:
                                        total_errors = total_errors + len(errors)
                                        log.debug(f"{method_log_prefix} errors number={len(errors)}")
                                    if warnings and len(warnings) > 0:
                                        total_warnings = total_warnings + len(warnings)
                                        log.debug(f"{method_log_prefix} warnings number={len(warnings)}")

                                    if errors and len(errors) > 0:
                                        obj = HarvestObject(guid=guid, job=harvest_job, state='ERROR',
                                                            content=json.dumps(dataset))
                                        obj.save()
                                        # object_ids.append(obj.id)
                                        total_error_datasets += 1
                                        num = 0
                                        reason = VALIDATION_REASON_INVALID_PARSE_DATASET
                                        for error in errors:
                                            num += 1
                                            if (num <= DGERDFHarvester.MAX_NUM):
                                                errormessage = NTIHarvesterConstants.DATASET_VALIDATION_ERROR.format(error)
                                                log.info(f"{method_log_prefix} Saving objectError {errormessage} for dataset {error_dataset_identifier}")
                                                error_detail = self._get_detail_by_index(
                                                    error_details,
                                                    num - 1,
                                                )
                                                error_entity_type = (error_detail or {}).get(HarvestMessageDetailConstants.KEY_SCOPE) or entity_type
                                                self._save_gather_stage_common_structured_object_report_error(
                                                    exception = (error_detail or {}).get(HarvestMessageDetailConstants.KEY_EXCEPTION),
                                                    harvest_object=obj,
                                                    display_message=(error_detail or {}).get(HarvestMessageDetailConstants.KEY_MESSAGE) or error,
                                                    phase=current_phase,
                                                    raw_message=error_detail,
                                                    kind=f"{error_entity_type}_validation_paser_error",
                                                    resource_uri=(error_detail or {}).get(HarvestMessageDetailConstants.KEY_RESOURCE_URI) or dataset.get(NTIDatasetConstants.KEY_URI),
                                                    reason=reason,
                                                    message_code=get_common_error_message_code(phase=current_phase, reason=reason),
                                                    payload = {"entity_type": error_entity_type},
                                                )
                                    else:
                                        obj = HarvestObject(guid=guid, job=harvest_job,
                                                            content=json.dumps(dataset), )

                                        obj.save()
                                        object_ids.append(obj.id)

                                    if warnings and len(warnings) > 0:
                                        num = 0
                                        reason = VALIDATION_REASON_WARNING_PARSE_DATASET
                                        for warn in warnings:
                                            num += 1
                                            if (num <= DGERDFHarvester.MAX_NUM):
                                                warnmessage = NTIHarvesterConstants.DATASET_VALIDATION_WARNING.format(warn)
                                                log.info(f"{method_log_prefix} Saving warning in objectError {warnmessage} for dataset {error_dataset_identifier}")
                                                warning_detail = self._get_detail_by_index(
                                                    warning_details,
                                                    num - 1,
                                                )
                                                warn_entity_type = (warning_detail or {}).get(HarvestMessageDetailConstants.KEY_SCOPE) or entity_type
                                                self._save_gather_stage_common_structured_object_report_warning(
                                                    exception = (warning_detail or {}).get(HarvestMessageDetailConstants.KEY_EXCEPTION),
                                                    harvest_object=obj,
                                                    display_message=(warning_detail or {}).get(HarvestMessageDetailConstants.KEY_MESSAGE) or warn,
                                                    phase=current_phase,
                                                    raw_message=warning_detail,
                                                    kind=f"{warn_entity_type}_validation_paser_error",
                                                    resource_uri=(warning_detail or {}).get(HarvestMessageDetailConstants.KEY_RESOURCE_URI) or dataset.get(NTIDatasetConstants.KEY_URI),
                                                    reason=reason,
                                                    message_code=get_common_warning_message_code(phase=current_phase, reason=reason),
                                                    payload = {"entity_type": warn_entity_type},
                                                )
                                            
                                # Summary
                                summarymsg = NTIHarvesterConstants.LOG_SUMMARY.format(
                                    total_catalog_warnings, total_datasets, total_error_datasets, total_errors,
                                    total_warnings)
                                log.info(f"{method_log_prefix} {summarymsg}")
                            except RDFParserException as e:
                                errormsg = NTIHarvesterConstants.DATASET_VALIDATION_ERROR.format(type(e).__name__, e)
                                log.info(f"{method_log_prefix} Saving gather_error - {errormsg}")
                                reason = VALIDATION_REASON_INVALID_PARSE_DATASET
                                self._save_common_structured_gather_report_error(
                                    exception=e,
                                    harvest_job=harvest_job,
                                    raw_message=errormsg,
                                    kind="unexpected_dataset_parser_error",
                                    reason=VALIDATION_REASON_INVALID_PARSE_DATASET,
                                    resource_uri=dataset.get(NTIDatasetConstants.KEY_URI),
                                    payload = {"entity_type": entity_type},
                                    message_code=get_common_error_message_code(phase=current_phase, reason=reason, exception=e),
                                )
                                # Summary
                                summarymsg = NTIHarvesterConstants.LOG_SUMMARY.format(
                                    total_catalog_warnings, total_datasets, (total_error_datasets + 1), total_errors,
                                    total_warnings)
                                log.info(f"{method_log_prefix} {summarymsg}")
                                log.debug(f'{method_log_prefix} End method 7. Returns: False')
                                return []
                except RDFParserException as e:
                    errormsg = NTIHarvesterConstants.CATALOG_VALIDATION_ERROR.format(type(e).__name__, e)
                    if next_page_url:
                        errormsg = NTIHarvesterConstants.CATALOG_VALIDATION_ERROR_URL.format(next_page_url, type(e).__name__, e)
                    log.info(f"{method_log_prefix} Saving gather_error - {errormsg}")
                    entity_type = "catalog"
                    reason = VALIDATION_REASON_INVALID_PARSE_DATASET
                    self._save_common_structured_gather_report_error(
                        exception=e,
                        harvest_job=harvest_job,
                        raw_message=errormsg,
                        kind="unexpected_dataset_parser_error",
                        reason=reason,
                        resource_uri=catalog_uri,
                        payload = {"entity_type": entity_type}, 
                        message_code=get_common_error_message_code(phase=current_phase, reason=reason, exception=e),
                    )
                    # Summary
                    summarymsg = NTIHarvesterConstants.LOG_CATALOG_ERROR_SUMMARY.format(catalog_uri or 'Not URIRef', total_catalog_warnings, (total_catalog_errors + 1))
                    log.info(f"{method_log_prefix} {summarymsg}")
                    log.debug(f'{method_log_prefix} End method 8. Returns: False')
                    return False
                
                # Add the current URL to the visited set
                visited_urls.add(next_page_url)
                # Get the next URL
                next_page_url = parser.next_page()
                log.debug(f'{method_log_prefix} Getting next page URL: {next_page_url}')

            # Check if some datasets need to be deleted
            object_ids_to_delete = self._mark_datasets_for_deletion(guids_in_source, harvest_job)
            log.debug(f'object_ids_to_delete={object_ids_to_delete}')
            log.debug(f'object_ids={object_ids}')
            object_ids.extend(object_ids_to_delete)
            log.debug(f'{method_log_prefix} content={content}')
            log.debug(f'{method_log_prefix} End method 9. Returns: {object_ids}')
            return object_ids
        except Exception as e:
            log.exception(
                f'{method_log_prefix} Error on gather stage for harvest job {harvest_job.id}: {type(e).__name__}: {str(e)}' )
            self._finish_unsuccessful_structured_gather_stage(
                exception = e,
                harvest_job=harvest_job,
                raw_message="Error inesperado en la etapa gather de la federación.",
                display_message=append_support_message("Se ha producido un error inesperado durante el proceso de federación."),
                phase=current_phase,
                category = REPORT_CATEGORY_TECHNICAL,
                kind="unexpected_error",
                message_code=get_technical_error_message_code(phase=current_phase, reason=None, exception=e),
            )
            return None


    def _get_detail_by_index(self, details, index):
        """Return one optional detail entry aligned with the plain message list."""
        if not details:
            return None
        if index < 0 or index >= len(details):
            return None
        return details[index]

    def fetch_stage(self, harvest_object):
        # Nothing to do here
        return True

    @log_info
    def import_stage(self, harvest_object):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        harvest_object_id = ''
        harvest_object_guid = ''
        current_phase = REPORT_PHASE_IMPORT
        try:
            harvest_object_id = harvest_object.id
            harvest_object_guid = harvest_object.guid
            status = self._get_object_extra(harvest_object, 'status')
            if status == 'delete':
                # Delete package
                return self._delete_package(harvest_object)

            if harvest_object.content is None:
                error = 'Empty content for object {0}'.format(harvest_object.id)
                log.info(f"{method_log_prefix} Saving objectError {error} for harvest_object_guid {harvest_object_guid}")
                self._save_import_stage_technical_structured_object_report_error(
                    harvest_object=harvest_object,
                    display_message = append_support_message(f"No se ha podido obtener el contenido para el recurso con guid {harvest_object_guid}."),
                    raw_message=NTIHarvesterConstants.DATASET_IMPORT_ERROR.format(error),
                    kind = "getting_object_content",
                    reason=IMPORT_REASON_EMPTY_OBJECT_CONTENT,
                    message_code = get_technical_error_message_code(phase=current_phase, reason=IMPORT_REASON_EMPTY_OBJECT_CONTENT)
                )
                return False
            try:
                dataset = json.loads(harvest_object.content)
            except ValueError as exc:
                error = 'Could not parse content for object {0}'.format(harvest_object.id)
                log.info(f"{method_log_prefix} Saving objectError {error} for harvest_object_guid {harvest_object_guid}")
                self._save_import_stage_technical_structured_object_report_error(
                    exception = exc,
                    harvest_object=harvest_object,
                    raw_message=NTIHarvesterConstants.DATASET_IMPORT_ERROR.format(error),
                    display_message = append_support_message(f"No se ha podido parsear el contenido para el recurso con guid {harvest_object_guid}."),
                    kind="invalid_object_content",
                    reason=IMPORT_REASON_WRONG_PARSE_LOAD_OBJECT_CONTENT,
                    message_code = get_technical_error_message_code(phase=current_phase, reason=IMPORT_REASON_WRONG_PARSE_LOAD_OBJECT_CONTENT),
            )
                return False
            # Get the last harvested object (if any)
            previous_object = model.Session.query(HarvestObject) \
                .filter(HarvestObject.guid == harvest_object.guid) \
                .filter(HarvestObject.current == True) \
                .first()

            # Flag previous object as not current anymore
            if previous_object:
                previous_object.current = False
                previous_object.add()

            # Flag this object as the current one
            harvest_object.current = True
            harvest_object.add()

            context = {
                'user': self._get_user_name(),
                'return_id_only': True,
                'ignore_auth': True,
            }

            # Check if a dataset with the same guid exists
            existing_dataset =self._get_existing_package_by_guid(context, harvest_object.guid)

            if existing_dataset:
                # Don't change the dataset name even if the title has
                dataset[NTIDatasetConstants.KEY_NAME] = existing_dataset[NTIDatasetConstants.KEY_NAME]
                dataset[NTIDatasetConstants.KEY_ID] = existing_dataset[NTIDatasetConstants.KEY_ID]
                if (existing_dataset[NTIDatasetConstants.KEY_STATE] == 'deleted'):
                    log.info(f'{method_log_prefix} Reactivating deleted package with id {existing_dataset[NTIDatasetConstants.KEY_ID]}')
                    dataset[NTIDatasetConstants.KEY_STATE] = 'active'

                # Save reference to the package on the object
                harvest_object.package_id = dataset[NTIDatasetConstants.KEY_ID]
                harvest_object.add()

                try:
                    p.toolkit.get_action('package_update')(context, dataset)
                except p.toolkit.ValidationError as e:
                    error = NTIHarvesterConstants.DATASET_IMPORT_ERROR.format(str(e.error_summary))
                    log.debug(f"{method_log_prefix} Saving objectError {error} for harvest_object_guid {harvest_object_guid}")
                    self._save_import_stage_technical_structured_object_report_error(
                        exception = e,
                        harvest_object=harvest_object,
                        raw_message= error,
                        display_message = append_support_message(f"No se ha podido actualizar el recurso existe {existing_dataset.get(CommonPackageConstants.KEY_URI, '')}."),
                        kind="package_update_validation_error",
                        message_code = get_technical_error_message_code(phase=current_phase, reason=None, exception=e),
                    )
                    return False

                log.info(f'{method_log_prefix} Updated dataset {dataset.get(NTIDatasetConstants.KEY_NAME)}')

            else:
                package_schema = logic.schema.default_create_package_schema()
                context['schema'] = package_schema

                # We need to explicitly provide a package ID
                dataset[NTIDatasetConstants.KEY_ID] = str(uuid.uuid4())
                package_schema['id'] = [str]

                # Save reference to the package on the object
                harvest_object.package_id = dataset[NTIDatasetConstants.KEY_ID]
                harvest_object.add()

                # Defer constraints and flush so the dataset can be indexed with
                # the harvest object id (on the after_show hook from the harvester
                # plugin)
                model.Session.execute('SET CONSTRAINTS harvest_object_package_id_fkey DEFERRED')
                model.Session.flush()

                try:
                    p.toolkit.get_action('package_create')(context, dataset)
                except p.toolkit.ValidationError as e:
                    error = NTIHarvesterConstants.DATASET_IMPORT_ERROR.format(str(e.error_summary))
                    log.info(f"{method_log_prefix} Saving objectError {error} for harvest_object_guid {harvest_object_guid}")
                    self._save_import_stage_technical_structured_object_report_error(
                        exception = e,
                        harvest_object=harvest_object,
                        raw_message= error,
                        display_message = append_support_message(f"No se ha podido crear el recurso para guid {harvest_object_guid}."),
                        kind="package_create_validation_error",
                        message_code = get_technical_error_message_code(phase=current_phase, reason=None, exception=e),
                    )
                    return False

                log.info(f'{method_log_prefix} Created dataset {dataset.get(NTIDatasetConstants.KEY_NAME)}')
            model.Session.commit()
        except Exception as e:
            errormsg = f'{str(e)}'
            try:
                errormsg = f"Exception in harvest_object {harvest_object_guid} ({harvest_object_id}) {type(e).__name__}: {str(e)}"
                log.error(f"{method_log_prefix} {errormsg}")
                if 'IntegrityError' == type(e).__name__:
                    errormsg = NTIHarvesterConstants.DATASET_INTEGRITY_ERROR
                self._save_import_stage_technical_structured_object_report_error(
                    exception = e,
                    harvest_object=harvest_object,
                    raw_message=NTIHarvesterConstants.DATASET_IMPORT_ERROR.format(errormsg),
                    display_message = append_support_message(f"No se ha podido importar el recurso con guid {harvest_object.guid}."),
                    kind="import_stage_exception",
                    message_code = get_technical_error_message_code(phase=current_phase, reason=None, exception=e),
                )
                
            except Exception as ex:
                log.error(f"{method_log_prefix} Exception {type(ex)}. {str(ex)}")
                harvest_object.package_id = None
                self._save_import_stage_technical_structured_object_report_error(
                    exception = e,
                    harvest_object=harvest_object,
                    raw_message=NTIHarvesterConstants.DATASET_IMPORT_ERROR.format(errormsg),
                    display_message = append_support_message(f"No se ha podido importar el recurso con guid {harvest_object.guid}."),
                    kind="import_stage_exception_handler_error",
                    message_code = get_technical_error_message_code(phase=current_phase, reason=None, exception=e),
                )
            return False
        return True

