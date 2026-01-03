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
# -*- coding: utf-8 -*-
import json
import logging
import hashlib
import inspect
from typing import List, Tuple
import ckan.model as model
from ckantoolkit import config
from ckanext.dcat.exceptions import RDFProfileException, RDFParserException
from ckanext.harvest.model import HarvestObject, HarvestJob, HarvestObjectExtra
from ..processors import DGEDCATAPESRDFParser
from ..constants import ( DCATAPESCatalogConstants as CatalogConstants, DCATAPESHarvesterConstants as HarvesterConstants, 
                          DCATAPESDatasetConstants as DatasetConstants, DCATAPESDataserviceConstants as DataserviceConstants,
                          CommonPackageConstants, HarvestObjectExtraKeyConstants, DCATAPESSerializerConstants )
from .dge_harvester import DGERDFHarvester
from .utils import (DcatApEsRdfValidator, RdfValidatorException, ShaclValidatorException,
                    VocabularyValidatorException,  GatherStageValidation, GatherStageValidationException, GatherStageInfo,
                     gather_stage_preprocessing_utils, gather_stage_parse_utils, harvester_utils, import_stage_utils)
from ..rdf_store import (RDFStoreException, RDFStoreComplete, RDFStoreInsertOrUpdate)
from ..utils import dge_harvest_dataset_uri, dge_harvest_dataservice_uri, generate_graph_uri_from_job, generate_graph_uri_and_catalog_uri_from_source_id
from ..decorators import log_debug, log_info
from ..helpers import dge_harvest_organizations_available
log = logging.getLogger(__name__)


IMPORT_STAGE = 'Import'

class DGEDCATAPESRDFHarvester(DGERDFHarvester):
    
    def info(self):
        return {
            'name': HarvesterConstants.HARVESTER_TYPE,
            'title': HarvesterConstants.HARVESTER_TYPE,
            'description': 'Harvester for DGE datasets and dataservices from an RDF graph'
        }

    @log_info
    def _parse_catalog(self, parser, catalog_graph, catalog_uri, catalog_dict) -> Tuple[bool, List[str], dict[str, object]]: 
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
            - catalog: catalog dict
        :rtype: Tuple[bool, List[str], dict[str, object]]
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        conforms = True
        parse_errors = []
        catalog = {}
        try:
            # Graph g contains an only catalog
            parser.g = catalog_graph
            for catalog in parser.catalogs(catalog_dict):
                parse_errors = catalog.get(CatalogConstants.KEY_CATALOG_ERRORS, [])
        except (RDFProfileException, RDFParserException) as e:
            log.warning(f'{method_log_prefix} Exception {type(e)}: {str(e)}', exc_info=True)
            conforms = False
            parse_errors.append(HarvesterConstants.VALIDATION_UNEXPECTED_ERROR_MESSAGE.format(catalog_uri, f"{type(e).__name__}: {e}"))
        conforms = False if parse_errors else True
        return conforms, parse_errors, catalog

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
    def _parse_dataservice(self, parser, dataservice_graph, dataservice_uri, dataservice_dict, owner_org_id) -> Tuple[bool, List[str], dict[str, object], str]: 
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
            - dataservice: dataservice dict
            - dataservice_guid: dataservice guid
        :rtype: Tuple[bool, List[str], dict[str, object], str]
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        conforms = True
        parse_errors = []
        try:
            parser.g = dataservice_graph
            for dataservice in parser.dataservices(dataservice_dict or {}):
                parse_errors = dataservice.get(DataserviceConstants.KEY_ERRORS, [])
                dataservice[DataserviceConstants.KEY_OWNER_ORG] = owner_org_id
                dataservice[DataserviceConstants.KEY_TYPE] = CommonPackageConstants.KEY_TYPE_DATASERVICE_VALUE
                dataservice[DataserviceConstants.KEY_NAME] = self._get_name_dataset_dataservice(dataservice.get(DataserviceConstants.KEY_NAME), 
                                                                                                dataservice.get(DataserviceConstants.KEY_TITLE), 
                                                                                                dataservice.get(DataserviceConstants.KEY_PUBLISHER_ID_MINHAP))
                dataservice_guid = self._get_guid(dataservice)
        except (RDFProfileException, RDFParserException) as e:
            log.warning(f'{method_log_prefix} Exception {type(e)}: {str(e)}', exc_info=True)
            parse_errors.append(HarvesterConstants.VALIDATION_UNEXPECTED_ERROR_MESSAGE.format(dataservice_uri, f"{type(e).__name__}: {e}"))
        conforms = False if parse_errors else True
        return conforms, parse_errors, dataservice, dataservice_guid

    @log_debug
    def _parse_dataset(self, parser, dataset_graph, dataset_uri, dataset_dict, owner_org_id) -> Tuple[bool, List[str], dict[str, object], str]:
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
            - dataset: dataset dict
            - dataset_guid: dataset guid
        :rtype:  -> Tuple[bool, List[str], dict[str, object], str]: 
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        conforms = True
        parse_errors = []
        try:
            parser.g = dataset_graph
            for dataset in parser.datasets(dataset_dict or {}):
                parse_errors = dataset.get(DatasetConstants.KEY_ERRORS, [])

                dataset[DatasetConstants.KEY_OWNER_ORG] = dataset.get(DatasetConstants.KEY_OWNER_ORG, None) or owner_org_id
                dataset[DatasetConstants.KEY_TYPE] = CommonPackageConstants.KEY_TYPE_DATASET_VALUE
                
                dataset[DataserviceConstants.KEY_NAME] = self._get_name_dataset_dataservice(dataset.get(DataserviceConstants.KEY_NAME), 
                                                                                            dataset.get(DataserviceConstants.KEY_TITLE), 
                                                                                            dataset.get(DataserviceConstants.KEY_PUBLISHER_ID_MINHAP))
                dataset_guid = self._get_guid(dataset)
        except (RDFProfileException, RDFParserException) as e:
            log.warning(f'{method_log_prefix} Exception {type(e)}: {str(e)}', exc_info=True)
            parse_errors.append(HarvesterConstants.VALIDATION_UNEXPECTED_ERROR_MESSAGE.format(dataset_uri, f"{type(e).__name__}: {e}"))
        conforms = False if parse_errors else True
        return conforms, parse_errors, dataset, dataset_guid

    @log_debug
    def _load_complete_rdf(self, parser: DGEDCATAPESRDFParser, rdf_store:RDFStoreInsertOrUpdate, harvest_job: HarvestJob, rdf_format: str) -> str:
        ''' 
        Process and store complete RDF in the rdf_store

        :param parser: parser object
        :type parser: DGEDCATAPESRDFParser

        :param harvest_job: harvest job object
        :type harvest_job: HarvestJob
        
        :param rdf_format: RDF format
        :type rdf_format: str
        
        :return: graph uri than contains the complete RDF
        :rtype: str
        ''' 
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        result = None
        last_content_hash = None
        visited_urls = set()
        # Get file contents of first page
        next_page_url = harvest_job.source.url
        log.info(f'{method_log_prefix} Init harvest for harvest_source with url {next_page_url}')

        #Get parser with complete graph
        while next_page_url is not None and next_page_url not in visited_urls:
            log.info(f'{method_log_prefix} Getting info from {next_page_url}')
            next_page_url = self._run_before_downloads(harvest_job, next_page_url)
            if not next_page_url:
                log.debug(f'{method_log_prefix} Error running tasks before download. There is no next_page_url.')
                result = None
                break
                
            content, rdf_format = self._get_content_and_type(next_page_url, harvest_job, 1, content_type=rdf_format)

            content_hash = hashlib.md5()
            if content:
                content_hash.update(content.encode('utf8'))

            if last_content_hash:
                if content_hash.digest() == last_content_hash.digest():
                    log.warning(f'{method_log_prefix} Remote content was the same even when using a paginated URL, skipping')
                    result = None
                    break
            else:
                last_content_hash = content_hash

            content = self._run_after_downloads(harvest_job, content, next_page_url)
            if not content:
                log.debug(f'{method_log_prefix} Error running tasks after download. There is no content.')
                result = None
                break
            try:
                current_parser = parser if parser else DGEDCATAPESRDFParser(profiles=[HarvesterConstants.HARVESTER_PROFILE])
                current_parser.parse(content, _format=rdf_format)
            except (RDFParserException, SyntaxError) as e:
                log.debug(f'{method_log_prefix} Error parsing the content of {next_page_url}. Exception {type(e).__name__}: {str(e)}')
                gather_error = HarvesterConstants.CATALOG_PARSER_ERROR_URL.format(next_page_url, e)
                self._save_gather_error(gather_error, harvest_job)
                result = None
                break
            except Exception as e:
                log.debug(f'{method_log_prefix} Unexpected error parsing the content of {next_page_url}. Unexpected exception {type(e).__name__}: {str(e)}')
                gather_error = gather_error = HarvesterConstants.CATALOG_PARSER_ERROR_URL.format(next_page_url, e)
                self._save_gather_error(gather_error, harvest_job)
                result = None
                break

            current_parser = self._run_after_parsings(harvest_job, current_parser, next_page_url)
            if not current_parser:
                log.debug(f'{method_log_prefix} Error running tasks after parsing. There is no parser.')
                result = None
                break
            
            # Add RDF data to the RDF store
            try:
                query_result = rdf_store.insert_rdf_data(current_parser.g)
                log.debug(f'{method_log_prefix} query_result: {query_result}')
                result = rdf_store.get_graph_uri()
            except RDFStoreException as e:
                log.debug(f'{method_log_prefix} Error storing the content of {next_page_url}. Exception {type(e).__name__}: {str(e)}')
                gather_error = HarvesterConstants.CATALOG_STORE_ERROR_URL.format(next_page_url, HarvesterConstants.VIRTUOSO_LOAD_ERROR.format(next_page_url, e))
                self._save_gather_error(gather_error, harvest_job)
                result = None
                break

            # Add the current URL to the visited set
            visited_urls.add(next_page_url)
            # Get the next URL
            next_page_url = current_parser.next_page(visited_urls)
            log.debug(f'{method_log_prefix} Next page URL: {next_page_url}')
        
        # Drop graph if errors have been found
        if result is None:
            rdf_store.drop_graph()
        return result

    def _finish_unsuccessful_gather_stage(self, gather_error, harvest_job, rdf_store_helper):
        if gather_error and harvest_job:
            self._save_gather_error(gather_error, harvest_job)
        rdf_store_helper.drop_graph()
        return []

    def _has_job_been_aborted(self, harvest_job):
        job_status = model.Session.query(HarvestJob.status).filter(HarvestJob.id == harvest_job.id).scalar()
        return job_status == 'Finished'

    @log_info
    def gather_stage(self, harvest_job: HarvestJob):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        
        if harvest_job.gather_finished is not None:
            log.info('%s End method 0. The gathering stage took more than 2 hours, and the harvest job was renewed before it was finished. Returns: []' % (method_log_prefix))
            return []
        
        # Finish method if job has been aborted
        if self._has_job_been_aborted(harvest_job):
            log.info(f'{method_log_prefix} Harvest_job with {harvest_job.id} has been aborted before its gather_stage started. Returns: []')
            return []
        
        parser = DGEDCATAPESRDFParser(profiles=[HarvesterConstants.HARVESTER_PROFILE])
        rdf_format, _default_catalog_language = self._get_rdf_format_config(harvest_job.source.config)

        guids_in_source = []
        guids_to_recover_from_previous_harvester = []
        object_ids = []
        self._names_taken = []


        _uri_ho_dict = {}
        _dataset_uri_is_served_by_dataservice_ho_id_dict = {}
        _catalog_uri_catalog_data_dict = {}

        # Remove graphs of old harvesting
        _last_graph_of_harvesting = harvester_utils.remove_graphs_of_previous_harvesting(harvest_job)   

        job_graph_uri = generate_graph_uri_from_job(harvest_job)
        source_graph_uri, source_catalog_uri = generate_graph_uri_and_catalog_uri_from_source_id(harvest_job.source_id)
        previous_source_graph_uri = f'{source_graph_uri}{HarvesterConstants.SUFFIX_GRAPH_NAME_OF_PREVIOUS_HARVEST}'
        rdf_store = RDFStoreComplete(job_graph_uri)

        # Load complete RDF
        job_graph_uri = self._load_complete_rdf(parser, rdf_store.rdf_store_insert_or_update, harvest_job, rdf_format)
        if not job_graph_uri:
            log.error(f'{method_log_prefix} No graph to job. Returns: []')
            return []

        #update bnode URIs
        try:
            rdf_store.rdf_store_insert_or_update.replace_uriref_bnodes()
        except RDFStoreException as e:
            log.error(f'{method_log_prefix} Error saving source rdf. Exception {type(e).__name__}: {str(e)}')
            return self._finish_unsuccessful_gather_stage(HarvesterConstants.PREPROCESSING_ERROR.format(harvest_job.source.url, e), harvest_job, rdf_store.rdf_store_helper)

        rdf_store.update_graph_uri(job_graph_uri)
        rdf_validator = DcatApEsRdfValidator(job_graph_uri, rdf_store.rdf_store_query)
        # Preprocess RDF
        try:
            gather_stage_preprocessing_utils.preprocess_source_rdf(rdf_store, job_graph_uri, harvest_job)
        except RDFStoreException as e:
            log.error(f'{method_log_prefix} Error preprocessing the source rdf. Exception {type(e).__name__}: {str(e)}')
            return self._finish_unsuccessful_gather_stage(HarvesterConstants.PREPROCESSING_ERROR.format(harvest_job.source.url, e), harvest_job, rdf_store.rdf_store_helper)

        # Graph backup
        try:
            rdf_store.rdf_store_insert_or_update.copy_source_graph_in_target_graph(source_graph_uri, previous_source_graph_uri)
        except RDFStoreException as e:
            log.error(f'{method_log_prefix} Error doing graph backup. Exception {type(e).__name__}: {str(e)}')
            return self._finish_unsuccessful_gather_stage(HarvesterConstants.PREPROCESSING_ERROR.format(harvest_job.source.url, e), harvest_job, rdf_store.rdf_store_helper)

        # Finish method if job has been aborted
        if self._has_job_been_aborted(harvest_job):
            log.info(f'{method_log_prefix} Harvest_job with {harvest_job.id} has been aborted before its gather_stage started. Returns: []')
            return []

        # Validation
        try:
            available_organizations = dge_harvest_organizations_available()
            gather_stage_info = GatherStageInfo()
            property_prefix =  'ckanext.dge_harvest.dcat_ap_es_1_0_0.' 
            havester_config_file_path = config.get(f'{property_prefix}config.filepath', '')
            gather_stage_validation = GatherStageValidation(havester_config_file_path, harvest_job, job_graph_uri, rdf_store, rdf_validator)
            # prevalidation
            gather_stage_validation.prevalidate_complete_graph(available_organizations)
            # Get validation config
            shacl_validator = None
            hvd_shacl_validator = None
            root_catalog = rdf_store.rdf_store_query.get_root_catalog_uri()
            shacl_validator, hvd_shacl_validator, harvester_catalog_config, catalogs_uris = gather_stage_validation.get_data_to_run_catalogs_validation(shacl_validator, hvd_shacl_validator)
            # Get all catatalogs from graph
            num_objects = 0
            catalogs_number = len(catalogs_uris or [])
            for catalog_uri in catalogs_uris or []:
                num_objects = num_objects + 1
                log.info(f'{method_log_prefix} #### VALIDATING CATALOG {num_objects} OF {catalogs_number}: {catalog_uri}')
                conforms, catalog_data = gather_stage_validation.validate_catalog(catalog_uri, shacl_validator, hvd_shacl_validator, harvester_catalog_config)
                # Parser catalog_data
                if conforms:
                    catalog_dict = {DCATAPESSerializerConstants.AVAILABLE_ORGANIZATIONS: available_organizations}
                    parse_conforms, parse_messages, catalog_dict = self._parse_catalog(parser, catalog_data, catalog_uri, catalog_dict)
                    conforms = conforms and parse_conforms
                    for message in parse_messages or []:
                        self._save_gather_error(message, harvest_job)
                    if not conforms:
                        gather_stage_validation.delete_not_conform_catalog(catalog_uri)
                    else:
                        _catalog_uri_catalog_data_dict[catalog_uri] = catalog_dict
                gather_stage_info.add_catalog(conforms)
            
            log.debug(f'{method_log_prefix} End catalogs shacl validation')

            #Necessary condition to be able to maintain all the elements of previous federations without processing all the elements of the RDF
            if gather_stage_info.total_wrong_catalogs > 0:
                return self._finish_unsuccessful_gather_stage(HarvesterConstants.CATALOG_WITH_ERRORS, harvest_job, rdf_store.rdf_store_helper)

            log.debug(f'{method_log_prefix} catalog_dict = {_catalog_uri_catalog_data_dict}')

            log.debug(f'{method_log_prefix} Init dataservices shacl validation')
            # Validation of dataservices. Dataservice that are referenced in a catalog 
            # Get validation configuration 
            shacl_validator, hvd_shacl_validator, harvester_dataservice_config, dataservices_uris = gather_stage_validation.get_data_to_run_dataservices_validation(shacl_validator, hvd_shacl_validator)
            # Validate each dataservice
            num_objects = 0
            dataservices_number = len(dataservices_uris or [])
            for dataservice_uri in dataservices_uris: 
                # Finish method if job has been aborted
                if self._has_job_been_aborted(harvest_job):
                    log.info(f'{method_log_prefix} Harvest_job with {harvest_job.id} has been aborted before its gather_stage started. Returns: []')
                    raise GatherStageValidationException(f'Harvest_job with {harvest_job.id} has been aborted ')
                num_objects = num_objects + 1
                log.info(f'{method_log_prefix} #### VALIDATING DATASERVICE {num_objects} OF {dataservices_number}: {dataservice_uri}')
                conforms, dataservice_data = gather_stage_validation.validate_dataservice(dataservice_uri, shacl_validator, hvd_shacl_validator, harvester_dataservice_config)
                # Parser dataservice_data
                dataservice_dict = {DatasetConstants.CONFORMS_TO_SHACL: conforms, DCATAPESSerializerConstants.AVAILABLE_ORGANIZATIONS: available_organizations}
                parse_conforms, parse_messages, dataservice_dict, dataservice_guid = self._parse_dataservice(parser, dataservice_data, dataservice_uri, dataservice_dict, gather_stage_validation.owner_organization_id)
                # Append guid to list
                guids_in_source.append(dataservice_guid)
                if conforms:
                    gather_stage_parse_utils.add_extras_keys_to_dict(dataservice_dict, dataservice_guid, dataservice_data, dge_harvest_dataservice_uri(dataservice_dict), dataservice_uri)
                    conforms = gather_stage_parse_utils.process_dataservice_after_parse(dataservice_uri, dataservice_dict, dataservice_guid, parse_conforms, parse_messages, harvest_job, HarvesterConstants.HARVESTER_TYPE, object_ids, _uri_ho_dict, _dataset_uri_is_served_by_dataservice_ho_id_dict)
                    if not conforms:
                        gather_stage_validation.delete_not_conform_dataservice(dataservice_uri)
                        guids_to_recover_from_previous_harvester.append(dataservice_guid)
                gather_stage_info.add_dataservice(conforms)

            log.debug(f'{method_log_prefix} End dataservices shacl validation')

            log.debug(f'{method_log_prefix} Init datasets shacl validation')
            # Validation of datasets and their distributions validation. Datasets that are referenced in a catalog 
            # Get harvester configuration dictionary
            log.debug(f'{method_log_prefix} {gather_stage_validation}')
            log.debug(f'{method_log_prefix} {shacl_validator} {hvd_shacl_validator}')
            shacl_validator, hvd_shacl_validator, harvester_dataset_config, datasets_uris = gather_stage_validation.get_data_to_run_datasets_validation(shacl_validator, hvd_shacl_validator)
            dist_shacl_validator, dist_hvd_shacl_validator, harvester_distribution_config = gather_stage_validation.get_data_to_run_distributions_validation(None, None)
            # Get all datasets referenced in a catalog
            num_objects = 0
            datasets_number = len(datasets_uris or [])
            for dataset_uri in datasets_uris: 
                if self._has_job_been_aborted(harvest_job):
                    log.info(f'{method_log_prefix} Harvest_job with {harvest_job.id} has been aborted before its gather_stage started.')
                    raise GatherStageValidationException(f'Harvest_job with {harvest_job.id} has been aborted ')
                num_objects = num_objects + 1
                log.info(f'{method_log_prefix} #### VALIDATING DATASET {num_objects} OF {datasets_number}: {dataset_uri}')
                conforms, complete_dataset_data = gather_stage_validation.validate_dataset(dataset_uri, shacl_validator, hvd_shacl_validator, dist_shacl_validator, dist_hvd_shacl_validator, harvester_dataset_config, harvester_distribution_config)
                # Parser dataset_data
                dataset_dict = {DatasetConstants.CONFORMS_TO_SHACL: conforms, DCATAPESSerializerConstants.AVAILABLE_ORGANIZATIONS: available_organizations}
                parse_conforms, parse_messages, dataset_dict, dataset_guid = self._parse_dataset(parser, complete_dataset_data, dataset_uri, dataset_dict, gather_stage_validation.owner_organization_id)
                # Append guid to list
                guids_in_source.append(dataset_guid)
                if conforms:
                    gather_stage_parse_utils.add_extras_keys_to_dict(dataset_dict, dataset_guid, complete_dataset_data, dge_harvest_dataset_uri(dataset_dict), dataset_uri)
                    conforms = gather_stage_parse_utils.process_dataset_after_parse(dataset_uri, dataset_dict, dataset_guid, HarvesterConstants.HARVESTER_TYPE, parse_conforms, parse_messages, harvest_job, object_ids, _uri_ho_dict, _dataset_uri_is_served_by_dataservice_ho_id_dict)
                if not conforms:
                    gather_stage_validation.delete_not_conform_dataset(dataset_uri)
                    guids_to_recover_from_previous_harvester.append(dataset_guid)
                gather_stage_info.add_dataset(conforms)
            log.debug(f'{method_log_prefix} End datasets shacl validation')

            # Drop all unreferenced node in rdf store
            log.debug(f'{method_log_prefix} Deleting all unreferenced nodes')
            rdf_store.rdf_store_delete.drop_all_unreferenced_nodes()
            # Clear and update source graph
            rdf_store.update_graph_uri(source_graph_uri)
            rdf_store.rdf_store_helper.clear_graph()
            harvester_utils.update_catalog_metadata_in_source_graph(root_catalog, job_graph_uri, source_graph_uri, source_catalog_uri)
            
            #Copy from old graph all not conforms datasets and dataservices
            conforms_to_uri = config.get('ckanext.dge_harvest.dcat_ap_es_1_0_0.conforms_to.uri', None)
            import_stage_utils.copy_from_old_harvester_graph_not_conforms_packages(guids_to_recover_from_previous_harvester, previous_source_graph_uri, source_graph_uri,source_catalog_uri, conforms_to_uri, rdf_store)

        except (KeyError, GatherStageValidationException, FileNotFoundError, RdfValidatorException, RDFStoreException, ShaclValidatorException, VocabularyValidatorException, ValueError, Exception) as e:
            if not isinstance(e, GatherStageValidationException):
                log.error(f'{method_log_prefix} End method. Exception validating RDF from graph_uri {job_graph_uri}. Exception {type(e).__name__}: {str(e)}', exc_info=True)
            log.warning(f'{method_log_prefix} Exception {type(e)}: {str(e)}', exc_info=True)
            object_ids = self._finish_unsuccessful_gather_stage(HarvesterConstants.SHACL_VALIDATION_ERROR.format(harvest_job.source.url, e), harvest_job, rdf_store.rdf_store_helper)
            # raise the exception for the ckanext.harvest.queue.gather_stage method, delete all created harvest objects
            raise e

        # Check if some datasets need to be deleted
        object_ids_to_delete = harvester_utils.mark_datasets_for_deletion(guids_in_source, harvest_job)
        log.debug(f'{method_log_prefix} objects_ids =  {object_ids} \n  object_ids_to_delete =  {object_ids_to_delete} ')
        object_ids.extend(object_ids_to_delete)
        log.debug(f'''{method_log_prefix} \n objects_ids =  {object_ids} \n guids_in_source: {guids_in_source} \n
                  _uri_ho_dict = {_uri_ho_dict} \n _dataset_uri_is_served_by_dataservice_ho_id_dict = {_dataset_uri_is_served_by_dataservice_ho_id_dict} \n
                  _catalog_uri_catalog_data_dict = {_catalog_uri_catalog_data_dict}''')
        log.info(f'{method_log_prefix} Returns: {str(gather_stage_info)}')
        return object_ids

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

        status = self._get_object_extra(harvest_object, 'status')
        if status == 'delete':
            # Delete package
            import_stage_utils.delete_package(harvest_object, self._get_user_name())
            return True

        if harvest_object.content is None:
            error = 'Empty content for object {0}'.format(harvest_object.id)
            log.info(f"{method_log_prefix} Saving objectError for harvest_object_guid {harvest_object_guid}: {error}")
            self._save_object_error(HarvesterConstants.IMPORT_ERROR.format(DEFAULT_OBJECT, error), harvest_object, IMPORT_STAGE)
            return False

        try:
            package = json.loads(harvest_object.content)
        except ValueError:
            error = f'Could not parse content for object {harvest_object.id}'
            log.info(f"{method_log_prefix} Saving objectError for harvest_object_guid {harvest_object_guid}: {error}", exc_info=True)
            self._save_object_error(HarvesterConstants.IMPORT_ERROR.format(DEFAULT_OBJECT, error), harvest_object, IMPORT_STAGE)
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
                import_stage_utils.process_dataset_before_finish_import_stage(package, harvest_object)

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
                return_value = import_stage_utils.import_existing_package(existing_package, package, harvest_object, [hoe_ckan_name, hoe_ckan_uri], context)
                package_uri_in_ckan = harvester_utils.get_value_of_a_package_extras_key(package, CommonPackageConstants.KEY_EXTRAS_CKAN_URI)
                harvest_object_aux.package_id = existing_package.get(CommonPackageConstants.KEY_ID, None)         
            else:
                log.info(f'{method_log_prefix} There is NOT a saved package with the same guid {harvest_object.guid} --> Create package')
                # return_value can be True is package has been updated; False if an error has happened while updating; 'unchanged' if package have not to be changed. 
                return_value = import_stage_utils.import_new_package(package, harvest_object, [hoe_ckan_name, hoe_ckan_uri], context)
                harvest_object_aux.package_id = package.get(CommonPackageConstants.KEY_ID, None)
        except Exception as e:
            errormsg = f"Exception in harvest_object with guid= {harvest_object_guid} and id= ({harvest_object_id}). Exception {type(e).__name__}: {e}"
            log.error(f"{method_log_prefix} {errormsg}", exc_info=True)
            self._save_object_error(HarvesterConstants.IMPORT_ERROR.format(object_type, errormsg), harvest_object, IMPORT_STAGE)
            log.info(f'{method_log_prefix} ### HARVEST_OBJECT {harvest_object.id} OF HARVEST_SOURCE {harvest_object.harvest_source_id} HAS NOT BEEN SUCCESSFULLY UPDATED OR CREATED IN CKANF ROM GRAPH OF CURRENT HARVESTER JOB') 
            return_value = False
        finally:
            try:
                log.info(f'{method_log_prefix} ### HARVEST_OBJECT {harvest_object.id} OF HARVEST_SOURCE {harvest_object.harvest_source_id} HAS BEEN SUCCESSFULLY UPDATED OR CREATED IN CKAN FROM GRAPH OF CURRENT HARVESTER JOB') 
                model.Session.commit()
            except Exception as e:
                errormsg = f"Exception making commit of harvest_object with guid= {harvest_object_guid} and id= ({harvest_object_id}). Exception {type(e).__name__}: {e}"
                log.error(f"{method_log_prefix} {errormsg}")
                return_value = False
                raise e
            finally:
                # update source graph
                self.import_stage_update_graphs(return_value, rdf_store, harvest_object, object_type, package_uri_in_source,current_graph_uri, package_uri_in_ckan,)
        return return_value

    def import_stage_update_graphs(self, right_import_stage:bool, rdf_store: RDFStoreComplete, harvest_object: HarvestObject,
                                   object_type:str, package_uri_in_source:str, job_graph_uri:str, package_uri_in_ckan: str):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
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
                import_stage_utils.delete_package_in_rdf_store(object_type, rdf_store.rdf_store_delete, harvest_object, package_uri_in_source)
                log.info(f'{method_log_prefix} Deleted node {package_uri_in_source} and/or {package_uri_in_ckan} in graph {job_graph_uri}')

                # Update graph of harvest source from previous harvest source grah
                import_stage_utils.add_dataset_or_dataservice_in_target_graph_from_source_graph(
                               harvest_object, package_uri_in_ckan, previous_source_graph_uri, source_graph_uri, source_catalog_uri, conforms_to_uri, rdf_store)
                log.info(f'{method_log_prefix} ### HARVEST_OBJECT {harvest_object.id} OF HARVEST_SOURCE {harvest_object.harvest_source_id} HAS BEEN SUCCESSFULLY ADDED IN SOURCE GRAPH FROM GRAPH OF PREVIOUS HARVESTER') 
        except Exception as e:
            errormsg = f"Exception updating graphs with harvest_object with guid {harvest_object.guid} and id ({harvest_object.id}) from previous harvester graph. Exception {type(e).__name__}: {e}"
            log.error(f"{method_log_prefix} {errormsg}", exc_info=True)
            self._save_object_error(HarvesterConstants.IMPORT_ERROR.format(object_type, errormsg), harvest_object, IMPORT_STAGE)    
