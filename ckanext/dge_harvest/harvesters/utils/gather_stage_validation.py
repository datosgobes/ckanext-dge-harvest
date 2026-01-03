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

import logging
import time
import traceback
import inspect

from typing import List, Tuple, Union
from rdflib import URIRef, Graph
from ckanext.dge_harvest import helpers as dhh
from ckanext.harvest.model import (HarvestGatherError, HarvestJob)
from ...constants import (DCATAPESConfigConstants as CC,
                            DCATAPESHarvesterConstants as HarvesterConstants, 
                            DCATAPESPrefixConstants as PrefixConstants,
                            DcatClassNameEnum) 
from ...constants.dcat_ap_es_constants import DCAT, ADMS
from ...rdf_store  import RDFStoreComplete
from .shacl_validator import ShaclValidator
from .vocabulary_validator import VocabularyValidator
from ...harvester_config_reader import HarvesterConfigReader
from .rdf_validator import DcatApEsRdfValidator, RdfValidatorException
from . import gather_stage_validation_utils
from ...decorators import log_debug, log_info

log = logging.getLogger(__name__)

class GatherStageValidationException(Exception):
    def __init__(self, msg=None) -> None:
        Exception.__init__(self, msg)
        self.msg = msg

class GatherStageValidation():
    """
    This class is responsible for processing certain aspects in the gather stage of the harvest.
    """
    _save_gather_error = HarvestGatherError.create 

    def _get_log_prefix(self, method_name):
        return f'[{self.__class__.__name__}][{method_name}]'
    
    def __init__(self, havester_config_file_path:str, harvest_job:HarvestJob, graph_uri:str, rdf_store:RDFStoreComplete, rdf_validator:DcatApEsRdfValidator):
        """
        To create an object of this class is necessary:
        
        :param havester_config_file_path: harvester config file path for all properties related to this federation
        :type havester_config_file_path: str
        
        :param harvest_job: object whith the harvester job that is in execution
        :type harvest_job: HarvesterJob

        :param graph_uri: URI of graph where catalog is stored
        :type graph_uri: str
        
        :param rdf_store: object with the conection to RDF Store where the graph is stored
        :type rdf_store: RDFStoreComplete

        :param rdf_validator: RDF validator to use
        :type rdf_validator: DcatApEsRdfValidator
        """
        if not havester_config_file_path:
            raise ValueError("havester_config_file_path is required for GatherStageProcessor.")
        self.havester_config_file_path = havester_config_file_path
        if not harvest_job:
            raise ValueError("harvest_job is required for GatherStageProcessor.")
        self.harvest_job = harvest_job
        self.owner_organization_id, self.owner_organization_minhap = gather_stage_validation_utils.get_owner_organization_from_harvester_job(self.harvest_job)
        if not graph_uri:
            raise ValueError("graph_uri is required for GatherStageProcessor.")
        self.graph_uri = graph_uri
        if not rdf_store:
            raise ValueError("rdf_store is required for GatherStageProcessor.")
        self.rdf_store = rdf_store
        if not rdf_validator:
            raise ValueError("rdf_validator is required for GatherStageProcessor.")
        self.rdf_validator = rdf_validator
        
        # Object that allows read the configuration of harvester
        self.harvester_config_reader = None
        # vocabulary_validator: object that makes the validation of vocabularies
        self.vocabulary_validator = None 
        # root catalog URI of graph
        self.root_catalog_uri = None
        self._setup_additional_config()

    def _setup_additional_config(self):
        self.harvester_config_reader = HarvesterConfigReader(self.havester_config_file_path)
        self.vocabulary_validator = VocabularyValidator(
                    rdf_store = self.rdf_store.rdf_store_helper,
                    vocabularies = self.harvester_config_reader.get_section_property_as_a_list(CC.SECTION_BASIC, 'vocabularies.uris', []),
                    vocabulary_graph_name = self.harvester_config_reader.get_property(CC.SECTION_BASIC, 'vocabularies.graph_name', None),
                    elements_belonging_to_vocabulary = {}, 
                    elements_unbelonging_to_vocabulary = {})

    @log_info
    def prevalidate_complete_graph(self, available_publisher:dict[str, List[str]]=None) -> None:
        '''
        Validate complete RDF. An error at this point causes the harvesting task to terminate
        
        :param available_publisher: allowed publishers
        :type  available_publisher: dict[str, List[str]]

        :raises RdfValidatorException
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            self.root_catalog_uri = self.rdf_validator.check_if_unique_root_catalog_by_graph()
            available_publisher_dict = available_publisher or dhh.dge_harvest_organizations_available()
            avalible_publisher_id_minhap = available_publisher_dict.keys()
            avalible_publisher_id_minhap = [PrefixConstants.PUBLISHER_PREFIX + id_minhap for id_minhap in avalible_publisher_id_minhap]
            self.rdf_validator.check_if_publishers_are_right(avalible_publisher_id_minhap)
            self.rdf_validator.check_if_creators_are_right(avalible_publisher_id_minhap)
        except (RdfValidatorException, Exception) as e:
            log.error(f'{method_log_prefix} End method. Exception prevalidating complete RDF from graph_uri {self.graph_uri}. Exception {type(e).__name__}: {str(e)}')
            self._save_gather_error(HarvesterConstants.SHACL_VALIDATION_ERROR.format(self.harvest_job.source.url, e), self.harvest_job)
            raise GatherStageValidationException(e)
        log.debug(f'{method_log_prefix} Root catalog uri = {self.root_catalog_uri}')

    def _get_validation_configuration(self, shacl_validator, hvd_shacl_validator, section):
        if shacl_validator is None or hvd_shacl_validator is None:
            default_ontology_uri_list = self.harvester_config_reader.get_section_property_as_a_list(CC.SECTION_BASIC,'shacl.ontology', [])
            shacl_validator = ShaclValidator(shacl_shapes_uri_list = None, ontology_uri_list = default_ontology_uri_list)
            hvd_shacl_validator = ShaclValidator(shacl_shapes_uri_list = None, ontology_uri_list = default_ontology_uri_list)
        # Get harvester configuration dictionary
        harvester_catalog_config = gather_stage_validation_utils.get_harvester_config_dict(self.harvester_config_reader, section)
        shacl_validator.load_shacl_shapes_graph(harvester_catalog_config.get(CC.SHACL_SHAPES, None))
        hvd_shacl_validator.load_shacl_shapes_graph(harvester_catalog_config.get(CC.COMBINED_SHACL_SHAPES, None))
        return shacl_validator, hvd_shacl_validator, harvester_catalog_config

    @log_debug
    def get_data_to_run_catalogs_validation(self, shacl_validator:ShaclValidator, hvd_shacl_validator:ShaclValidator) -> Tuple[ShaclValidator, ShaclValidator, HarvesterConfigReader, List[str]]:
        '''
        Gets the data to validate catalogs (vocabulary and shacl) and the catalogs URIs
        
        :param shacl_validator: object that makes the shacl validation
        :type shacl_validator: ShaclValidator
        
        :param hvd_shacl_validator: object that makes the hvd shacl validation
        :type hvd_shacl_validator: ShaclValidator
        
        :returns a Tuple with:
            - An object to run a shacl validation
            - An object to run a hvd shacl validation
            - An object with config to validation
            - A list whith catalogs' URIs to validate
        :rType: Tuple[ShaclValidator, ShaclValidator, HarvesterConfigReader, List[str]]
        '''        
        shacl_validator, hvd_shacl_validator, harvester_catalog_config = self._get_validation_configuration(shacl_validator, hvd_shacl_validator, CC.SECTION_CATALOG)
        catalogs_uris = self.rdf_store.rdf_store_query.get_catalogs_uris_sorted_by_depth_level()
        return shacl_validator, hvd_shacl_validator, harvester_catalog_config, catalogs_uris

    @log_info
    def validate_catalog(self, catalog_uri:str, shacl_validator:ShaclValidator, hvd_shacl_validator:ShaclValidator, harvester_config_dict:dict[str, Union[List[str], dict[str, List[str]]]]) -> Tuple[bool, Graph]:
        '''
        Validate if data in catalog_uri is conforms to vocabulary and shacl templates
        
        :param catalog_uri: URI of catalog to validate
        :type catalog_uri: str
        
        :param shacl_validator: object that makes the shacl validation
        :type shacl_validator: ShaclValidator
        
        :param hvd_shacl_validator: object that makes the hvd shacl validation
        :type hvd_shacl_validator: ShaclValidator
        
        :param harvester_config_dict: Dictionary with the configuration of catalog harvester.
        :type harvester_config_dict: dict[str, Union[List[str], dict[str, List[str]]]]
        
        :returns a Tuple:
            - True if catalog is conforms, False in other case
            - graph with catalog data
        :rtype: Tupla[bool, Graph]
        '''        
        if not harvester_config_dict:
            harvester_config_dict = {}
        metadata_vocabularies = harvester_config_dict.get(CC.METADATA_VOCABULARIES_DICT, None)
        combined_metadata_vocabularies = harvester_config_dict.get(CC.COMBINED_METADATA_VOCABULARIES_DICT, None)
        # check vocabularies:
        catalog_data = self.rdf_store.rdf_store_query.get_customized_node(node_uri = catalog_uri,
                                                                              predicates_to_exclude = [],
                                                                              node_classes_to_exclude = [],
                                                                              predicates_to_include_only_their_type = []
                                                                              )

        # check vocabularies and shacl templates:
        conforms, vocabulary_validation_error_messages, shacl_messages = gather_stage_validation_utils.check_vocabulary_and_shacl_validation(catalog_uri, catalog_data, self.vocabulary_validator, shacl_validator, hvd_shacl_validator, metadata_vocabularies, combined_metadata_vocabularies)
        for message in vocabulary_validation_error_messages or []:
            self._save_gather_error(f'Error in catalog {catalog_uri}. {message}', self.harvest_job)
        for message in shacl_messages or []:
            self._save_gather_error(message, self.harvest_job)
        if not conforms:
            self.delete_not_conform_catalog(catalog_uri)
            catalog_data = None
        return conforms, catalog_data

    @log_info
    def delete_not_conform_catalog(self, catalog_uri):
        self.rdf_store.rdf_store_delete.delete_catalogs_in_graph(([catalog_uri] + (self.rdf_store.rdf_store_query.get_subcatalogs_uris_of_a_catalog(catalog_uri) or [])))
        self._save_gather_error(HarvesterConstants.DELETE_CATALOG.format(catalog_uri), self.harvest_job)

    @log_debug
    def get_data_to_run_dataservices_validation(self, shacl_validator, hvd_shacl_validator) -> Tuple[ShaclValidator, ShaclValidator, HarvesterConfigReader, List[str]]:
        '''
        Gets the data to validate dataservices (vocabulary and shacl) and the dataservices URIs
        
        :returns a Tuple with:
            - An object to run a shacl validation
            - An object to run a hvd shacl validation
            - An object with config to validation
            - A list whith dataservices' URIs to validate
        :rType: Tuple[ShaclValidator, ShaclValidator, HarvesterConfigReader, List[str]]
        '''        
        shacl_validator, hvd_shacl_validator, harvester_dataservice_config = self._get_validation_configuration(shacl_validator, hvd_shacl_validator, CC.SECTION_DATASERVICE)
        #Load dataservices referenced in a catalog
        all_dataservices = self.rdf_store.rdf_store_query.get_uris_from_referenced_datasets_or_dataservices_in_catalogs_of_a_graph(DcatClassNameEnum.DATASERVICE)
        return shacl_validator, hvd_shacl_validator, harvester_dataservice_config, all_dataservices

    @log_info
    def validate_dataservice(self, dataservice_uri:str, shacl_validator:ShaclValidator, hvd_shacl_validator:ShaclValidator, harvester_config_dict:dict[str, Union[List[str], dict[str, List[str]]]]) -> Tuple[bool, Graph]:
        '''
        Validate if data in dataservice_uri is conforms to vocabulary and shacl templates
        
        :param dataservice_uri: URI of dataservice to validate
        :type dataservice_uri: str
        
        :param graph_uri: URI of graph where catalog is stored
        :type graph_uri: str
        
        :param hvd_shacl_validator: object that makes the shacl validation
        :type hvd_shacl_validator: ShaclValidator
        
        :param harvester_config_dict: Dictionary with the configuration of dataservice harvester.
        :type harvester_config_dict: dict[str, Union[List[str], dict[str, List[str]]]]
        
        :returns a Tuple:
            - True if dataservice is conforms, False in other case
            - graph with dataservice data
        :rtype: Tupla[bool, Graph]
        '''        
        if not harvester_config_dict:
            harvester_config_dict = {}
        metadata_vocabularies = harvester_config_dict.get(CC.METADATA_VOCABULARIES_DICT, None)
        combined_metadata_vocabularies = harvester_config_dict.get(CC.COMBINED_METADATA_VOCABULARIES_DICT, None)
        # check vocabularies:
        dataservice_data = self.rdf_store.rdf_store_query.get_customized_node(node_uri = dataservice_uri,
                                                                              predicates_to_exclude = [],
                                                                              node_classes_to_exclude = [],
                                                                              predicates_to_include_only_their_type = []
                                                                              )
        # check vocabularies and shacl templates:
        conforms, vocabulary_validation_error_messages, shacl_messages = gather_stage_validation_utils.check_vocabulary_and_shacl_validation(dataservice_uri, dataservice_data, self.vocabulary_validator, shacl_validator, hvd_shacl_validator, metadata_vocabularies, combined_metadata_vocabularies)
        for message in vocabulary_validation_error_messages or []:
            self._save_gather_error(f'Error in dataservice {dataservice_uri}. {message}', self.harvest_job)
        for message in shacl_messages or []:
            self._save_gather_error(message, self.harvest_job)
        if not conforms:
            # if not conforms, drop dataservice in graph
            self.delete_not_conform_dataservice(dataservice_uri)
        return conforms, dataservice_data

    @log_info
    def delete_not_conform_dataservice(self, dataservice_uri):
        self.rdf_store.rdf_store_delete.delete_dataservice_in_graph(dataservice_uri)
        self._save_gather_error(HarvesterConstants.DELETE_DATASERVICE.format(dataservice_uri), self.harvest_job)

    @log_debug
    def get_data_to_run_datasets_validation(self, shacl_validator, hvd_shacl_validator) -> Tuple[ShaclValidator, ShaclValidator, HarvesterConfigReader, List[str]]:
        '''
        Gets the data to validate datasets (vocabulary and shacl) and the datasets URIs
        
        :returns a Tuple with:
            - An object to run a shacl validation
            - An object to run a hvd shacl validation
            - An object with config to validation
            - A list whith dataservices' URIs to validate
        :rType: Tuple[ShaclValidator, ShaclValidator, HarvesterConfigReader, List[str]]
        '''
        shacl_validator, hvd_shacl_validator, harvester_dataset_config = self._get_validation_configuration(shacl_validator, hvd_shacl_validator, CC.SECTION_DATASET)
        #Load datasets referenced in a catalog
        all_datasets = self.rdf_store.rdf_store_query.get_uris_from_referenced_datasets_or_dataservices_in_catalogs_of_a_graph(DcatClassNameEnum.DATASET)
        return shacl_validator, hvd_shacl_validator, harvester_dataset_config, all_datasets

    @log_info
    def validate_dataset(self, dataset_uri:str, shacl_validator:ShaclValidator, hvd_shacl_validator:ShaclValidator, dist_shacl_validator:ShaclValidator, dist_hvd_shacl_validator:ShaclValidator, harvester_dataset_config_dict:dict[str, Union[List[str], dict[str, List[str]]]], harvester_distribution_config_dict:dict[str, Union[List[str], dict[str, List[str]]]]) -> Tuple[bool, Graph]:
        '''
        Validate if data in dataset_uri is conforms to vocabulary and shacl templates
        
        :param dataset_uri: URI of dataset to validate
        :type dataset_uri: str
        
        :param shacl_validator: object that makes the shacl validation od dataset
        :type shacl_validator: ShaclValidator
        
        :param hvd_shacl_validator: object that makes the shacl validation of dataset
        :type hvd_shacl_validator: ShaclValidator
        
        :param dist_shacl_validator: object that makes the shacl validation of distribution
        :type dist_shacl_validator: ShaclValidator
        
        :param dist_hvd_shacl_validator: object that makes the shacl validation of distribution
        :type dist_hvd_shacl_validator: ShaclValidator
        
        :param harvester_dataset_config_dict: Dictionary with the configuration of dataset harvester.
        :type harvester_dataset_config_dict: dict[str, Union[List[str], dict[str, List[str]]]]
        
        :param harvester_distribution_config_dict: Dictionary with the configuration of distribution harvester.
        :type harvester_distribution_config_dict: dict[str, Union[List[str], dict[str, List[str]]]]
        
        :returns a Tuple:
            - True if dataservice is conforms, False in other case
            - graph with dataservice data
        :rtype: Tupla[bool, Graph]
        '''        
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        
        # Harvester dataset config
        if not harvester_dataset_config_dict:
            harvester_dataset_config_dict = {}
        metadata_vocabularies = harvester_dataset_config_dict.get(CC.METADATA_VOCABULARIES_DICT, None)
        combined_metadata_vocabularies = harvester_dataset_config_dict.get(CC.COMBINED_METADATA_VOCABULARIES_DICT, None)
        # Get dataset graph without data distribution
        dataset_data = self.rdf_store.rdf_store_query.get_customized_node(node_uri = dataset_uri,
                                                                              predicates_to_exclude = [],
                                                                              node_classes_to_exclude = [],
                                                                              predicates_to_include_only_their_type = [DCAT.distribution, ADMS.sample]
                                                                        )
        # check vocabularies and shacl templates:
        conforms, vocabulary_validation_error_messages, shacl_messages = gather_stage_validation_utils.check_vocabulary_and_shacl_validation(dataset_uri, dataset_data, self.vocabulary_validator, shacl_validator, hvd_shacl_validator, metadata_vocabularies, combined_metadata_vocabularies)
        for message in vocabulary_validation_error_messages or []:
            self._save_gather_error(f'Error in dataset {dataset_data}. {message}', self.harvest_job)
        for message in shacl_messages or []:
            self._save_gather_error(message, self.harvest_job)

        log.debug(f'{method_log_prefix} Init distributions shacl validation')
        # Get distribution uris
        sample_uris = set(dataset_data.objects(subject=URIRef(dataset_uri), predicate=URIRef(ADMS.sample)))
        distribution_uris = set(dataset_data.objects(subject=URIRef(dataset_uri), predicate=URIRef(DCAT.distribution)))
        all_distribution_uris = sample_uris | distribution_uris
        all_distribution_conforms = True
        distribution_conforms_number = 0
        complete_dataset_data = dataset_data
        num_distr = 0
        total_number_of_distributions = len(all_distribution_uris)
        for distribution_uri in all_distribution_uris:
            num_distr = num_distr + 1
            log.info(f'{method_log_prefix} #### VALIDATING DISTRIBUTION {num_distr} OF {total_number_of_distributions} OF DATASET {dataset_uri}: {distribution_uri}')
            distribution_conforms, distribution_data = self._validate_distribution(dataset_uri, distribution_uri, dist_shacl_validator, dist_hvd_shacl_validator, harvester_distribution_config_dict)
            all_distribution_conforms = all_distribution_conforms and distribution_conforms
            # to know if dataset has conforms distribution in dcat:distribution
            if distribution_conforms and distribution_uri in distribution_uris:
                distribution_conforms_number += 1
            complete_dataset_data += distribution_data
        if distribution_conforms_number == 0:
            self._save_gather_error(HarvesterConstants.NO_VALID_DISTRIBUTION_IN_DATASET.format(dataset_uri), self.harvest_job)
        log.debug(f'{method_log_prefix} End distribution shacl validation')
        if not conforms or not all_distribution_conforms or distribution_conforms_number == 0:
            # if not conforms, drop dataset in graph
            conforms = False
            self.delete_not_conform_dataset(dataset_uri)
        return conforms, complete_dataset_data

    @log_info
    def delete_not_conform_dataset(self, dataset_uri):
        self.rdf_store.rdf_store_delete.delete_dataset_in_graph(dataset_uri)
        self._save_gather_error(HarvesterConstants.DELETE_DATASET.format(dataset_uri), self.harvest_job)

    @log_debug
    def get_data_to_run_distributions_validation(self, shacl_validator, hvd_shacl_validator) -> Tuple[ShaclValidator, ShaclValidator, HarvesterConfigReader, List[str]]:
        '''
        Gets the data to validate distributions (vocabulary and shacl)
        
        :returns a Tuple with:
            - An object to run a shacl validation
            - An object to run a hvd shacl validation
            - An object with config to validation
            - A list whith dataservices' URIs to validate
        :rType: Tuple[ShaclValidator, ShaclValidator, HarvesterConfigReader, List[str]]
        '''
        shacl_validator, hvd_shacl_validator, harvester_distribution_config = self._get_validation_configuration(shacl_validator, hvd_shacl_validator, CC.SECTION_DISTRIBUTION)
        return shacl_validator, hvd_shacl_validator, harvester_distribution_config

    @log_info
    def _validate_distribution(self, dataset_uri: str, distribution_uri:str, shacl_validator:ShaclValidator, hvd_shacl_validator:ShaclValidator, harvester_distribution_config_dict:dict[str, Union[List[str], dict[str, List[str]]]]) -> Tuple[bool,Graph]:
        '''
        Get distribution data and check if data is conforms to vocabulary 
        
        :param dataset_uri: URI of dataset 
        :type dataset_uri: str
                
        :param distribution_uri: URI of distribution to validate
        :type distribution_uri: str
        
        :param shacl_validator: object that makes the shacl validation od dataset
        :type shacl_validator: ShaclValidator
        
        :param hvd_shacl_validator: object that makes the shacl validation of dataset
        :type hvd_shacl_validator: ShaclValidator
                
        :param vocabulary_validator: object that makes the validation of vocabularies
        :type vocabulary_validator: VocabularyValidator
        
        :param harvester_distribution_config_dict: Dictionary with the configuration of distribution harvester.
        :type harvester_distribution_config_dict: dict[str, Union[List[str], dict[str, List[str]]]]
        
        :returns: True if distribution is conforms, False in other case
        :rtype: bool
        '''        
        # Harvester distribution config
        if not harvester_distribution_config_dict:
            harvester_distribution_config_dict = {}

        metadata_vocabularies = harvester_distribution_config_dict.get(CC.METADATA_VOCABULARIES_DICT, None)
        combined_metadata_vocabularies = harvester_distribution_config_dict.get(CC.COMBINED_METADATA_VOCABULARIES_DICT, None)
        
        distribution_data = self.rdf_store.rdf_store_query.get_customized_node(node_uri = distribution_uri,
                                                                              predicates_to_exclude = [],
                                                                              node_classes_to_exclude = [],
                                                                              predicates_to_include_only_their_type = []
                                                                              )
        # check vocabularies and shacl templates:
        conforms, vocabulary_validation_error_messages, shacl_messages = gather_stage_validation_utils.check_vocabulary_and_shacl_validation(distribution_uri, distribution_data, self.vocabulary_validator, shacl_validator, hvd_shacl_validator, metadata_vocabularies, combined_metadata_vocabularies)
        for message in vocabulary_validation_error_messages or []:
            self._save_gather_error(f'Error in distribution {distribution_uri} of dataset {dataset_uri}. {message}', self.harvest_job)
        for message in shacl_messages or []:
            self._save_gather_error(message, self.harvest_job)
        return conforms, distribution_data
