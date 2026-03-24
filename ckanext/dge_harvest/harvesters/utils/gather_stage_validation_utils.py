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

import logging
import time
import inspect

import ckan.model as model

from rdflib import Graph
from typing import Tuple, List
from ckanext.dge_harvest import helpers as dhh

from ...harvester_config_reader import HarvesterConfigReader
from ...constants import (DCATAPESConfigConstants as CC)

from .shacl_validator import ShaclValidator
from ...utils import check_hvd_entity
from .vocabulary_validator import VocabularyValidator
from ...decorators import log_debug, log_info

log = logging.getLogger(__name__)

def get_owner_organization_from_harvester_job(harvest_job):
    _owner_org = None
    if harvest_job and harvest_job.source and harvest_job.source.id:
        source_catalog = model.Package.get(harvest_job.source.id)
        if source_catalog and source_catalog.owner_org:
            _owner_org_id =  source_catalog.owner_org
    _owner_org = dhh.dge_get_organization(_owner_org_id, False)
    _owner_org_minhap = dhh._get_extra_value(_owner_org.get('extras', []), CC.ORG_PROP_ID_UD_ORGANICA)
    return _owner_org_id, _owner_org_minhap

@log_debug
def get_harvester_config_dict(harvester_config_reader:HarvesterConfigReader, section:str):
    if harvester_config_reader is None or section is None:
        return {}
    harvester_config = {}
    harvester_config[CC.METADATA_VOCABULARIES_DICT] = harvester_config_reader.get_section_property_as_a_list_dict(section, f'{section}{CC.PROP_METADATA_VOCABULARIES}', '', None)
    harvester_config[CC.METADATA_VOCABULARIES_HVD_DICT] = harvester_config_reader.get_section_property_as_a_list_dict(section, f'{section}{CC.PROP_METADATA_VOCABULARIES_HVD}', '', None)
    harvester_config[CC.SHACL_SHAPES] = harvester_config_reader.get_section_property_as_a_list(section, f'{section}{CC.PROP_SHACL_SHAPES}', [])
    harvester_config[CC.SHACL_SHAPES_HVD] = harvester_config_reader.get_section_property_as_a_list(section, f'{section}{CC.PROP_SHACL_SHAPES_HVD}', [])

    # Combined data
    metadata_vocabularies = harvester_config.get(CC.METADATA_VOCABULARIES_DICT, {}) or {}
    hvd_metadata_vocabularies = harvester_config.get(CC.METADATA_VOCABULARIES_HVD_DICT, {})  or {}
    harvester_config[CC.COMBINED_METADATA_VOCABULARIES_DICT] = {k: list(set(metadata_vocabularies.get(k, []) + hvd_metadata_vocabularies.get(k, []))) for k in metadata_vocabularies.keys() | hvd_metadata_vocabularies.keys()}

    shacl_shapes = harvester_config.get(CC.SHACL_SHAPES, None) 
    hvd_shacl_shapes = harvester_config.get(CC.SHACL_SHAPES_HVD, None)
    harvester_config[CC.COMBINED_SHACL_SHAPES] =  list(set((shacl_shapes or []) + (hvd_shacl_shapes or [])))
    return harvester_config

@log_debug
def check_vocabulary_and_shacl_validation(entity_uri, data_graph:Graph, vocabulary_validator: VocabularyValidator, shacl_validator:ShaclValidator, hvd_shacl_validator:ShaclValidator, metadata_vocabularies:dict[str, dict[str]], hvd_metadata_vocabularies:dict[str, dict[str]]) -> Tuple[bool, List[str], List[str]]:
    """
    Checks whether a graph conforms to given vocabularies and/or templates basic and optionally HVD

    :param entity_uri: entity uri of data graph to check 
    :type entity_uri: str

    :param data_graph: data graph to check 
    :type data_graph: Graph

    :param vocabulary_validator: object that makes the vocabulary validation
    :type vocabulary_validator: VocabularyValidator

    :param shacl_validator: object that makes the shacl validation
    :type shacl_validator: ShaclValidator

    :param hvd_shacl_validator: object that makes the shacl validation
    :type hvd_shacl_validator: ShaclValidator

    :param metadata_vocabularies: Dictionary with the configuration of metadata and vocabularies that may have.
    :type metadata_vocabularies: dict[str, List[str]]

    :param hvd_metadata_vocabularies: Dictionary with the configuration of metadata and vocabularies that may have.
    :type hvd_metadata_vocabularies: dict[str, List[str]]

    :returns: Tuple with three params: 
                - conforms: True if data_graph is conforms, False in other case
                - vocabulary_messages: List of messages in vocabulary validation
                - shacl_messages: List of messages in shacl validation
    :rtype: Tuple[bool, List[str], List[str]]
    """
    method_log_prefix = f'[{inspect.currentframe().f_code.co_name}]'
    conforms = True
    vocabulary_validation_error_messages = []
    shacl_messages = []
    if len(data_graph) > 0:
        final_shacl_validator = shacl_validator
        final_metadata_vocabularies = metadata_vocabularies
        if check_hvd_entity(data_graph, entity_uri):
            final_shacl_validator = hvd_shacl_validator
            final_metadata_vocabularies = hvd_metadata_vocabularies
        # check vocabularies:
        vocabulary_conforms, vocabulary_validation_error_messages = check_vocabulary(vocabulary_validator, data_graph, final_metadata_vocabularies)
        # check SHACL templates
        shacl_conforms, shacl_messages = check_shacl_validation(data_graph,final_shacl_validator)
        conforms = vocabulary_conforms and shacl_conforms
        vocabulary_validation_error_messages = vocabulary_validation_error_messages or []
        shacl_messages = shacl_messages or []
    else:
        log.debug(f'{method_log_prefix} Data graph is empty. Nothing to validate')
    return conforms, vocabulary_validation_error_messages, shacl_messages

@log_debug
def check_vocabulary(vocabulary_validator: VocabularyValidator, data_graph:Graph, metadata_vocabularies:dict[str, dict[str]]) -> Tuple[bool, List[str]]:
    """
    Checks whether a graph conforms to given vocabularies.

    :param vocabulary_validator: object that makes the vocabulary validation
    :type vocabulary_validator: VocabularyValidator

    :param data_graph: URI of dataset 
    :type data_graph: str

    :param rdf_store: object with the conection to RDF Store
    :type rdf_store: RDFStore

    :param metadata_vocabularies: Dictionary with the configuration of metadata and vocabularies that may have.
    :type metadata_vocabularies: dict[str, List[str]]

    :returns: Tuple with two params: 
                - conforms: True if data_graph is conforms, False in other case
                - vocabulary_messages: List of messages in vocabulary validation
    :rtype: Tuple(bool, List[str])
    """
    # check vocabularies:
    vocabulary_validation_error_messages = vocabulary_validator.check_vocabularies(data_graph, metadata_vocabularies)
    vocabulary_conforms = False if vocabulary_validation_error_messages and len(vocabulary_validation_error_messages) > 0 else True
    return vocabulary_conforms, vocabulary_validation_error_messages

@log_debug
def check_shacl_validation(data_graph:Graph, shacl_validator:ShaclValidator) -> Tuple[bool, List[str]]:
    """
    Checks whether a graph conforms to given shacl validator.

    :param data_graph: URI of entity to validate
    :type data_graph: str

    :param shacl_validator: object that makes the shacl validation
    :type shacl_validator: ShaclValidator

    :returns: Tuple with three params: 
                - conforms: True if data_graph is conforms, False in other case
                - shacl_messages: List of messages in shacl validation
    :rtype: Tuple(bool, List[str])
    """
    # check SHACL templates
    shacl_conforms, shacl_messages = shacl_validator.check_shacl_validation(data_graph)
    return shacl_conforms, shacl_messages
