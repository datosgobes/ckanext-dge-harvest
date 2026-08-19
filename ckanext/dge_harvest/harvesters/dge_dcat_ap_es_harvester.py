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
import inspect
from typing import List, Optional, Tuple
import ckan.plugins as p
from rdflib import Graph
import ckan.model as model
from ckantoolkit import config
from ckanext.dcat.exceptions import RDFProfileException, RDFParserException
from ckanext.harvest.model import HarvestObject, HarvestJob, HarvestObjectExtra
from ckanext.dge_harvest.processors import DGEDCATAPESRDFParser
from ckanext.dge_harvest.constants import ( DCATAPESCatalogConstants as CatalogConstants, DCATAPESHarvesterConstants as HarvesterConstants, 
                          DCATAPESDatasetConstants as DatasetConstants, DCATAPESDataserviceConstants as DataserviceConstants,
                          CommonPackageConstants, HarvestMessageDetailConstants, HarvestObjectExtraKeyConstants, DCATAPESSerializerConstants )
from ckanext.dge_harvest.harvesters.dge_harvester import DGERDFHarvester, GatherRdfFormatConfigError, PrepareGatherContextError
from ckanext.dge_harvest.harvesters.dge_harvester_exceptions import (
    GatherConnectionError,
    GatherFileNotFoundError,
    GatherFileTooLargeError,
    GatherHTTPError,
    GatherHookError,
    GatherParserError,
    GatherTimeoutError,
    GatherCatalogsWithErrorsError
)
from ckanext.dge_harvest.harvesters.utils import (DcatApEsRdfValidator, ShaclValidatorException,
                    VocabularyValidatorException,  GatherStageValidation, GatherStageValidationException, GatherStageInfo,
                     gather_stage_preprocessing_utils, gather_stage_parse_utils, harvester_utils, import_stage_utils)
from ckanext.dge_harvest.rdf_store import (RDFStoreException, RDFStoreComplete, RDFStoreInsertOrUpdate)
from ckanext.dge_harvest.utils import dge_harvest_dataset_uri, dge_harvest_dataservice_uri, generate_graph_uri_from_job, generate_graph_uri_and_catalog_uri_from_source_id
from ckanext.dge_harvest.decorators import log_debug, log_info
from ckanext.dge_harvest.helpers import dge_harvest_organizations_available
from ckanext.dge_harvest.harvesters.utils.report.import_stage_report_helper import (
    DcatImportStageReportHelperMixin
)
from ckanext.dge_harvest.harvesters.utils.report.gather_stage_report_helper import (
    DcatGatherStageReportHelperMixin
)
from ckanext.dge_harvest.harvesters.utils.report.gather_stage_validation_report_helper import (
    DcatGatherStageValidationMessageHelperMixin,
    ValidationReportMessages,
)
from ckanext.dge_harvest.harvesters.dge_harvester_exceptions import (
    RdfValidatorException,
)
from ckanext.dge_harvest.services.report.harvest_report_dimensions import (
    REPORT_PHASE_SETUP,
    REPORT_PHASE_DOWNLOAD,
    REPORT_PHASE_PREPROCESSING,
    REPORT_PHASE_STORAGE,
    REPORT_PHASE_VALIDATION,
    REPORT_PHASE_FALLBACK,
    REPORT_PHASE_IMPORT,
    REPORT_CATEGORY_COMMON,
    REPORT_CATEGORY_TECHNICAL,
)
from ckanext.dge_harvest.services.report.harvest_report_technical_classifier import (
    get_technical_error_message_code,
    get_technical_warning_message_code,
    get_technical_info_message_code,    
    IMPORT_REASON_EMPTY_OBJECT_CONTENT, 
    IMPORT_REASON_WRONG_PARSE_LOAD_OBJECT_CONTENT, 
    IMPORT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_THAT_SERVES_DATASET, 
    IMPORT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_ACCESSED_BY_DISTRIBUTION, 
    IMPORT_REASON_DELETED_DATASET, 
    IMPORT_REASON_DELETED_DATASERVICE, 

)

from ckanext.dge_harvest.services.report.harvest_report_common_classifier import (
    get_common_error_message_code,
    get_common_info_message_code,
    get_common_warning_message_code,
    VALIDATION_REASON_WRONG_CATALOGS,
    VALIDATION_REASON_NO_VALID_DISTRIBUTION_IN_DATASET,
    COMMON_REASON_JOB_RENEWED_BEFORE_FINISH,
    COMMON_REASON_ABORTED_JOB,
    PREPROCESSING_REASON_NON_CANONICAL_NAMESPACES,
    PREPROCESSING_REASON_WRONG_REPLACEMENT_BNODES,
    PREPROCESSING_REASON_ROOT_CATALOG_URI_NOT_FOUND,
    PREPROCESSING_REASON_INVALID_PREPROCESSING_OF_SOURCE_RDF,
    PREPROCESSING_REASON_ERROR_DOING_BACKUP_FROM_SOURCE_GRAPH,
    
)
from ckanext.dge_harvest.services.report.harvest_report_catalog_messages import(
    append_support_message
)
from .constants.harvest_report_constants import (
    GATHER_JOB_ABORTED_RAW_MESSAGE,
    GATHER_JOB_RENEWED_RAW_MESSAGE
)
log = logging.getLogger(__name__)


IMPORT_STAGE = 'Import'

class DGEDCATAPESRDFHarvester(DcatGatherStageValidationMessageHelperMixin, 
                              DcatGatherStageReportHelperMixin,
                              DcatImportStageReportHelperMixin,
                              DGERDFHarvester):

    def _extract_parse_errors(self, entity_dict, errors_key):
        """Prefer structured detail messages when parser provides them."""
        error_details = entity_dict.get(CommonPackageConstants.KEY_ERROR_DETAILS, [])
        if error_details:
            return [
                detail.get(HarvestMessageDetailConstants.KEY_MESSAGE)
                for detail in error_details
                if detail.get(HarvestMessageDetailConstants.KEY_MESSAGE)
            ]
        return entity_dict.get(errors_key, [])

    def _extract_parse_error_details(self, entity_dict):
        """Return structured parse error details when parser provides them."""
        return entity_dict.get(CommonPackageConstants.KEY_ERROR_DETAILS, [])

    def _build_parse_error_detail(self, message, scope, resource_uri, exception=None):
        """Build one structured parse error detail entry."""
        return {
            HarvestMessageDetailConstants.KEY_LEVEL: "error",
            HarvestMessageDetailConstants.KEY_SCOPE: scope,
            HarvestMessageDetailConstants.KEY_MESSAGE: message,
            HarvestMessageDetailConstants.KEY_RESOURCE_URI: resource_uri,
            HarvestMessageDetailConstants.KEY_EXCEPTION: exception,
        }
    
    def info(self):
        return {
            'name': HarvesterConstants.HARVESTER_TYPE,
            'title': HarvesterConstants.HARVESTER_TYPE,
            'description': 'Harvester for DGE datasets and dataservices from an RDF graph',
            'order': 10
        }

    @log_info
    def _parse_catalog(self, parser, catalog_graph, catalog_uri, catalog_dict) -> Tuple[bool, List[str], List[dict[str, object]], dict[str, object]]: 
        """
        Parse catalog graph in catalog dict to store in CKAN

        :param parser: parser 
        :type parser: RDFParser
            
        :param catalog_graph: catalog graph 
        :type catalog_graph: graph
                    
        :param catalog_uri: URI of catalog
        :type catalog_uri: str

        :returns: Tuple with three params: 
            - conforms: True if catalog_graph is conforms, False in other case
            - messages: List of messages in parse
            - error_details: Structured messages in parse
            - catalog: catalog dict
        :rtype: Tuple[bool, List[str], List[dict[str, object]], dict[str, object]]
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        conforms = True
        parse_errors = []
        parse_error_details = []
        catalog = catalog_dict or {}
        try:
            # Graph g contains an only catalog
            parser.g = catalog_graph
            for catalog in parser.catalogs(catalog_dict):
                parse_errors = self._extract_parse_errors(
                    catalog,
                    CatalogConstants.KEY_CATALOG_ERRORS,
                )
                parse_error_details = self._extract_parse_error_details(catalog)
        except Exception as e:
            log.exception(f'{method_log_prefix} Exception {type(e)}: {str(e)}')
            conforms = False
            error_message = (
                HarvesterConstants.VALIDATION_UNEXPECTED_CATALOG_ERROR_MESSAGE.format(
                    catalog_uri
                )
            )
            parse_errors.append(error_message)
            catalog.setdefault(CatalogConstants.KEY_CATALOG_ERRORS, [])
            if error_message not in catalog[CatalogConstants.KEY_CATALOG_ERRORS]:
                catalog[CatalogConstants.KEY_CATALOG_ERRORS].append(error_message)
            catalog.setdefault(CommonPackageConstants.KEY_ERROR_DETAILS, [])
            error_detail = self._build_parse_error_detail(
                message=error_message,
                scope="catalog",
                resource_uri=catalog_uri,
                exception=e,
            )
            if error_detail not in catalog[CommonPackageConstants.KEY_ERROR_DETAILS]:
                catalog[CommonPackageConstants.KEY_ERROR_DETAILS].append(error_detail)
            parse_error_details = catalog[CommonPackageConstants.KEY_ERROR_DETAILS]
        conforms = False if parse_errors else True
        return conforms, parse_errors, parse_error_details, catalog

    def _get_name_dataset_dataservice(self, current_name, title, publisher_minhap):
        name = None
        if current_name:
            name = current_name
        elif title:
            publisher_id_minhap = publisher_minhap + '-' if publisher_minhap else '' 
            name = self._gen_new_name(publisher_id_minhap + title)
            if name in self._names_taken:
                suffix = len([i for i in self._names_taken if i.startswith(name + '-')]) + 1
                name = '{}-{}'.format(name, suffix)
        self._names_taken.append(name)
        return name

    @log_debug
    def _parse_dataservice(self, parser, dataservice_graph, dataservice_uri, dataservice_dict, owner_org_id) -> Tuple[bool, List[str], List[dict[str, object]], dict[str, object], str]: 
        """
        Parse dataservice graph in dataservice dict to store in CKAN

        :param parser: parser 
        :type parser: RDFParser

        :param dataservice_graph: dataservice graph 
        :type dataservice_graph: graph

        :param dataservice_uri: URI of catalog
        :type dataservice_uri: str

        :param dataservice_dict: dictionary with data useful for parse
        :type dataservice_dict: dict[str, object]

        :param owner_org_id: owner organization id
        :type owner_org_id: str

        :returns: Tuple with three params: 
            - conforms: True if dataservice_graph is conforms, False in other case
            - messages: List of messages in parse
            - error_details: Structured messages in parse
            - dataservice: dataservice dict
            - dataservice_guid: dataservice guid
        :rtype: Tuple[bool, List[str], List[dict[str, object]], dict[str, object], str]
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        conforms = True
        parse_errors = []
        parse_error_details = []
        dataservice = dataservice_dict or {}
        dataservice_guid = None
        try:
            parser.g = dataservice_graph
            for dataservice in parser.dataservices(dataservice_dict or {}):
                parse_errors = self._extract_parse_errors(
                    dataservice,
                    DataserviceConstants.KEY_ERRORS,
                )
                parse_error_details = self._extract_parse_error_details(dataservice)
                # owner_org
                dataservice[DataserviceConstants.KEY_OWNER_ORG] = owner_org_id
                dataservice[DataserviceConstants.KEY_TYPE] = CommonPackageConstants.KEY_TYPE_DATASERVICE_VALUE
                dataservice[DataserviceConstants.KEY_NAME] = self._get_name_dataset_dataservice(dataservice.get(DataserviceConstants.KEY_NAME), 
                                                                                                dataservice.get(DataserviceConstants.KEY_TITLE), 
                                                                                                dataservice.get(DataserviceConstants.KEY_PUBLISHER_ID_MINHAP))
                dataservice_guid = self._get_guid(dataservice)
        except Exception as e:
            log.exception(f'{method_log_prefix} Exception {type(e)}: {str(e)}')
            error_message = (
                HarvesterConstants.VALIDATION_UNEXPECTED_DATASERVICE_ERROR_MESSAGE.format(
                    dataservice_uri
                )
            )
            parse_errors.append(error_message)
            dataservice.setdefault(DataserviceConstants.KEY_ERRORS, [])
            if error_message not in dataservice[DataserviceConstants.KEY_ERRORS]:
                dataservice[DataserviceConstants.KEY_ERRORS].append(error_message)
            dataservice.setdefault(CommonPackageConstants.KEY_ERROR_DETAILS, [])
            error_detail = self._build_parse_error_detail(
                message=error_message,
                scope="dataservice",
                resource_uri=dataservice_uri,
                exception=e,
            )
            if error_detail not in dataservice[CommonPackageConstants.KEY_ERROR_DETAILS]:
                dataservice[CommonPackageConstants.KEY_ERROR_DETAILS].append(error_detail)
            parse_error_details = dataservice[CommonPackageConstants.KEY_ERROR_DETAILS]
        conforms = False if parse_errors else True
        return conforms, parse_errors, parse_error_details, dataservice, dataservice_guid

    @log_debug
    def _parse_dataset(self, parser, dataset_graph, dataset_uri, dataset_dict, owner_org_id) -> Tuple[bool, List[str], List[dict[str, object]], dict[str, object], str]:
        """
        Parse dataset graph in dataset dict to store in CKAN
            
        :param parser: parser 
        :type parser: RDFParser
            
        :param dataset_graph: dataset graph 
        :type dataset_graph: graph
                    
        :param dataset_uri: URI of catalog
        :type dataset_uri: str

        :param dataset_dict: dictionary with data useful for parse
        :type dataset_dict: dict[str, object]
                    
        :param owner_org_id: owner organization id
        :type owner_org_id: str

        :returns: Tuple with three params: 
            - conforms: True if dataset_graph is conforms, False in other case
            - messages: List of messages in parse
            - error_details: Structured messages in parse
            - dataset: dataset dict
            - dataset_guid: dataset guid
        :rtype:  -> Tuple[bool, List[str], List[dict[str, object]], dict[str, object], str]: 
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        conforms = True
        parse_errors = []
        parse_error_details = []
        dataset = dataset_dict or {}
        dataset_guid = None
        try:
            parser.g = dataset_graph
            for dataset in parser.datasets(dataset_dict or {}):
                parse_errors = self._extract_parse_errors(
                    dataset,
                    DatasetConstants.KEY_ERRORS,
                )
                parse_error_details = self._extract_parse_error_details(dataset)
                # Unless already set by the parser, get the owner organization (if any)
                # from the harvest source dataset
                dataset[DatasetConstants.KEY_OWNER_ORG] = dataset.get(DatasetConstants.KEY_OWNER_ORG, None) or owner_org_id
                dataset[DatasetConstants.KEY_TYPE] = CommonPackageConstants.KEY_TYPE_DATASET_VALUE
                
                dataset[DataserviceConstants.KEY_NAME] = self._get_name_dataset_dataservice(dataset.get(DataserviceConstants.KEY_NAME), 
                                                                                            dataset.get(DataserviceConstants.KEY_TITLE), 
                                                                                            dataset.get(DataserviceConstants.KEY_PUBLISHER_ID_MINHAP))
                dataset_guid = self._get_guid(dataset)
        except Exception as e:
            log.exception(f'{method_log_prefix} Exception {type(e)}: {str(e)}')
            error_message = (
                HarvesterConstants.VALIDATION_UNEXPECTED_DATASET_ERROR_MESSAGE.format(
                    dataset_uri
                )
            )
            parse_errors.append(error_message)
            dataset.setdefault(DatasetConstants.KEY_ERRORS, [])
            if error_message not in dataset[DatasetConstants.KEY_ERRORS]:
                dataset[DatasetConstants.KEY_ERRORS].append(error_message)
            dataset.setdefault(CommonPackageConstants.KEY_ERROR_DETAILS, [])
            error_detail = self._build_parse_error_detail(
                message=error_message,
                scope="dataset",
                resource_uri=dataset_uri,
                exception=e,
            )
            if error_detail not in dataset[CommonPackageConstants.KEY_ERROR_DETAILS]:
                dataset[CommonPackageConstants.KEY_ERROR_DETAILS].append(error_detail)
            parse_error_details = dataset[CommonPackageConstants.KEY_ERROR_DETAILS]
        conforms = False if parse_errors else True
        return conforms, parse_errors, parse_error_details, dataset, dataset_guid

    @log_debug
    def _load_complete_rdf(self, parser: DGEDCATAPESRDFParser, rdf_store:RDFStoreInsertOrUpdate, harvest_job: HarvestJob, rdf_format: str, effective_url: str) -> str:
        ''' 
        Process and store complete RDF in the rdf_store

        :param parser: parser object
        :type parser: DGEDCATAPESRDFParser

        :param harvest_job: harvest job object
        :type harvest_job: HarvestJob
        
        :param rdf_format: RDF format
        :type rdf_format: str
        
        :param effective_url: URL congelada del job (no harvest_job.source.url)
        :type effective_url: str
        
        :return: graph uri than contains the complete RDF
        :rtype: str
        ''' 
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            current_phase = REPORT_PHASE_DOWNLOAD
            result = None
            last_content_hash = None
            visited_urls = set()
            # Get file contents of first page
            next_page_url = effective_url
            log.info(f'{method_log_prefix} Init harvest for harvest_source with url {next_page_url}')

            #Get parser with complete graph per page
            while next_page_url is not None and next_page_url not in visited_urls:
                try:
                    current_phase = REPORT_PHASE_DOWNLOAD
                    # run before_download of plugins that implements IDCATRDFHarvester
                    log.info(f'{method_log_prefix} Getting info from {next_page_url}')
                    next_page_url = self._run_before_downloads(harvest_job, next_page_url)
                    if not next_page_url:
                        log.debug(f'{method_log_prefix} Error running tasks before download. There is no next_page_url.')
                        result = None
                        break

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
                                category=REPORT_CATEGORY_COMMON,
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
                                category=REPORT_CATEGORY_COMMON,
                                message_code = get_common_warning_message_code(phase=current_phase, exception=warn_message)
                            )
                    
                    content_hash = hashlib.md5()
                    if content:
                        content_hash.update(content.encode('utf8'))

                    if last_content_hash:
                        if content_hash.digest() == last_content_hash.digest():
                            log.warning(f'{method_log_prefix} Remote content was the same even when using a paginated URL, skipping')
                            result = None
                            break

                    last_content_hash = content_hash

                    # run after_download of plugins that implements IDCATRDFHarvester
                    content = self._run_after_downloads(harvest_job, content, next_page_url)
                    if not content:
                        log.debug(f'{method_log_prefix} Error running tasks after download. There is no content.')
                        result = None
                        break

                    # Parse each page in isolated graph to avoid re-inserting triples
                    # already loaded from previous pages.
                    current_parser = parser if parser else DGEDCATAPESRDFParser(profiles=[HarvesterConstants.HARVESTER_PROFILE])
                    current_parser.g = Graph()
                    current_parser.parse(content, _format=rdf_format)
                    
                    # run after_parsings of plugins that implements IDCATRDFHarvester
                    current_parser = self._run_after_parsings(harvest_job, current_parser, next_page_url)
                    if not current_parser:
                        log.debug(f'{method_log_prefix} Error running tasks after parsing. There is no parser.')
                        result = None
                        break

                    # Add RDF data to the RDF store
                    current_phase = REPORT_PHASE_STORAGE
                    query_result = rdf_store.insert_rdf_data(current_parser.g)
                    log.debug(f'{method_log_prefix} query_result: {query_result}')
                    result = rdf_store.get_graph_uri()
                    current_phase = REPORT_PHASE_DOWNLOAD
                    # Add the current URL to the visited set
                    visited_urls.add(next_page_url)
                    # Get the next URL
                    next_page_url = current_parser.next_page(visited_urls)
                    log.debug(f'{method_log_prefix} Next page URL: {next_page_url}')
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
                    result = None
                    break
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
                    result = None
                    break
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
                        result = None
                        break
                except (GatherParserError) as exc:
                    log.exception(f'{method_log_prefix} Error parsing the content of {next_page_url}. Exception {type(e).__name__}: {str(e)}')
                    self._save_common_structured_gather_report_error(
                        exception=e,
                        harvest_job=harvest_job,
                        raw_message=exc.raw_message,
                        phase=current_phase,
                        kind=exc.report_kind,
                        reason=exc.report_reason,
                        message_code=get_common_error_message_code(phase=current_phase, exception=exc),
                        display_message=exc.display_message,
                        payload=exc.context,
                    )
                    result = None
                    break
                except RDFStoreException as e:
                    log.exception(f'{method_log_prefix} Error storing the content of {next_page_url}. Exception {type(e).__name__}: {str(e)}',e, exc_info=True),
                    gather_error = HarvesterConstants.CATALOG_STORE_ERROR_URL.format(next_page_url, HarvesterConstants.VIRTUOSO_LOAD_ERROR.format(next_page_url, e))
                    self._save_technical_structured_gather_report_error(
                        exception=e,
                        harvest_job=harvest_job,
                        raw_message=gather_error,
                        phase=current_phase,
                        kind="rdf_store_load_error",
                        message_code=get_technical_error_message_code(phase=current_phase, reason=None, exception=e),
                        display_message="Se ha producido un error en la obtención del fichero de la federación.",
                        payload=None,
                    )
                    result = None
                    break
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
                            message_code=get_technical_error_message_code(phase=current_phase, reason=None, exception=None),
                        )
                    result = None
                    break
            
            # Drop graph if errors have been found
            if result is None:
                try: 
                    rdf_store.drop_graph()
                except RDFStoreException as e:
                    log.warning(f'{method_log_prefix} Error dropping the graph. Exception {type(e).__name__}: {str(e)}')
            return result
    
        except Exception as e:
            log.exception(f'{method_log_prefix} Unexpected error loading and saving the content of {next_page_url or effective_url}. Unexpected exception {type(e).__name__}: {str(e)}')
            self._save_technical_structured_gather_report_error(
                exception=e,
                harvest_job=harvest_job,
                raw_message=f"Error inesperado durante la obtención y carga del RDF de {next_page_url or effective_url}",
                phase=current_phase,
                display_message=f"Error inesperado durante la obtención y carga del RDF de {next_page_url or effective_url}",
                kind="rdf_get_and_store_error",
                message_code=get_technical_error_message_code(phase=current_phase, reason=None, exception=None), 
            )
            result = None

    def _resolve_gather_stage_context_and_handle_early_exit(
        self,
        harvest_job: HarvestJob,
        method_log_prefix: str,
    ) -> Optional[dict[str, object]]:
        """Freeze gather context and stop early for renewed or aborted jobs."""
        current_phase = REPORT_PHASE_SETUP
        source_url = harvest_job.source.url
        try:
            gather_stage_context = self._prepare_gather_context(harvest_job)
            source_url = gather_stage_context.get(HarvesterConstants.SOURCE_URL_AT_RUN, source_url)
        except PrepareGatherContextError as exc:
            log.exception(
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

    def _prepare_dcat_gather_preconditions(
        self,
        harvest_job: HarvestJob,
        method_log_prefix: str,
        gather_stage_context: dict[str, object],
    ) -> Optional[dict[str, object]]:
        """Prepare parser, RDF store and graph inputs for DCAT gather.

        Returns a dictionary with the ready-to-use preconditions, or ``None``
        when any step fails and the failure is already reported.
        """
        effective_url = gather_stage_context[HarvesterConstants.SOURCE_URL_AT_RUN]
        current_phase = REPORT_PHASE_SETUP
        try:
            rdf_format, _default_catalog_language = self._get_rdf_format_config(
                gather_stage_context[HarvesterConstants.SOURCE_CONFIG_AT_RUN]
            )
        except GatherRdfFormatConfigError as e:
            log.exception(
                f'{method_log_prefix} Error reading RDF format config for harvest job {harvest_job.id}: {type(e).__name__}: {str(e)}',
                exc_info=True,
            )
            self._finish_unsuccessful_structured_gather_stage(
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
            return None

        precondition_error = {
            "kind": "rdf_parser_init_error",
            "raw_message": "Error al iniciar el parser.",
        }

        try:
            parser = DGEDCATAPESRDFParser(profiles=[HarvesterConstants.HARVESTER_PROFILE])
            precondition_error.update({
                "kind": "job_graph_uri_error",
                "raw_message": "Error al generar la URI del grafo de la federación.",
            })
            job_graph_uri = generate_graph_uri_from_job(harvest_job)

            precondition_error.update({
                "kind": "rdf_store_init_error",
                "raw_message": "Error al crear e iniciar el RFDStore para la federación.",
            })
            rdf_store = RDFStoreComplete(job_graph_uri)

            precondition_error.update({
                "kind": "previous_harvest_graph_cleanup_error",
                "raw_message": "Error al borrar los grafos previos existentes para la misma fuente de federación.",
            })
            harvester_utils.remove_graphs_of_previous_harvesting(harvest_job)

            property_prefix = 'ckanext.dge_harvest.dcat_ap_es_1_0_0.'
            havester_config_file_path = config.get(f'{property_prefix}config.filepath', '')
            source_graph_uri, source_catalog_uri = generate_graph_uri_and_catalog_uri_from_source_id(harvest_job.source_id)
            previous_source_graph_uri = f'{source_graph_uri}{HarvesterConstants.SUFFIX_GRAPH_NAME_OF_PREVIOUS_HARVEST}'

        except Exception as e:
            log.exception(
                f'{method_log_prefix} Error on gather precondition step {precondition_error["kind"]} for harvest job {harvest_job.id}: {type(e).__name__}: {str(e)}'
            )
            self._finish_unsuccessful_structured_gather_stage(
                e,
                harvest_job=harvest_job,
                raw_message=precondition_error.get("raw_message", "Error inesperado en la configuración de la tarea de configuración"),
                phase=current_phase,
                category=REPORT_CATEGORY_TECHNICAL,
                kind=precondition_error["kind"],
                reason=None,
                message_code=get_technical_error_message_code(phase=current_phase, reason=None, exception=e),
                payload=None,
            )
            return None

        return {
            "parser": parser,
            "rdf_store": rdf_store,
            "job_graph_uri": job_graph_uri,
            "havester_config_file_path": havester_config_file_path,
            "source_graph_uri": source_graph_uri,
            "source_catalog_uri": source_catalog_uri,
            "previous_source_graph_uri": previous_source_graph_uri,
            "effective_url": effective_url,
            "rdf_format": rdf_format,
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



    @log_info
    def gather_stage(self, harvest_job: HarvestJob):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        effective_url = None
        current_phase = REPORT_PHASE_SETUP
        try:

            current_phase = REPORT_PHASE_SETUP

            gather_stage_context = self._resolve_gather_stage_context_and_handle_early_exit(
                harvest_job=harvest_job,
                method_log_prefix=method_log_prefix,
            )
            if not gather_stage_context:
                return []
            effective_url = gather_stage_context[HarvesterConstants.SOURCE_URL_AT_RUN]


            preconditions = self._prepare_dcat_gather_preconditions(
                harvest_job=harvest_job,
                method_log_prefix=method_log_prefix,
                gather_stage_context=gather_stage_context,
            )
            if not preconditions:
                log.info(f"Etapa gather finaliza en fase {current_phase} debido a problemas en la preparación de la federación")
                return []

            parser = preconditions["parser"]
            rdf_store = preconditions["rdf_store"]
            havester_config_file_path = preconditions["havester_config_file_path"]
            source_graph_uri = preconditions["source_graph_uri"]
            source_catalog_uri = preconditions["source_catalog_uri"]
            previous_source_graph_uri = preconditions["previous_source_graph_uri"]
            effective_url = preconditions["effective_url"]
            rdf_format = preconditions["rdf_format"]

            # Load complete RDF 
            current_phase = REPORT_PHASE_DOWNLOAD
            job_graph_uri = self._load_complete_rdf(parser, rdf_store.rdf_store_insert_or_update, harvest_job, rdf_format, effective_url)
            if not job_graph_uri:
                log.error(f'{method_log_prefix} No graph to job. Returns: []')
                return None

            guids_in_source = []
            guids_to_recover_from_previous_harvester = []
            object_ids = []
            self._names_taken = []

            _uri_ho_dict = {}
            _dataset_uri_is_served_by_dataservice_ho_id_dict = {}
            _catalog_uri_catalog_data_dict = {}


            current_phase = REPORT_PHASE_PREPROCESSING
            try:
            
                #update bnode URIs
                precondition_error = {
                "kind": "replace_bnode_uris_error",
                "reason": PREPROCESSING_REASON_WRONG_REPLACEMENT_BNODES,
                }
                rdf_store.rdf_store_insert_or_update.replace_uriref_bnodes()
                
                rdf_store.update_graph_uri(job_graph_uri)
                rdf_validator = DcatApEsRdfValidator(job_graph_uri, rdf_store.rdf_store_query)
            
                # Preprocess RDF
                precondition_error = {
                "kind": "get_root_catalog_uri",
                "reason": PREPROCESSING_REASON_ROOT_CATALOG_URI_NOT_FOUND,
                }
                if not rdf_store.rdf_store_helper.get_root_catalog_uri():
                    raise RdfValidatorException(
                        raw_message = "Catálogo raíz no encontrado", 
                        display_message="Catálogo raíz no encontrado. Comprueba que el RDF tiene un catálogo raíz.",
                        kind = precondition_error["kind"]
                    )
                
                precondition_error = {
                    "kind": "preprocess_source_rdf",
                    "reason": PREPROCESSING_REASON_INVALID_PREPROCESSING_OF_SOURCE_RDF,
                }
                save_error_method = self._save_preprocessing_structured_gather_report_info_message
                gather_stage_preprocessing_utils.preprocess_source_rdf(rdf_store=rdf_store, graph_uri=job_graph_uri, harvest_job=harvest_job, save_preprocessing_structured_gather_report_info_message_method=save_error_method)
            
                # Validate canonical namespaces
                precondition_error = {
                    "kind": "check_namespaces_are_canonical_from_config",
                    "reason": PREPROCESSING_REASON_NON_CANONICAL_NAMESPACES,
                }
                rdf_validator.check_namespaces_are_canonical_from_config(havester_config_file_path)
                
                # Graph backup
                precondition_error = {
                    "kind": "copy_source_graph_in_target_graph",
                    "reason": PREPROCESSING_REASON_ERROR_DOING_BACKUP_FROM_SOURCE_GRAPH,
                }
                rdf_store.rdf_store_insert_or_update.copy_source_graph_in_target_graph(source_graph_uri, previous_source_graph_uri)
            except (RdfValidatorException) as e:
                log.exception(f'{method_log_prefix} Error in preprocessing stage. Exception {type(e).__name__}: {str(e)}')
                return self._finish_unsuccessful_structured_gather_stage(
                    exception = e,
                    harvest_job=harvest_job,
                    display_message=e.display_message or f"Error al hacer el preprocesamiento del RDF de la url {effective_url}",
                    raw_message=e.raw_message or HarvesterConstants.PREPROCESSING_ERROR.format(effective_url, e),
                    phase=current_phase,
                    kind=precondition_error["kind"] ,
                    category=REPORT_CATEGORY_COMMON,
                    reason=precondition_error["reason"],
                    message_code=get_common_error_message_code(phase=current_phase, reason=precondition_error["reason"], exception=e),
                    payload=None,
                )
            except (RDFStoreException, FileNotFoundError, KeyError, ValueError) as e:
                log.exception(f'{method_log_prefix} Error in preprocessing stage. Exception {type(e).__name__}: {str(e)}')
                return self._finish_unsuccessful_structured_gather_stage(
                    exception = e,
                    harvest_job=harvest_job,
                    display_message=f"Error al hacer el preprocesamiento del RDF de la url {effective_url}",
                    raw_message=HarvesterConstants.PREPROCESSING_ERROR.format(effective_url, e),
                    phase=current_phase,
                    kind=precondition_error["kind"] ,
                    category=REPORT_CATEGORY_TECHNICAL,
                    reason=precondition_error["reason"],
                    message_code=get_technical_error_message_code(phase=current_phase, reason=precondition_error["reason"], exception=e),
                    payload=None,
                )


            current_phase = REPORT_PHASE_VALIDATION
            # Finish method if job has been aborted
            if self._check_has_job_been_aborted(harvest_job, 'aborted_before_validation', REPORT_PHASE_VALIDATION):
                return []

            """Validate, parse, and reconcile harvested RDF data into CKAN objects."""
            available_organizations = dge_harvest_organizations_available()
            self.gather_validation  = None
            gather_stage_info = GatherStageInfo()

            precondition_error = {
                "kind": "init_gather_stage_validation",
                "raw_message": "Error al iniciar el objeto para validar (GatherStageValidation).",
                "phase": current_phase,
            }
            try:
                gather_stage_validation = GatherStageValidation(
                    havester_config_file_path,
                    harvest_job,
                    job_graph_uri,
                    rdf_store,
                    rdf_validator,
                )
                
                precondition_error.update({
                    "kind": "prevalidate_complete_graph",
                    "raw_message": "Error al validar el contenido del fichero de federación.",
                })
                try:
                    gather_stage_validation.prevalidate_complete_graph(available_organizations)
                except RdfValidatorException as exc:
                    log.exception(f'{method_log_prefix} Excepcion: {str(exc)}')
                    self._save_common_structured_gather_report_error(
                        exception = exc,
                        harvest_job=harvest_job,
                        raw_message=exc.raw_message or precondition_error.get('raw_message', None),
                        display_message = exc.display_message or precondition_error.get('display_message', None),
                        phase=current_phase,
                        kind=precondition_error.get('kind', "prevalidate_complete_graph"),
                        message_code=get_common_error_message_code(phase=current_phase, reason=None, exception=exc),
                    ) 
                

                shacl_validator = None
                hvd_shacl_validator = None
                
                precondition_error.update({
                    "kind": "get_root_catalog_uri",
                    "raw_message": "Error al obtener la URI del catálogo a federar.",
                })
                root_catalog = rdf_store.rdf_store_query.get_root_catalog_uri()
                
                precondition_error.update({
                    "kind": "get_data_to_run_catalogs_validation",
                    "raw_message": "Error al obtener los datos para ejecutar la validación del catálogo a federear.",
                })
                shacl_validator, hvd_shacl_validator, harvester_catalog_config, catalogs_uris = gather_stage_validation.get_data_to_run_catalogs_validation(shacl_validator, hvd_shacl_validator)

                num_objects = 0
                catalogs_number = len(catalogs_uris or [])
                for catalog_uri in catalogs_uris or []:
                    num_objects = num_objects + 1
                    log.info(f'{method_log_prefix} #### VALIDATING CATALOG {num_objects} OF {catalogs_number}: {catalog_uri}')
                    precondition_error.update({
                        "kind": "catalog_validation",
                        "raw_message": "Error al validar los metadatos del catálogo {catalog_uri}}."
                        })
                    conforms, catalog_data, vocabulary_validation_error_messages, shacl_messages = gather_stage_validation.validate_catalog(catalog_uri, shacl_validator, hvd_shacl_validator, harvester_catalog_config)
                    self._save_catalog_report_messages(
                            report_messages = ValidationReportMessages(
                                vocabulary_messages = vocabulary_validation_error_messages,
                                shacl_messages = shacl_messages
                            ),
                            entity_uri = catalog_uri,
                            harvest_job = harvest_job,
                            default_payload=precondition_error.get("payload", {})
                            )
                    if conforms:
                        catalog_dict = {DCATAPESSerializerConstants.AVAILABLE_ORGANIZATIONS: available_organizations}
                        parse_conforms, parse_messages, parse_message_details, catalog_dict = self._parse_catalog(parser, catalog_data, catalog_uri, catalog_dict)
                        conforms = conforms and parse_conforms
                        if not conforms:
                            gather_stage_validation.delete_not_conform_catalog(catalog_uri)
                        else:
                            _catalog_uri_catalog_data_dict[catalog_uri] = catalog_dict
                    
                    if not conforms:
                        self._save_catalog_report_messages(
                            report_messages = ValidationReportMessages(deleted_resource = not conforms),
                            entity_uri = catalog_uri,
                            harvest_job = harvest_job,
                            default_payload=precondition_error.get("payload", {})
                        )
                    gather_stage_info.add_catalog(conforms)

                log.debug(f'{method_log_prefix} End catalogs shacl validation')
                if gather_stage_info.total_wrong_catalogs > 0:
                    return self._finish_unsuccessful_structured_gather_stage(
                        harvest_job=harvest_job,
                        raw_message=HarvesterConstants.CATALOG_WITH_ERRORS,
                        display_message=HarvesterConstants.CATALOG_WITH_ERRORS,
                        phase=current_phase,
                        category=REPORT_CATEGORY_COMMON,
                        kind="wrong_catalogs",
                        reason=VALIDATION_REASON_WRONG_CATALOGS,
                        message_code=get_common_error_message_code(phase=current_phase, reason=None, exception=GatherCatalogsWithErrorsError(HarvesterConstants.CATALOG_WITH_ERRORS)),
                        payload={
                            **precondition_error.get("payload", {}),
                        },
                )

                log.debug(f'{method_log_prefix} catalog_dict = {_catalog_uri_catalog_data_dict}')
                log.debug(f'{method_log_prefix} Init dataservices shacl validation')
                precondition_error.update({
                    "kind": "get_data_to_run_dataservices_validation",
                    "raw_message": "Error al obtener los datos para ejecutar la validación de servicios de datos.",
                })
                shacl_validator, hvd_shacl_validator, harvester_dataservice_config, dataservices_uris = gather_stage_validation.get_data_to_run_dataservices_validation(shacl_validator, hvd_shacl_validator)

                num_objects = 0
                dataservices_number = len(dataservices_uris or [])
                for dataservice_uri in dataservices_uris:
                    if self._check_has_job_been_aborted(harvest_job, "aborted_while_dataservices_validation", REPORT_PHASE_VALIDATION):
                        return []
                    num_objects = num_objects + 1
                    log.info(f'{method_log_prefix} #### VALIDATING DATASERVICE {num_objects} OF {dataservices_number}: {dataservice_uri}')                    
                    precondition_error.update({
                        "kind": "validate_dataservice",
                        "raw_message": "Error al validar los metadatos del servicio de datos {dataservice_uri}}.",
                    })

                    conforms, dataservice_data, vocabulary_validation_error_messages, shacl_messages = gather_stage_validation.validate_dataservice(dataservice_uri, shacl_validator, hvd_shacl_validator, harvester_dataservice_config)
                    self._save_dataservice_report_messages(
                            report_messages = ValidationReportMessages(
                                vocabulary_messages= vocabulary_validation_error_messages,
                                shacl_messages= shacl_messages
                            ),
                            entity_uri = dataservice_uri,
                            harvest_job = harvest_job,
                            default_payload=precondition_error.get("payload", {})
                            )
                    dataservice_dict = {DatasetConstants.CONFORMS_TO_SHACL: conforms, DCATAPESSerializerConstants.AVAILABLE_ORGANIZATIONS: available_organizations}
                    
                    parse_conforms, parse_messages, parse_message_details, dataservice_dict, dataservice_guid = self._parse_dataservice(parser, dataservice_data, dataservice_uri, dataservice_dict, gather_stage_validation.owner_organization_id)

                    guids_in_source.append(dataservice_guid)
                    
                    if conforms:
                        gather_stage_parse_utils.add_extras_keys_to_dict(dataservice_dict, dataservice_guid, dataservice_data, dge_harvest_dataservice_uri(dataservice_dict), dataservice_uri)
                        conforms = gather_stage_parse_utils.process_dataservice_after_parse(
                            dataservice_uri, dataservice_dict, 
                            dataservice_guid, parse_conforms, 
                            parse_messages, parse_message_details, harvest_job, 
                            HarvesterConstants.HARVESTER_TYPE, object_ids, 
                            _uri_ho_dict, _dataset_uri_is_served_by_dataservice_ho_id_dict, 
                            self._save_gather_stage_common_structured_object_report_error
                        )
                        if not conforms:
                            gather_stage_validation.delete_not_conform_dataservice(dataservice_uri)
                            guids_to_recover_from_previous_harvester.append(dataservice_guid)
                    if not conforms:
                        self._save_dataservice_report_messages(
                            report_messages = ValidationReportMessages(deleted_resource = not conforms),
                            entity_uri = dataservice_uri,
                            harvest_job = harvest_job,
                            default_payload=precondition_error.get("payload", {})
                        )
                    gather_stage_info.add_dataservice(conforms)
                   
                log.debug(f'{method_log_prefix} End dataservices shacl validation')
                log.debug(f'{method_log_prefix} Init datasets shacl validation')
                precondition_error.update({
                    "kind": "get_data_to_run_datasets_validation",
                    "raw_message": "Error al obtener los datos para ejecutar la validación de conjuntos de datos.",
                })
                shacl_validator, hvd_shacl_validator, harvester_dataset_config, datasets_uris = gather_stage_validation.get_data_to_run_datasets_validation(shacl_validator, hvd_shacl_validator)
                precondition_error.update({
                    "kind": "get_data_to_run_distributions_validation",
                    "raw_message": "Error al obtener los datos para ejecutar la validación de distribuciones de datos.",
                })
                dist_shacl_validator, dist_hvd_shacl_validator, harvester_distribution_config = gather_stage_validation.get_data_to_run_distributions_validation(None, None)

                num_objects = 0
                datasets_number = len(datasets_uris or [])
                for dataset_uri in datasets_uris:
                    if self._check_has_job_been_aborted(harvest_job, "aborted_while_datasets_validation", REPORT_PHASE_VALIDATION):
                        return []
                    num_objects = num_objects + 1
                    log.info(f'{method_log_prefix} #### VALIDATING DATASET {num_objects} OF {datasets_number}: {dataset_uri}')
                    conforms, complete_dataset_data, distribution_conforms_number, vocabulary_validation_error_messages, shacl_messages, distribution_validation_messages = gather_stage_validation.validate_dataset(dataset_uri, shacl_validator, hvd_shacl_validator, dist_shacl_validator, dist_hvd_shacl_validator, harvester_dataset_config, harvester_distribution_config)
                    self._save_dataset_report_messages(
                            report_messages = ValidationReportMessages(
                                vocabulary_messages= vocabulary_validation_error_messages,
                                shacl_messages= shacl_messages
                            ),
                            entity_uri = dataset_uri,
                            harvest_job = harvest_job,
                            default_payload=precondition_error.get("payload", {})
                            )
                    for distribution_uri, distribution_vocabulary_messages, distribution_shacl_messages in distribution_validation_messages:
                        self._save_distribution_report_messages(
                            report_messages=ValidationReportMessages(
                                vocabulary_messages=distribution_vocabulary_messages,
                                shacl_messages=distribution_shacl_messages,
                            ),
                            entity_uri=distribution_uri,
                            harvest_job=harvest_job,
                            default_payload={
                                **precondition_error.get("payload", {}),
                                "dataset_uri": dataset_uri,
                            },
                        )
                    if distribution_conforms_number == 0:
                        
                        self._save_common_structured_gather_report_error(
                            harvest_job=harvest_job,
                            raw_message=HarvesterConstants.NO_VALID_DISTRIBUTION_IN_DATASET.format(dataset_uri),
                            display_message = HarvesterConstants.NO_VALID_DISTRIBUTION_IN_DATASET.format(dataset_uri),
                            phase=current_phase,
                            kind='valid_distribution_in_dataset',
                            reason=VALIDATION_REASON_NO_VALID_DISTRIBUTION_IN_DATASET,
                            message_code=get_common_error_message_code(phase=current_phase, reason=VALIDATION_REASON_NO_VALID_DISTRIBUTION_IN_DATASET),
                        )

                    dataset_dict = {DatasetConstants.CONFORMS_TO_SHACL: conforms, DCATAPESSerializerConstants.AVAILABLE_ORGANIZATIONS: available_organizations}
                    parse_conforms, parse_messages, parse_message_details, dataset_dict, dataset_guid = self._parse_dataset(parser, complete_dataset_data, dataset_uri, dataset_dict, gather_stage_validation.owner_organization_id)
                    guids_in_source.append(dataset_guid)
                    if conforms:
                        gather_stage_parse_utils.add_extras_keys_to_dict(dataset_dict, dataset_guid, complete_dataset_data, dge_harvest_dataset_uri(dataset_dict), dataset_uri)
                        conforms = gather_stage_parse_utils.process_dataset_after_parse(
                            dataset_uri, dataset_dict, 
                            dataset_guid, HarvesterConstants.HARVESTER_TYPE, 
                            parse_conforms, parse_messages, parse_message_details,
                            harvest_job, object_ids, 
                            _uri_ho_dict, _dataset_uri_is_served_by_dataservice_ho_id_dict,
                            self._save_gather_stage_common_structured_object_report_error
                        )
                    if not conforms:
                        gather_stage_validation.delete_not_conform_dataset(dataset_uri)
                        self._save_dataset_report_messages(
                            report_messages = ValidationReportMessages(deleted_resource= not conforms),
                            entity_uri = dataset_uri,
                            harvest_job = harvest_job,
                            default_payload=precondition_error.get("payload", {})
                            )
                        guids_to_recover_from_previous_harvester.append(dataset_guid)
                    gather_stage_info.add_dataset(conforms)
                    # save messages
                    

                log.debug(f'{method_log_prefix} End datasets shacl validation')
                log.debug(f'{method_log_prefix} Deleting all unreferenced nodes')
                rdf_store.rdf_store_delete.drop_all_unreferenced_nodes()
                rdf_store.update_graph_uri(source_graph_uri)
                rdf_store.rdf_store_helper.clear_graph()
                harvester_utils.update_catalog_metadata_in_source_graph(root_catalog, job_graph_uri, source_graph_uri, source_catalog_uri)
                conforms_to_uri = config.get('ckanext.dge_harvest.dcat_ap_es_1_0_0.conforms_to.uri', None)
                import_stage_utils.copy_from_old_harvester_graph_not_conforms_packages(guids_to_recover_from_previous_harvester, previous_source_graph_uri, source_graph_uri, source_catalog_uri, conforms_to_uri, rdf_store)
            except (TypeError, KeyError, ValueError, GatherStageValidationException, FileNotFoundError, RdfValidatorException, RDFStoreException, ShaclValidatorException, VocabularyValidatorException, ValueError, Exception) as e:
                log.exception(f'{method_log_prefix} End method. Exception validating RDF from graph_uri {job_graph_uri}. Exception {type(e).__name__}: {str(e)}')
                return self._finish_unsuccessful_structured_gather_stage(
                    exception = e,
                    harvest_job=harvest_job,
                    display_message="Error en la tarea de federación",
                    raw_message="Error inesperado en la validación de la tarea de federación",
                    phase=current_phase,
                    category=REPORT_CATEGORY_TECHNICAL,
                    kind=precondition_error.get("kind", "global_validation_error"),
                    resource_uri=job_graph_uri,
                    message_code=get_technical_error_message_code(phase=current_phase, reason=None, exception=None),
                    payload=None,
                )


            # Check if some datasets need to be deleted
            object_ids_to_delete = harvester_utils.mark_datasets_for_deletion(guids_in_source, harvest_job)
            log.debug(f'{method_log_prefix} objects_ids =  {object_ids} \n  object_ids_to_delete =  {object_ids_to_delete} ')
            object_ids.extend(object_ids_to_delete)
            log.debug(f'''{method_log_prefix} \n objects_ids =  {object_ids} \n guids_in_source: {guids_in_source} \n
                    _uri_ho_dict = {_uri_ho_dict} \n _dataset_uri_is_served_by_dataservice_ho_id_dict = {_dataset_uri_is_served_by_dataservice_ho_id_dict} \n
                    _catalog_uri_catalog_data_dict = {_catalog_uri_catalog_data_dict}''')
            log.info(f'{method_log_prefix} Returns: {str(gather_stage_info)}')
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
                message_code=get_technical_error_message_code(phase=current_phase, reason=None, exception=None),
            )
            return None

    def fetch_stage(self, harvest_object):
        # Nothing to do here
        return True

    @log_info
    def import_stage(self, harvest_object):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        log.info(f'{method_log_prefix} ### RUNNING IMPORT_STAGE OF HARVEST_OBJECT {harvest_object.id} OF HARVEST_SOURCE {harvest_object.harvest_source_id}') 
        DEFAULT_OBJECT = 'objeto'
        rdf_store = RDFStoreComplete(None)
        current_graph_uri = None
        package_uri_in_source = None
        package_uri_in_ckan = None
        object_type = None
        harvest_object_id = harvest_object.id
        harvest_object_guid = harvest_object.guid
        return_value = None
        current_phase = REPORT_PHASE_IMPORT

        status = self._get_object_extra(harvest_object, 'status')
        if status == 'delete':
            # Delete package
            import_stage_utils.delete_package(harvest_object, self._get_user_name())
            return True

        if harvest_object.content is None:
            error = 'Empty content for object {0}'.format(harvest_object.id)
            log.info(f"{method_log_prefix} Saving objectError for harvest_object_guid {harvest_object_guid}: {error}")
            self._save_import_stage_technical_structured_object_report_error(
                harvest_object=harvest_object,
                display_message = append_support_message(f"No se ha podido obtener el contenido para el recurso con guid {harvest_object_guid}."),
                raw_message=HarvesterConstants.IMPORT_ERROR.format(DEFAULT_OBJECT,error),
                kind = "getting_object_content",
                reason=IMPORT_REASON_EMPTY_OBJECT_CONTENT,
                message_code = get_technical_error_message_code(phase=current_phase, reason=IMPORT_REASON_EMPTY_OBJECT_CONTENT)
            )
            return False

        try:
            package = json.loads(harvest_object.content)
        except ValueError as exc:
            error = f'Could not parse content for object {harvest_object.id}'
            log.exception(f"{method_log_prefix} Saving objectError for harvest_object_guid {harvest_object_guid}: {error}")
            self._save_import_stage_technical_structured_object_report_error(
                exception = exc,
                harvest_object=harvest_object,
                    raw_message=HarvesterConstants.IMPORT_ERROR.format(
                    DEFAULT_OBJECT,
                    error,
                ),
                display_message = append_support_message(f"No se ha podido parsear el contenido para el recurso con guid {harvest_object_guid}."),
                kind="invalid_object_content",
                reason=IMPORT_REASON_WRONG_PARSE_LOAD_OBJECT_CONTENT,
                message_code = get_technical_error_message_code(phase=current_phase, reason=IMPORT_REASON_WRONG_PARSE_LOAD_OBJECT_CONTENT),
            )
            return False

        context = {
            'user': self._get_user_name(),
            'return_id_only': True,
            'ignore_auth': True,
        }


        try:
            # Get the graph_uri for the harvest object, object_type, uri and ckan_uri of package
            current_graph_uri = import_stage_utils.get_graph_uri_for_harvest_object(harvest_object)
            rdf_store.update_graph_uri(current_graph_uri)
            object_type = package.get('type', 'unknown')
            package_uri_in_ckan = harvester_utils.get_value_of_a_package_extras_key(package, CommonPackageConstants.KEY_EXTRAS_CKAN_URI)
            package_uri_in_source = package.get(CommonPackageConstants.KEY_URI, None)

            # Replace harvest_objects with ckan_uris in package data
            if object_type == CommonPackageConstants.KEY_TYPE_DATASET_VALUE:
                missing_related_served_by_dataservices_ho_id, missing_related_access_services_ho_id_by_distribution = import_stage_utils.process_dataset_before_finish_import_stage(package)
                if missing_related_served_by_dataservices_ho_id:
                    self._save_import_stage_technical_structured_object_report_warning(
                        harvest_object=harvest_object,
                        display_message = f"El conjunto de datos {package_uri_in_ckan} no se ha podido relacionar con todos los servicios de datos que lo servían.",
                        raw_message=HarvesterConstants.IMPORT_WARNING.format(object_type, f"One or more DataServices (package_id of harvest_object) associated with dataset {package.id} could not be found (servedByDataservice)."),
                        reason=IMPORT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_THAT_SERVES_DATASET,
                        message_code = get_technical_warning_message_code(phase=current_phase, reason=IMPORT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_THAT_SERVES_DATASET),
                        payload = {"missing_related_served_by_dataservices_ho_id" : (missing_related_served_by_dataservices_ho_id)}
                    )
                if missing_related_access_services_ho_id_by_distribution:
                    self._save_import_stage_technical_structured_object_report_warning(
                        harvest_object=harvest_object,
                        raw_message= HarvesterConstants.IMPORT_WARNING.format(object_type, f"One or more DataServices (package_id of harvest_object) associated with resources of dataset {package.id} could not be found (accessService)."),
                        display_message = f"Las distribuciones del conjunto de datos {package_uri_in_ckan} no se ha podido relacionar con todos los servicios de datos a los que accedían.",
                        kind="missing_related_dataservices_accessed_by_distribution_objects",
                        reason=IMPORT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_ACCESSED_BY_DISTRIBUTION,
                        message_code = get_technical_warning_message_code(phase=current_phase, reason=IMPORT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_ACCESSED_BY_DISTRIBUTION),
                        payload = {"missing_related_access_services_ho_id_by_distribution" : (missing_related_access_services_ho_id_by_distribution)}
                    )
                        
            # Get the last harvested object (if any)
            previous_objects = model.Session.query(HarvestObject) \
                .filter(HarvestObject.guid == harvest_object.guid) \
                .filter(HarvestObject.current == True) \
                .order_by(HarvestObject.gathered.desc()) \
                .all()

            # Flag previous object as not current anymore
            previous_object = None
            for prev_object in previous_objects or []:
                prev_object.current = False
                prev_object.add()
                if not previous_object:
                    previous_object = prev_object
            
            # Flag this object as the current one
            harvest_object.current = True
            harvest_object.add()

            harvest_object_aux = HarvestObject()
            harvest_object_aux.guid = harvest_object.guid
            # Check if a dataset with the same guid exists
            existing_package =self._get_existing_package_by_guid(context, harvest_object.guid)
            hoe_ckan_name = model.Session.query(HarvestObjectExtra) \
                    .filter(HarvestObjectExtra.key == HarvestObjectExtraKeyConstants.HOE_CKAN_NAME_KEY) \
                    .filter(HarvestObjectExtra.harvest_object_id == harvest_object.id) \
                    .first()
                
            hoe_ckan_uri = model.Session.query(HarvestObjectExtra) \
                    .filter(HarvestObjectExtra.key == HarvestObjectExtraKeyConstants.HOE_CKAN_URI_KEY) \
                    .filter(HarvestObjectExtra.harvest_object_id == harvest_object.id) \
                    .first()
            if existing_package:
                log.info(f'{method_log_prefix} There is a saved package with the same guid {harvest_object.guid} --> Update package')

                # Reactivating deleted package
                if (existing_package[CommonPackageConstants.KEY_STATE] == 'deleted'):
                    log.info(f'{method_log_prefix} Reactivating deleted package with id {existing_package[CommonPackageConstants.KEY_ID]}')
                    package[CommonPackageConstants.KEY_STATE] = 'active'
                # return_value can be True is package has been updated; False if an error has happened while updating; 'unchanged' if package have not to be changed. 
                try:
                    return_value = import_stage_utils.import_existing_package(existing_package, package, harvest_object, [hoe_ckan_name, hoe_ckan_uri], context)
                except p.toolkit.ValidationError as e:
                    return_value = False
                    self._save_import_stage_technical_structured_object_report_error(
                        exception = e,
                        harvest_object=harvest_object,
                        raw_message=HarvesterConstants.IMPORT_ERROR.format(object_type, f'Update validation Error: {str(e.error_summary)}'),
                        display_message = append_support_message(f"No se ha podido actualizar el recurso existe {package.get(CommonPackageConstants.KEY_URI, None)}."),
                        kind="package_update_validation_error",
                        message_code = get_technical_error_message_code(phase=current_phase, reason=None, exception=e),
                    )

                package_uri_in_ckan = harvester_utils.get_value_of_a_package_extras_key(package, CommonPackageConstants.KEY_EXTRAS_CKAN_URI)
                harvest_object_aux.package_id = existing_package.get(CommonPackageConstants.KEY_ID, None)         
            else:
                log.info(f'{method_log_prefix} There is NOT a saved package with the same guid {harvest_object.guid} --> Create package')
                # return_value can be True is package has been updated; False if an error has happened while updating; 'unchanged' if package have not to be changed. 
                try:
                    return_value, error = import_stage_utils.import_new_package(package, harvest_object, [hoe_ckan_name, hoe_ckan_uri], context)
                    if error:
                        self._save_import_stage_technical_structured_object_report_error(
                            harvest_object=harvest_object,
                            raw_message=f'RDFHarvester plugin error: {str(error)}',
                            display_message = append_support_message(f"No se ha podido crear el recurso {package.get(CommonPackageConstants.KEY_NAME)}."),
                            kind="after_create_plugin_error",
                            resource_uri=package.get(CommonPackageConstants.KEY_URI, None)
                        )
                except (p.toolkit.ValidationError, Exception) as e:
                    return_value = False
                    self._save_import_stage_technical_structured_object_report_error(
                        exception = e,
                        harvest_object=harvest_object,
                        raw_message= HarvesterConstants.IMPORT_ERROR.format(object_type, f'Create validation Error: {str(e)}'),
                        display_message = append_support_message(f"No se ha podido crear el recurso {hoe_ckan_uri}."),
                        kind="package_create_validation_error",
                        message_code = get_technical_error_message_code(phase=current_phase, reason=None, exception=e),
                    )
                    return False 
                    
                harvest_object_aux.package_id = package.get(CommonPackageConstants.KEY_ID, None)
        except Exception as e:
            errormsg = f"Exception in harvest_object with guid= {harvest_object_guid} and id= ({harvest_object_id}). Exception {type(e).__name__}: {e}"
            log.exception(f"{method_log_prefix} {errormsg}")
            self._save_import_stage_technical_structured_object_report_error(
                exception = e,
                harvest_object=harvest_object,
                raw_message=HarvesterConstants.IMPORT_ERROR.format(
                    object_type,
                    errormsg,
                ),
                display_message = append_support_message(f"No se ha podido importar el recurso con guid {harvest_object_guid}."),
                kind="import_stage_exception",
                message_code = get_technical_error_message_code(phase=current_phase, reason=None, exception=e),
            )
            log.info(f'{method_log_prefix} ### HARVEST_OBJECT {harvest_object.id} OF HARVEST_SOURCE {harvest_object.harvest_source_id} HAS NOT BEEN SUCCESSFULLY UPDATED OR CREATED IN CKANF ROM GRAPH OF CURRENT HARVESTER JOB') 
            return_value = False
        finally:
            try:
                log.info(f'{method_log_prefix} ### HARVEST_OBJECT {harvest_object.id} OF HARVEST_SOURCE {harvest_object.harvest_source_id} HAS BEEN SUCCESSFULLY UPDATED OR CREATED IN CKAN FROM GRAPH OF CURRENT HARVESTER JOB') 
                model.Session.commit()
            except Exception as e:
                errormsg = f"Exception making commit of harvest_object with guid= {harvest_object_guid} and id= ({harvest_object_id}). Exception {type(e).__name__}: {e}"
                log.exception(f"{method_log_prefix} {errormsg}")
                return_value = False
                self._save_import_stage_technical_structured_object_report_error(
                    exception = e,
                    harvest_object=harvest_object,
                    raw_message=errormsg,
                    display_message = append_support_message(f"No se ha podido importar el recurso con guid {harvest_object_guid}."),
                    kind="import_commit_session",
                    message_code = get_technical_error_message_code(phase=current_phase, reason=None, exception=e),
                )
                raise e
            finally:
                # update source graph
                self.import_stage_update_graphs(return_value, rdf_store, harvest_object, object_type, package_uri_in_source,current_graph_uri, package_uri_in_ckan,)
        return return_value

    def import_stage_update_graphs(self, right_import_stage:bool, rdf_store: RDFStoreComplete, harvest_object: HarvestObject,
                                   object_type:str, package_uri_in_source:str, job_graph_uri:str, package_uri_in_ckan: str):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        current_phase = REPORT_PHASE_IMPORT
        try:
            source_graph_uri, source_catalog_uri = generate_graph_uri_and_catalog_uri_from_source_id(harvest_object.harvest_source_id)
            previous_source_graph_uri = f'{source_graph_uri}{HarvesterConstants.SUFFIX_GRAPH_NAME_OF_PREVIOUS_HARVEST}'
            conforms_to_uri = config.get('ckanext.dge_harvest.dcat_ap_es_1_0_0.conforms_to.uri', None)
            if right_import_stage is not None and right_import_stage is True:
                # Update graph of current harvest job graph: update data related to harvest object (uri, lineage, catalog record)
                rdf_store.rdf_store_base.update_graph_uri(job_graph_uri)
                # Update graph of harvest source from graph of current harvest job
                import_stage_utils.add_dataset_or_dataservice_in_target_graph_from_source_graph(
                harvest_object, package_uri_in_source, job_graph_uri, source_graph_uri, source_catalog_uri, conforms_to_uri, rdf_store)
                log.info(f'{method_log_prefix} ### HARVEST_OBJECT {harvest_object.id} OF HARVEST_SOURCE {harvest_object.harvest_source_id} HAS BEEN SUCCESSFULLY ADDED IN SOURCE GRAPH FROM CURRENT HARVESTER JOB') 
            else:
                # keep_previous_version:
                # Update graph of current harvest job: delete data related to harvest object
                rdf_store.update_graph_uri(job_graph_uri)
                deleted_object = import_stage_utils.delete_package_in_rdf_store(object_type, rdf_store.rdf_store_delete, package_uri_in_source)
                if deleted_object and object_type:
                    log.info(f'{method_log_prefix} Deleted node {package_uri_in_source} and/or {package_uri_in_ckan} in graph {job_graph_uri}')
                    if object_type == CommonPackageConstants.KEY_TYPE_DATASET_VALUE:
                        self._save_import_stage_technical_structured_object_report_info(
                            harvest_object=harvest_object,
                            raw_message=HarvesterConstants.DELETE_DATASET.format(package_uri_in_source), 
                            display_message = HarvesterConstants.DELETE_DATASET.format(package_uri_in_source),
                            kind="deleted_invalid_dataset",
                            reason=IMPORT_REASON_DELETED_DATASET,
                            message_code = get_technical_info_message_code(phase=current_phase, reason=IMPORT_REASON_DELETED_DATASET),
                        )
                    elif object_type == CommonPackageConstants.KEY_TYPE_DATASERVICE_VALUE:
                        self._save_import_stage_technical_structured_object_report_info(
                            harvest_object=harvest_object,
                            raw_message=HarvesterConstants.DELETE_DATASERVICE.format(package_uri_in_source), 
                            display_message = HarvesterConstants.DELETE_DATASERVICE.format(package_uri_in_source),
                            kind="deleted_invalid_dataservice",
                            reason=IMPORT_REASON_DELETED_DATASERVICE,
                            message_code = get_technical_info_message_code(phase=current_phase, reason=IMPORT_REASON_DELETED_DATASERVICE),
                        )
                        
                # Update graph of harvest source from previous harvest source grah
                import_stage_utils.add_dataset_or_dataservice_in_target_graph_from_source_graph(
                               harvest_object, package_uri_in_ckan, previous_source_graph_uri, source_graph_uri, source_catalog_uri, conforms_to_uri, rdf_store)
                log.info(f'{method_log_prefix} ### HARVEST_OBJECT {harvest_object.id} OF HARVEST_SOURCE {harvest_object.harvest_source_id} HAS BEEN SUCCESSFULLY ADDED IN SOURCE GRAPH FROM GRAPH OF PREVIOUS HARVESTER') 
        except Exception as e:
            errormsg = f"Exception updating graphs with harvest_object with guid {harvest_object.guid} and id ({harvest_object.id}) from previous harvester graph. Exception {type(e).__name__}: {e}"
            log.exception(f"{method_log_prefix} {errormsg}")
            self._save_import_stage_technical_structured_object_report_error(
                exception = e,
                harvest_object=harvest_object,
                raw_message=HarvesterConstants.IMPORT_ERROR.format(
                    object_type,
                    errormsg,
                ),
                kind="graph_update_error",
                message_code=get_technical_error_message_code(phase=current_phase, reason=None, exception=e),
                display_message = append_support_message(f"No se ha podido importar el recurso con guid {harvest_object.guid}."),
            )
