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
import inspect
import json

from rdflib import URIRef, Literal
from ckan.plugins.toolkit import config
from ckanext.dcat.exceptions import RDFProfileException
from ckanext.dge_harvest import helpers as dhh
from ..constants import (DCATAPESPrefixConstants as PrefixConstants, 
                        DCATAPESDataserviceConstants as DataserviceConstants, 
                        DCATAPESDatasetConstants as DatasetConstants,
                        DCATAPESDistributionConstants as DistributionConstants, 
                        DCATAPESCatalogConstants as CatalogConstants, 
                        DCATAPESHarvesterConstants as HarvesterConstants, 
                        DCATAPESSerializerConstants as SerializerConstants, 
                        DCATAPESConfigConstants as ConfigConstants,
                        NTIDatasetConstants)
from .base_profile import DGEProfile
from . import _profile_serialize_utils, _profile_utils
from .dcat_ap_es_profile_parse_utils_base import DGEDCATAPESProfileParseUtilsBase
from .base_profile_parse_utils_base import BaseProfileParseUtilsBase
from ..harvester_config_reader import HarvesterConfigReader
from ..constants.dcat_ap_es_constants import (NAMESPACES, DCT, DCAT, DCATAP, FOAF, RDF_NAMESPACE, ADMS, TIME, XSD, RDFS, SCHEMA, PROV, ODRL, SPDX, SKOS_NAMESPACE)
from ..decorators import log_debug, log_info

BASIC_FIELDS_METADATA = [
    ('homepage', FOAF.homepage),
    ('spatial', DCT.spatial),
    ('themeTaxonomy', DCAT.themeTaxonomy),
    ('license', DCT.license),
    ('publisher', DCT.publisher),
    ('rights', DCT.rights)]

log = logging.getLogger(__name__)

class DGEDCATAPESProfile(DGEProfile):
    
    '''
    An RDF profile based on the DCAT-AP-ES for data portals in Spain

    More information and specification:

    https://joinup.ec.europa.eu/asset/dcat_application_profile

    '''
    class MetadataValidationData():
        '''
        Class to store all the keys and objects needed to validate a metadata
        '''
        def __init__(self, field_key, errors_key, warnings_key, metadata_key, data_dict):
            self.field_key = field_key
            self.errors_key = errors_key
            self.warnings_key = warnings_key
            self.metadata_key = metadata_key
            self.data_dict = data_dict or {}
            if self.data_dict[self.errors_key] is None:
                self.data_dict[self.errors_key] = []
            if self.data_dict[self.warnings_key] is None:
                self.data_dict[self.warnings_key] = []

    def __init__(self, graph, dataset_type="dataset", compatibility_mode=False):
        super().__init__(graph = graph, dataset_type=dataset_type, compatibility_mode=compatibility_mode)
        self.default_locale = self._get_ckan_default_locale()
        self.locales_offered = self._get_ckan_locales_offered()
        self.dcat_ap_default_locale =  self._from_iso_6391_to_language_DCAT_AP(self._get_ckan_default_locale())
        self.dcat_ap_offered_locales = self._get_dcat_ap_offered_locales()
        self.parse_utils = None
        self.parse_dataset_error_message = None
        self.parse_dataservice_error_message = None

    def _initialize_parse_utils(self):
        if self.parse_utils == None:
            self.parse_utils = DGEDCATAPESProfileParseUtilsBase(self.g)
        if self.base_parse_utils == None:
            self.base_parse_utils = BaseProfileParseUtilsBase(self.g)

    def _get_dcat_ap_offered_locales(self):
        dcat_ap_offered_locales = []
        for locale in self.locales_offered or []:
            dcat_ap_offered_locales.append(self._from_iso_6391_to_language_DCAT_AP(locale))
        return dcat_ap_offered_locales

    @log_debug
    def parse_catalog(self, catalog_dict, catalog_ref):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        self._initialize_parse_utils()
        key_catalog_errors = CatalogConstants.KEY_CATALOG_ERRORS
        catalog_dict[key_catalog_errors] = []
        metadata = None
        try:
            allowed_publishers = self._get_available_organizations(catalog_dict)
            
            # Catalog uri
            catalog_dict[CatalogConstants.KEY_CATALOG_URI] = self._get_uri_ref(catalog_ref)

            # Title (dct:title) mandatory, multiple
            metadata = DCT.title
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_TITLE_TRANSLATE, self.parse_utils.object_value_multilanguage_literal_dictionary(catalog_ref, metadata))

            # Description (dct:description) mandatory, multiple
            metadata = DCT.description
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_DESCRIPTION, self.parse_utils.object_value_multilanguage_literal_dictionary(catalog_ref, metadata))

            # Publisher (dct:publisher) mandatory, single
            metadata = DCT.publisher
            publisher_uri,  publisher_name, publisher_id, publisher_minhap = self.parse_utils.publisher(catalog_ref, metadata, allowed_publishers)
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_PUBLISHER_ID_MINHAP, publisher_minhap, False)
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_PUBLISHER, publisher_id, False)
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_PUBLISHER_NAME, publisher_name, False)
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_PUBLISHER_URI, publisher_uri, False)

            # Homepage (foaf:homepage) mandatory, single
            metadata = DCT.homepage
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_HOMEPAGE, self.parse_utils.object_uriref_value(catalog_ref, metadata), False)

            # Themes (dcat:themeTaxonomy) mandatory, multiple
            metadata = DCAT.themeTaxonomy
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_THEME_TAXONOMY, self.parse_utils.object_uriref_value_list(catalog_ref, metadata), False)

            # Release date (dct:issued) mandatory, single
            metadata = DCT.issued
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_ISSUED_DATE, self.parse_utils.object_datetime_value(catalog_ref, metadata), False)

            # Update/modification date (dct:modified) mandatory, single
            metadata = DCT.modified
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_MODIFIED_DATE, self.parse_utils.object_datetime_value(catalog_ref, metadata), False)

            # Language (dct:language) mandatory, multiple
            metadata = DCT.language
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_LANGUAGE, self.parse_utils.object_uriref_value_list(catalog_ref, metadata), False)

            # License (dct:license) mandatory, single
            metadata = DCT.license
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_LICENSE, self.parse_utils.object_uriref_value(catalog_ref, metadata), False)

            # Spatial coverage (dct:spatial) recommended, multiple
            metadata = DCT.spatial
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_SPATIAL, self.parse_utils._get_spatial(catalog_ref, metadata), True)

            # Catalog (dct:catalog) optional, multiple
            metadata = DCT.catalog
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_CATALOG, self.parse_utils.object_uriref_value_list(catalog_ref, metadata), False)

            # Author (dct:creator) Optional, multiple
            metadata = DCT.creator
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_CREATOR, self.parse_utils._get_creators(catalog_ref, metadata), False)

            # Includes (dct:hasPart) optional, multiple
            metadata = DCT.hasPart
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_HAS_PART, self.parse_utils.object_uriref_value_list(catalog_ref, metadata), False)

            # Is part of (dct:isPartOf) optional, single
            metadata = DCT.isPartOf
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_IS_PART_OF, self.parse_utils.object_uriref_value(catalog_ref, metadata), False)

            # Rights (dct:rights) optional, single
            metadata = DCT.rights
            self._add_to_dictionary_if_value_not_empty(catalog_dict, CatalogConstants.KEY_CATALOG_RIGHTS, self.parse_utils.object_uriref_value(catalog_ref, metadata), False)

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            if metadata:
                error_msg = HarvesterConstants.VALIDATION_ERROR_MESSAGE.format(catalog_ref, metadata, error_msg)
            else:
                error_msg = HarvesterConstants.VALIDATION_UNEXPECTED_ERROR_MESSAGE.format(catalog_ref, error_msg)
            catalog_dict[key_catalog_errors].append(self._build_error_warning_msg(error_msg, None))
            log.error(f'{method_log_prefix} Exception parsing catalog {catalog_ref}. {error_msg}', exc_info=True)
        return catalog_dict

    @log_debug
    def parse_dataset(self, dataset_dict, dataset_ref):
        self._initialize_parse_utils()
        dataset_dict[DatasetConstants.KEY_ERRORS] = []
        dataset_dict[DatasetConstants.KEY_WARNINGS] = []
        self.parse_dataset_error_message = None
        try:
            self._parse_basic_dataset_data(dataset_dict, dataset_ref)
            if dataset_dict.get(DatasetConstants.CONFORMS_TO_SHACL, True) and not dataset_dict.get(DatasetConstants.KEY_ERRORS):
                self._parse_complete_dataset_data(dataset_dict, dataset_ref)
        except Exception as e:
            if not self.parse_dataset_error_message:
                self.parse_dataservice_error_message = f"{type(e).__name__}: {e}"
            dataset_dict[DatasetConstants.KEY_ERRORS].append(self._build_error_warning_msg(self.parse_dataservice_error_message, None))
        return dataset_dict

    def _parse_basic_dataset_data(self, dataset_dict, dataset_ref):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            allowed_publishers = self._get_available_organizations(dataset_dict)

            # extras
            dataset_dict[DatasetConstants.KEY_EXTRAS] = dataset_dict.get(DatasetConstants.KEY_EXTRAS, [])
            dataset_dict[DatasetConstants.KEY_RESOURCES] = dataset_dict.get(DatasetConstants.KEY_RESOURCES, [])
            dataset_dict[DatasetConstants.KEY_TYPE] = DatasetConstants.KEY_TYPE_DATASET_VALUE

            # Dataset uri
            dataset_dict[DatasetConstants.KEY_URI] = self._get_uri_ref(dataset_ref)

            # Publisher (dct:publisher) mandatory, single
            metadata = DCT.publisher
            publisher_uri,  publisher_name, publisher_id, publisher_minhap = self.parse_utils.publisher(dataset_ref, metadata, allowed_publishers)
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_PUBLISHER_ID_MINHAP, publisher_minhap, False)
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_PUBLISHER, publisher_id, False)
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_PUBLISHER_NAME, publisher_name, False)
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_PUBLISHER_URI, publisher_uri, False)

            # Title (dct:title) mandatory, multiple
            metadata = DCT.title
            title_dict = self.parse_utils.object_value_multilanguage_literal_dictionary(dataset_ref, metadata)
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_TITLE_TRANSLATED, title_dict, False)
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_TITLE,  title_dict.get(self.default_locale, None), False)
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            log.error(f'{method_log_prefix} Exception parsing dataset {dataset_ref}. {error_msg}.', exc_info=True)
            if metadata:
                self.parse_dataset_error_message = HarvesterConstants.VALIDATION_ERROR_MESSAGE.format(dataset_ref, self.metadata, error_msg)
            else:
                self.parse_dataset_error_message = HarvesterConstants.VALIDATION_UNEXPECTED_ERROR_MESSAGE.format(dataset_ref, error_msg)
            raise e

    def _parse_complete_dataset_data(self, dataset_dict, dataset_ref):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            # Language (dct:language) optional, multiple
            metadata = DCT.language
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_LANGUAGE, self.parse_utils.object_uriref_value_list(dataset_ref, metadata), False)

            # Identifier (dct:identifier) optional, multiple
            metadata = DCT.identifier
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_IDENTIFIER, self.parse_utils.object_value_literal_list(dataset_ref, metadata), False)

            # Description (dct:description) mandatory, multiple
            metadata = DCT.description
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_DESCRIPTION, self.parse_utils.object_value_multilanguage_literal_dictionary(dataset_ref, metadata), False)

            # Version (dcat:version) optional, multiple
            metadata = DCAT.version
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_VERSION, self.parse_utils.object_value_literal_value(dataset_ref, metadata), False)

            # Version notes (adms:versionNotes) optional, multiple
            metadata = ADMS.versionNotes
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_VERSION_NOTES, self.parse_utils.object_value_multilanguage_literal_dictionary(dataset_ref, metadata), False)
            
            # Themes (dcat:theme) mandatory, multiple
            metadata = DCAT.theme
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_THEME, self.parse_utils.object_uriref_value_list(dataset_ref, metadata), False)

            # Spatial coverage (dct:spatial) recommended, multiple
            metadata = DCT.spatial
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_SPATIAL, self.parse_utils._get_spatial(dataset_ref, metadata), True)

            # Applicable HVD Legistlation (dcatap:applicableLegislation) mandatory if HVD, multiple
            metadata = DCATAP.applicableLegislation
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_HVD_APPLICABLE_LEGISLATION, self.parse_utils.object_uriref_value_list(dataset_ref, metadata), False)

            # HVD Category (dcatap:hvdCategory) mandatory if HVD, multiple
            metadata = DCATAP.hvdCategory
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_HVD_CATEGORY, self.parse_utils.object_uriref_value_list(dataset_ref, metadata), False)

            # Multilingual tags (dcat:keyword) optional, multiple
            metadata = DCAT.keyword
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_MULTILINGUAL_TAGS, self.parse_utils.object_value_multilanguage_literal_list_dictionary(dataset_ref, metadata), False)

            # Contact Point (dcat:contactPoint) optional, multiple
            metadata = DCAT.contactPoint
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_CONTACT_POINT, self.parse_utils._get_contact_points(dataset_ref, metadata), False)

            # Temporal coverage (dct:temporal) optional, multiple
            metadata = DCT.temporal
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_TEMPORAL_COVERAGE, self.parse_utils._get_temporal(dataset_ref, metadata), False)

            # Another identifier (adms:identifier) optional, multiple
            metadata = ADMS.identifier
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_ANOTHER_IDENTIFIER, self.parse_utils._get_other_identifiers(dataset_ref, metadata), False)

            # Author (dct:creator) optional, multiple
            metadata = DCT.creator
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_CREATOR, self.parse_utils._get_creators(dataset_ref, metadata), False)

            # Documentation (foaf:page) optional, multiple
            metadata = FOAF.page
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_PAGE, self.parse_utils.object_uriref_value_list(dataset_ref, metadata), False)

            # Landing page (dcat:landingPage) optional, multiple
            metadata = DCAT.landingPage
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_LANDING_PAGE, self.parse_utils.object_uriref_value_list(dataset_ref, metadata), False)

            # Conforms to (dct:conformsTo) optional, multiple
            metadata = DCT.conformsTo
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_NORMATIVE, self.parse_utils.object_uriref_value_list(dataset_ref, metadata), False)

            # Issued date (dct:issued) optional, single
            metadata = DCT.issued
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_ISSUED_DATE, self.parse_utils.object_datetime_value(dataset_ref, metadata), False)

            # Modified date (dct:modified) optional, single
            metadata = DCT.modified
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_MODIFIED_DATE, self.parse_utils.object_datetime_value(dataset_ref, metadata), False)

            # Type (dct:type) optional, single
            metadata = DCT.type
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_TYPE, self.parse_utils.object_uriref_value(dataset_ref, metadata), False)

            # Accrual Periodicity (dct:accrualPeriodicity) optional, single
            metadata = DCT.accrualPeriodicity
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_FREQUENCY, self._get_frequency_value(dataset_ref, metadata), True)

            # Has Version (dcat:hasVersion) optional, multiple
            metadata = DCAT.hasVersion
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_HAS_VERSION, self.parse_utils.object_uriref_value_list(dataset_ref, metadata), False)

            # Is version of (dcat:isVersionOf) optional, multiple
            metadata = DCAT.isVersionOf
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_IS_VERSION_OF, self.parse_utils.object_uriref_value_list(dataset_ref, metadata), False)

            # Qualified Relation (dcat:qualifiedRelation) optional, multiple
            metadata = DCAT.qualifiedRelation
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_QUALIFIED_RELATION, self.parse_utils._get_qualified_relations(dataset_ref, metadata), False)

            # Spatial resolution (dcat:spatialResolutionInMeters) optional, single
            metadata = DCAT.spatialResolutionInMeters
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_SPATIAL_RESOLUTION_IN_METERS, self.parse_utils.object_value_literal_value_with_datatype(dataset_ref, metadata, [XSD.decimal, XSD.double, XSD.integer]), False)

            # Temporal resolution (dcat:temporalResolution) optional, single
            metadata = DCAT.temporalResolution
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_TEMPORAL_RESOLUTION, self.parse_utils.object_value_literal_value_with_datatype(dataset_ref, metadata, [XSD.duration]), False)

            # Is referenced by (dct:isReferencedBy) optional, multiple
            metadata = DCT.isReferencedBy
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_IS_REFERENCED_BY, self.parse_utils.object_uriref_value_list(dataset_ref, metadata), False)

            # Provenance (dct:provenance) optional, multiple
            metadata = DCT.provenance
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_PROVENANCE, self.parse_utils.object_uriref_value_list(dataset_ref, metadata), False)

            # Related resource (dct:relation) optional, multiple
            metadata = DCT.relation
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_RELATION, self.parse_utils.object_uriref_value_list(dataset_ref, metadata), False)

            # Qualified attribution (prov:qualifiedAttribution) optional, multiple
            metadata = PROV.qualifiedAttribution
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_QUALIFIED_ATTRIBUTION, self.parse_utils._get_qualified_attributions(dataset_ref, metadata), False)

            # Was generated by (prov:wasGeneratedBy) optional, multiple
            metadata = PROV.wasGeneratedBy
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_WAS_GENERATED_BY, self.parse_utils.object_uriref_value_list(dataset_ref, metadata), False)

            # Source (dct:source) optional, multiple
            metadata = DCT.source
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_SOURCE, self.parse_utils.object_uriref_value_list(dataset_ref, metadata), False)

            # Access Rights (dct:accessRights) optional, single
            metadata = DCT.accessRights
            self._add_to_dictionary_if_value_not_empty(dataset_dict, DatasetConstants.KEY_DATASET_ACCESS_RIGHTS, self.parse_utils.object_uriref_value(dataset_ref, metadata), False)

            # Sample (adms:sample) optional, multiple
            metadata = ADMS.sample
            samples = self.parse_utils._get_samples(dataset_ref, metadata)

            # Resources
            for distribution_ref in self._distributions(dataset_ref) or []:
                resource_dict = self.parse_distribution(dataset_dict, dataset_ref, distribution_ref, False)
                dataset_dict['resources'].append(resource_dict)

            for sample_ref in samples:
                sample_dict = self.parse_distribution(dataset_dict, dataset_ref, sample_ref, True)
                dataset_dict['resources'].append(sample_dict)

        except Exception as e:
            if not self.parse_dataset_error_message:
                error_msg = f"{type(e).__name__}: {str(e)}"
                log.error(f'{method_log_prefix} Exception parsing dataset {dataset_ref}. {error_msg}.', exc_info=True)
                if metadata:
                    self.parse_dataset_error_message = HarvesterConstants.VALIDATION_ERROR_MESSAGE.format(dataset_ref, self.metadata, error_msg)
                else:
                    self.parse_dataset_error_message = HarvesterConstants.VALIDATION_UNEXPECTED_ERROR_MESSAGE.format(dataset_ref, error_msg)
            raise e

    @log_debug
    def parse_distribution(self, dataset_dict, dataset_ref, distribution_ref, is_sample):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:

            log.info(f'{method_log_prefix} distribution_ref = {distribution_ref}')
            resource_dict = {}

            resource_dict[DistributionConstants.KEY_DISTRIBUTION_SOURCE_URI] = distribution_ref

            # is sample or distribution
            resource_dict[DistributionConstants.KEY_DISTRIBUTION_IS_SAMPLE] = is_sample

            # access URL (dcat:accessURL) mandatory, multiple
            metadata = DCAT.accessURL
            access_urls = self.parse_utils.object_uriref_value_list(distribution_ref, metadata)
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_ACCESS_URL, access_urls, False)
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_AN_ACCESS_URL, access_urls[0] if access_urls and len(access_urls) > 0 else None, False)

            # Applicable HVD Legislation (dcatap:applicableLegislation) mandatory if HVD, multiple
            metadata = DCATAP.applicableLegislation
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_HVD_APPLICABLE_LEGISLATION, self.parse_utils.object_uriref_value_list(distribution_ref, metadata), False)
            
            # Description (dct:description) mandatory, multiple
            metadata = DCT.description
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_DESCRIPTION, self.parse_utils.object_value_multilanguage_literal_dictionary(distribution_ref, metadata), False)

            # Availability (dcatap:availability) optional, single
            metadata = DCATAP.availability
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_AVAILABILITY, self.parse_utils.object_uriref_value(distribution_ref, metadata), False)

            # MIME type format (dcat:mediaType) optional, single
            metadata = DCAT.mediaType
            media_type = self.parse_utils.object_uriref_value(distribution_ref, metadata)
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_MEDIA_TYPE, media_type, False)

            # Format (dct.format) optional, single
            metadata = DCT['format']
            dct_format = self.parse_utils._distribution_format(distribution_ref, metadata)
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_RESOURCE_FORMAT, dct_format, False)

            # Format (resource.format)
            distribution_format = ''
            if dct_format:
                if dct_format.startswith(PrefixConstants.FORMAT_PREFIX_EDP):
                    distribution_format = self.parse_utils._get_format_str_from_format_uri(dct_format, PrefixConstants.FORMAT_PREFIX_EDP)
                    distribution_format = self.parse_utils._parse_format_label_to_format_value(distribution_format)
                else:
                    distribution_format = dct_format
            elif media_type:
                distribution_format = self.parse_utils._get_format_str_from_format_uri(media_type, PrefixConstants.FORMAT_PREFIX_EDP_IANA)
            resource_dict[DistributionConstants.KEY_DISTRIBUTION_FORMAT] = distribution_format
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_FORMAT, distribution_format, False)

            # Compress format (dcat:compressFormat) optional, single
            metadata = DCAT.compressFormat
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_COMPRESS_FORMAT, self.parse_utils.object_uriref_value(distribution_ref, metadata), False)

            # Package format (dcat:packageFormat) optional, single
            metadata = DCAT.packageFormat
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_PACKAGE_FORMAT, self.parse_utils.object_uriref_value(distribution_ref, metadata), False)

            # License (dct:license) optional, single
            metadata = DCT.license
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_LICENSE, self.parse_utils.object_uriref_value(distribution_ref, metadata), False)

            # Access Service (dcat:accessService) optional, multiple
            metadata = DCAT.accessService
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_ACCESS_SERVICE, self.parse_utils.object_uriref_value_list(distribution_ref, metadata), False)

            # Title (dct:title) optional, multiple
            metadata = DCT.title
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_TITLE_TRANSLATED, self.parse_utils.object_value_multilanguage_literal_dictionary(distribution_ref, metadata), False)

            # Documentation (foaf:page) optional, multiple
            metadata = FOAF.page
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_PAGE, self.parse_utils.object_uriref_value_list(distribution_ref, metadata), False)

            # Download URL (dcat:downloadURL) optional, multiple
            metadata = DCAT.downloadURL
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_DOWNLOAD_URL, self.parse_utils.object_uriref_value_list(distribution_ref, metadata), False)

            # Schema (dct:conformsTo) optional, multiple
            metadata = DCT.conformsTo
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_CONFORMS_TO, self.parse_utils.object_uriref_value_list(distribution_ref, metadata), False)

            # Issued date (dct:issued) optional, single
            metadata = DCT.issued
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_ISSUED_DATE, self.parse_utils.object_datetime_value(distribution_ref, metadata), False)

            # Modified date (dct:modified) optional, single
            metadata = DCT.modified
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_MODIFIED_DATE, self.parse_utils.object_datetime_value(distribution_ref, metadata), False)

            # Status (adms:status) optional, single
            metadata = ADMS.status
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_STATUS, self.parse_utils.object_uriref_value(distribution_ref, metadata), False)

            # Language (dct:language) optional, multiple
            metadata = DCT.language
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_LANGUAGE, self.parse_utils.object_uriref_value_list(distribution_ref, metadata), False)

            # Byte size (dcat:byteSize) optional, single
            metadata = DCAT.byteSize
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_BYTE_SIZE, self.parse_utils.object_value_literal_value(distribution_ref, metadata), False)

            # Spatial resolution (dcat:spatialResolutionInMeters) optional, single
            metadata = DCAT.spatialResolutionInMeters
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_SPATIAL_RESOLUTION_IN_METERS, self.parse_utils.object_value_literal_value_with_datatype(distribution_ref, metadata, [XSD.decimal, XSD.double, XSD.integer]), False)

            # Temporal resolution (dcat:temporalResolution) optional, single
            metadata = DCAT.temporalResolution
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_TEMPORAL_RESOLUTION, self.parse_utils.object_value_literal_value_with_datatype(distribution_ref, metadata, [XSD.duration]), False)

            # Checksum (spdx:checksum) optional, single
            metadata = SPDX.checksum
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_CHECKSUM, self.parse_utils._get_checksum(distribution_ref, metadata), True)

            # ODRL Policy (odrl:hasPolicy) optional, single
            metadata = ODRL.hasPolicy
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_HAS_POLICY, self.parse_utils.object_uriref_value(distribution_ref, metadata), False)

            # Rights (dct:rights) optional, single
            metadata = DCT.rights
            self._add_to_dictionary_if_value_not_empty(resource_dict, DistributionConstants.KEY_DISTRIBUTION_RIGHTS, self.parse_utils.object_uriref_value(distribution_ref, metadata), False)
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            log.error(f'{method_log_prefix} Exception parsing distribution {distribution_ref} of dataset {dataset_ref}. {error_msg}.', exc_info=True)
            if metadata:
                self.parse_dataset_error_message = HarvesterConstants.VALIDATION_SUBNODE_ERROR_MESSAGE.format(distribution_ref, dataset_ref, self.metadata, error_msg)
            else:
                self.parse_dataset_error_message = HarvesterConstants.VALIDATION_SUBNODE_UNEXPECTED_ERROR_MESSAGE.format(distribution_ref, dataset_ref, error_msg)
            raise e

        return resource_dict

    @log_debug
    def parse_dataservice(self, dataservice_dict, dataservice_ref):
        self._initialize_parse_utils()
        key_dataservice_errors = DataserviceConstants.KEY_ERRORS
        key_dataservice_warnings = DataserviceConstants.KEY_WARNINGS
        dataservice_dict[key_dataservice_errors] = []
        dataservice_dict[key_dataservice_warnings] = []
        self.parse_dataservice_error_message = None
        try:
            self._parse_basic_dataservice_data(dataservice_dict, dataservice_ref)
            if dataservice_dict.get(DatasetConstants.CONFORMS_TO_SHACL, True):
                self._parse_complete_dataservice_data(dataservice_dict, dataservice_ref)
        except Exception as e:
            if not self.parse_dataservice_error_message:
                self.parse_dataservice_error_message = f"{type(e).__name__}: {e}"
            dataservice_dict[key_dataservice_errors].append(self._build_error_warning_msg(self.parse_dataservice_error_message, None))
        return dataservice_dict

    @log_debug
    def _parse_basic_dataservice_data(self, dataservice_dict, dataservice_ref):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            allowed_publishers = self._get_available_organizations(dataservice_dict)

            # Extras
            dataservice_dict[DataserviceConstants.KEY_EXTRAS] = dataservice_dict.get(DataserviceConstants.KEY_EXTRAS, [])
            dataservice_dict[DataserviceConstants.KEY_TYPE] = 'dataservice'
            dataservice_dict[DataserviceConstants.KEY_RESOURCES] = []

            # Dataservice uri
            dataservice_dict[DataserviceConstants.KEY_URI] = self._get_uri_ref(dataservice_ref)

            # Publisher (dct:publisher) mandatory, single
            metadata = DCT.publisher
            publisher_uri,  publisher_name, publisher_id, publisher_minhap = self.parse_utils.publisher(dataservice_ref, metadata, allowed_publishers)
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_PUBLISHER_ID_MINHAP, publisher_minhap, False)
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_PUBLISHER, publisher_id, False)
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_PUBLISHER_NAME, publisher_name, False)
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_PUBLISHER_URI, publisher_uri, False)

            # Title (dct:title) mandatory, multiple
            metadata = DCT.title
            title_dict = self.parse_utils.object_value_multilanguage_literal_dictionary(dataservice_ref, metadata)
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_TITLE_TRANSLATED, title_dict, False)
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_TITLE,  title_dict.get(self.default_locale, None), False)

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            log.error(f'{method_log_prefix} Exception parsing dataservice {dataservice_ref}. {error_msg}.', exc_info=True)
            if metadata:
                self.self.parse_dataservice_error_message = HarvesterConstants.VALIDATION_ERROR_MESSAGE.format(dataservice_ref, self.metadata, error_msg)
            else:
                self.self.parse_dataservice_error_message = HarvesterConstants.VALIDATION_UNEXPECTED_ERROR_MESSAGE.format(dataservice_ref, error_msg)
            raise e

    @log_debug
    def _parse_complete_dataservice_data(self, dataservice_dict, dataservice_ref):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            # Applicable HVD Legistlation (dcatap:applicableLegislation) mandatory if HVD, multiple
            metadata = DCATAP.applicableLegislation
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_HVD_APPLICABLE_LEGISLATION, self.parse_utils.object_uriref_value_list(dataservice_ref, metadata), False)

            # HVD Category (dcatap:hvdCategory) mandatory if HVD, multiple
            metadata = DCATAP.hvdCategory
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_HVD_CATEGORY, self.parse_utils.object_uriref_value_list(dataservice_ref, metadata), False)

            # Contact Point (dcat:contactPoint) optional, multiple
            metadata = DCAT.contactPoint
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_CONTACT_POINT, self.parse_utils._get_contact_points(dataservice_ref, metadata), False)

            # Documentation (foaf:page) optional, multiple
            metadata = FOAF.page
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_PAGE, self.parse_utils.object_uriref_value_list(dataservice_ref, metadata), False)

            # Themes (dcat:theme) mandatory, multiple
            metadata = DCAT.theme
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_THEME, self.parse_utils.object_uriref_value_list(dataservice_ref, metadata), False)

            # Access URL (dcat:endpointURL) mandatory, multiple
            metadata = DCAT.endpointURL
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_ENDPOINT_URL, self.parse_utils.object_uriref_value_list(dataservice_ref, metadata), False)

            # Endpoint description (dcat:endpointURL) optative, multiple (recommended)metadata = DCAT.endpointURL
            metadata = DCAT.endpointDescription
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_ENDPOINT_DESCRIPTION, self.parse_utils.object_uriref_value_list(dataservice_ref, metadata), False)

            # Serves dataset (dcat:servesDatsaset) optional, multiple (recommended) 
            metadata = DCAT.servesDataset
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_SERVES_DATASET, self.parse_utils.object_uriref_value_list(dataservice_ref, metadata), False)

            # Description (dct:description) optional, multiple   
            metadata = DCT.description
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_DESCRIPTION, self.parse_utils.object_value_multilanguage_literal_dictionary(dataservice_ref, metadata), False)

            # Access Rights (dct:accessRights) optional, single
            metadata = DCT.accessRights
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_ACCESS_RIGHTS, self.parse_utils.object_uriref_value(dataservice_ref, metadata), False)

            # License (dct:license) optional, single
            metadata = DCT.license
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_LICENSE, self.parse_utils.object_uriref_value(dataservice_ref, metadata), False)

            # Multilingual tags (dcat:keyword) optional, multiple
            metadata = DCAT.keyword
            self._add_to_dictionary_if_value_not_empty(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_MULTILINGUAL_TAGS, self.parse_utils.object_value_multilanguage_literal_list_dictionary(dataservice_ref, metadata), False)
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            log.error(f'{method_log_prefix} Exception parsing dataservice {dataservice_ref}. {error_msg}.', exc_info=True)
            if metadata:
                self.self.parse_dataservice_error_message = HarvesterConstants.VALIDATION_ERROR_MESSAGE.format(dataservice_ref, self.metadata, error_msg)
            else:
                self.self.parse_dataservice_error_message = HarvesterConstants.VALIDATION_UNEXPECTED_ERROR_MESSAGE.format(dataservice_ref, error_msg)
            raise e

    @log_debug
    def graph_from_catalog(self, catalog_dict, catalog_ref):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            # check if is an export to european data portal
            _is_european_data_portal_export = _profile_utils._is_european_export(catalog_dict)
            # get config_reader
            _config_reader = self._get_config_reader(catalog_dict)
            # properties prefix
            _properties_prefix = catalog_dict.get(SerializerConstants.CATALOG_EXPORT_PROPERTIES_PREFIX)
            # organizations
            allowed_publishers = self._get_available_organizations(catalog_dict)

            g = self.g
            
            for prefix, namespace in NAMESPACES.items():
                g.bind(prefix, namespace)

            g.add((catalog_ref, RDF_NAMESPACE.type, DCAT.Catalog))

            # Languages
            _profile_serialize_utils.add_resource_list_triple(g, catalog_ref, DCT.language, self.dcat_ap_offered_locales, encode_url=_is_european_data_portal_export)
            
            # Translate fields
            default_title = _profile_serialize_utils.get_str_value_of_property_from_config_reader(_config_reader, _properties_prefix, 'title', None)
            default_description = _profile_serialize_utils.get_str_value_of_property_from_config_reader(_config_reader, _properties_prefix, 'description', None)
            items = [
                ('title', DCT.title, default_title, self.default_locale),
                ('description', DCT.description, default_description, self.default_locale)
            ]
            if (self.locales_offered):
                metadata_info = items
                items = _profile_serialize_utils.set_translate_fields_items([], metadata_info, self.locales_offered, _config_reader, ConfigConstants.SECTION_RDF_EXPORT, _properties_prefix)
            _profile_serialize_utils.set_translate_fields_metadata(items, catalog_dict, catalog_ref, g)

            # Basic fields (homepage, spatial, themeTaxonomy, publisher and rights)
            items = []
            for key, predicate in BASIC_FIELDS_METADATA:
                items.append((key, 
                              predicate, 
                              _profile_serialize_utils.get_str_value_of_property_from_config_reader(_config_reader, _properties_prefix, key, None)))
            _profile_serialize_utils.set_multiple_basic_fields_metadata(items, catalog_dict, catalog_ref, g)

            # check if is an export to european data portal
            if _is_european_data_portal_export:
                # Add european theme taxonomy
                european_theme_taxonomy = catalog_dict.get(SerializerConstants.EUROPEAN_THEME_TAXONOMY, None)
                if european_theme_taxonomy:
                    g.add((catalog_ref, DCAT.themeTaxonomy, URIRef(european_theme_taxonomy)))

            # publisher (extended info)
            publisher = _profile_serialize_utils.get_str_value_of_property_from_config_reader(_config_reader, _properties_prefix, 'publisher', None)
            if publisher:
                g.add((catalog_ref, DCT.publisher, URIRef(publisher)))
                _profile_serialize_utils.set_publisher_metadata(publisher, allowed_publishers, g, self.default_locale)

            # Creator (extended info)
            creators = _profile_serialize_utils.get_list_of_str_values_of_property_from_config_reader(_config_reader, _properties_prefix, 'creator', None)
            if creators:
                _profile_serialize_utils._set_creators_metadata(creators, self.default_locale, g, catalog_ref, allowed_publishers)

            # Dates
            modified = self._last_catalog_modification()
            if modified:
                self._add_date_triple(catalog_ref, DCT.modified, modified)

            # Issued
            issued = _profile_serialize_utils.get_str_value_of_property_from_config_reader(_config_reader, _properties_prefix, 'issued', None)
            if issued:
                self._add_date_triple(catalog_ref, DCT.issued, issued)
        except Exception as e:
            log.error(f'{method_log_prefix} [catalog_ref: {catalog_ref}.Unexpected Error {type(e).__name__}: {e}', exc_info=True)
        #log.debug(f'{method_log_prefix} Graph =\n {g.serialize(format="ttl")}')

    @log_debug
    def graph_from_dataset(self, dataset_dict, dataset_ref):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            g = self.g
            _is_european_export = _profile_utils._is_european_export(dataset_dict)
            _is_nti_dataset = _profile_utils._is_nti_dataset(dataset_dict)
            # get config_reader
            _config_reader = self._get_config_reader(dataset_dict)
            # properties prefix
            _properties_prefix = dataset_dict.get(SerializerConstants.CATALOG_EXPORT_PROPERTIES_PREFIX)
            # organizations
            allowed_publishers = self._get_available_organizations(dataset_dict)

            for prefix, namespace in NAMESPACES.items():
                g.bind(prefix, namespace)

            g.add((dataset_ref, RDF_NAMESPACE.type, DCAT.Dataset))
            
            #CatalogRecord
            conforms_to_uri = config.get('ckanext.dge_harvest.dcat_ap_es_1_0_0.conforms_to.uri', None)
            _profile_serialize_utils._add_catalog_record(dataset_ref, dataset_dict, conforms_to_uri, g)

            # Title
            self._add_translated_triple_field_from_dict(dataset_dict, dataset_ref, DCT.title, DatasetConstants.KEY_DATASET_TITLE_TRANSLATED, None)

            # Description
            self._add_translated_triple_field_from_dict(dataset_dict, dataset_ref, DCT.description, DatasetConstants.KEY_DATASET_DESCRIPTION, None)

            # publisher (extended info)
            publisher = self._get_value_from_dict(dataset_dict, DatasetConstants.KEY_PUBLISHER_URI)
            if publisher:
                g.add((dataset_ref, DCT.publisher, URIRef(publisher)))
                _profile_serialize_utils.set_publisher_metadata(publisher, allowed_publishers, g, self.default_locale)

            # Theme
            themes = self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_THEME)
            _profile_serialize_utils.add_resource_list_triple(g, dataset_ref, DCAT.theme, themes, encode_url=_is_european_export)
            # check if is an export to european data portal
            if _is_european_export and not _profile_utils._has_european_data_themes(themes):
                # Add european theme taxonomy
                self._add_european_theme_tanonomies(dataset_ref, dataset_dict, themes, g)

            # Applicable Legislation
            _profile_serialize_utils.add_resource_list_triple(g, dataset_ref, DCATAP.applicableLegislation, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_HVD_APPLICABLE_LEGISLATION), encode_url=_is_european_export)

            # HVD Catagory
            _profile_serialize_utils.add_resource_list_triple(g, dataset_ref, DCATAP.hvdCategory, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_HVD_CATEGORY), encode_url=_is_european_export)

            # Tags / Keywords
            self._add_translated_list_triple_field_from_dict(dataset_dict, dataset_ref, DCAT.keyword, DatasetConstants.KEY_DATASET_MULTILINGUAL_TAGS, None)

            # Contact Point
            _profile_serialize_utils.add_vcard_kinds(g, dataset_ref, DCAT.contactPoint, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_CONTACT_POINT), encode_url=_is_european_export)

            # temporal resolution
            _profile_serialize_utils.add_temporal_resolution(self, g, dataset_ref, self._get_dataset_value(dataset_dict, DatasetConstants.KEY_DATASET_TEMPORAL_COVERAGE), _is_nti_dataset, encode_url=_is_european_export)

            # geographical coverage
            _profile_serialize_utils.add_geographical_coverage(g, dataset_ref, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_SPATIAL), encode_url=_is_european_export)

            # Identifier
            for identifier in self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_IDENTIFIER) or []:
                g.add((dataset_ref, DCT.identifier, Literal(str(identifier))))

            # Other Identifier
            identifier_index = 1
            for identifier in self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_ANOTHER_IDENTIFIER) or []:
                identifier_ref = URIRef(f'{str(dataset_ref)}/adms_identifier/{identifier_index}')
                g.add((dataset_ref, ADMS.identifier, identifier_ref))
                g.add((identifier_ref, RDF_NAMESPACE.type, ADMS.Identifier))
                g.add((identifier_ref, SKOS_NAMESPACE.notation, Literal(str(identifier))))

            # Author
            _profile_serialize_utils.add_creators(g, dataset_ref, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_CREATOR), encode_url=_is_european_export)

            # Documentation
            _profile_serialize_utils.add_resource_list_triple(g, dataset_ref, FOAF.page, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_PAGE), encode_url=_is_european_export)            

            # Web site
            _profile_serialize_utils.add_resource_list_triple(g, dataset_ref, DCAT.landingPage, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_PAGE), encode_url=_is_european_export)

            # conforms to
            _profile_serialize_utils.add_resource_list_triple(g, dataset_ref, DCT.conformsTo, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_NORMATIVE), encode_url=_is_european_export)

            # Issued and modified date
            if _is_nti_dataset:
                self._add_nti_date_triple(dataset_ref, DCT.issued, self._get_value_from_dict(dataset_dict, DatasetConstants.KEY_DATASET_ISSUED_DATE))
                self._add_nti_date_triple(dataset_ref, DCT.modified,self._get_value_from_dict(dataset_dict, DatasetConstants.KEY_DATASET_MODIFIED_DATE))
            else:
                self._add_date_triple(dataset_ref, DCT.issued, self._get_value_from_dict(dataset_dict, DatasetConstants.KEY_DATASET_ISSUED_DATE), Literal)
                self._add_date_triple(dataset_ref, DCT.modified,self._get_value_from_dict(dataset_dict, DatasetConstants.KEY_DATASET_MODIFIED_DATE), Literal)

            # type
            _profile_serialize_utils.add_resource_list_triple(g, dataset_ref, DCT.type, [self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_TYPE)], encode_url=_is_european_export)

            # languages
            _profile_serialize_utils.add_resource_list_triple(g, dataset_ref, DCT.language, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_LANGUAGE), encode_url=_is_european_export)

            # accrual periodicity
            _profile_serialize_utils.add_accrual_periodicity(g, dataset_ref, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_FREQUENCY))

            # version
            _profile_serialize_utils._add_literal(g, dataset_ref, DCT.version, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_VERSION), None)

            # version notes
            self._add_translated_triple_field_from_dict(dataset_dict, dataset_ref, DCT.versionNotes, DatasetConstants.KEY_DATASET_VERSION_NOTES, None)

            # has Version
            _profile_serialize_utils.add_resource_list_triple(g, dataset_ref, DCAT.hasVersion, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_HAS_VERSION), encode_url=_is_european_export)

            # is version of
            _profile_serialize_utils.add_resource_list_triple(g, dataset_ref, DCAT.isVersionOf, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_IS_VERSION_OF), encode_url=_is_european_export)

            # qualified relation
            _profile_serialize_utils.add_qualified_relations(g, dataset_ref, DCAT.qualifiedRelation, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_QUALIFIED_RELATION), encode_url=_is_european_export)

            # spatial resolution
            _profile_serialize_utils._add_literal(g, dataset_ref, DCAT.spatialResolutionInMeters, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_SPATIAL_RESOLUTION_IN_METERS), None)

            # temporal resolution
            _profile_serialize_utils._add_literal(g, dataset_ref, DCT.temporalResolution, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_TEMPORAL_RESOLUTION), XSD.Duration)

            # referenced by
            _profile_serialize_utils.add_resource_list_triple(g, dataset_ref, DCT.isReferencedBy, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_IS_REFERENCED_BY), encode_url=_is_european_export)

            # provenance
            _profile_serialize_utils.add_resource_list_triple(g, dataset_ref, DCT.provenance, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_PROVENANCE), encode_url=_is_european_export)

            # related resource
            _profile_serialize_utils.add_resource_list_triple(g, dataset_ref, DCT.relation, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_RELATION), encode_url=_is_european_export)

            # qualified attribution
            _profile_serialize_utils.add_qualified_attributions(g, dataset_ref, DCAT.qualifiedAttribution, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_QUALIFIED_ATTRIBUTION), encode_url=_is_european_export)

            # generated by
            _profile_serialize_utils.add_resource_list_triple(g, dataset_ref, PROV.wasGeneratedBy, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_WAS_GENERATED_BY), encode_url=_is_european_export)

            # source
            _profile_serialize_utils.add_resource_list_triple(g, dataset_ref, DCT.source, self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_SOURCE), encode_url=_is_european_export)

            # access rights
            _profile_serialize_utils.add_resource_list_triple(g, dataset_ref, DCT.accessRights, [self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_ACCESS_RIGHTS)], encode_url=_is_european_export)

            if _is_nti_dataset:
                # Valid date
                self._add_nti_date_triple(dataset_ref, DCT.valid,self._get_value_from_dict(dataset_dict, NTIDatasetConstants.KEY_DATASET_VALID))
                
                # referenced resources
                _profile_serialize_utils.add_resource_list_triple(g, dataset_ref, DCT.references, self._get_dict_value(dataset_dict, NTIDatasetConstants.KEY_DATASET_REFERENCE), encode_url=_is_european_export)

            # Distributions and Samples
            for resource_dict in dataset_dict.get('resources', []):
                uri_resource = f'{dataset_ref}/resource/{resource_dict["id"]}'
                self.graph_from_distribution(g, dataset_dict, dataset_ref, resource_dict, uri_resource, _is_european_export)

            # served_by_dataservice:
            dataservices = self._get_dict_value(dataset_dict, DatasetConstants.KEY_DATASET_SERVED_BY_DATASERVICE)
            for dataservice in dataservices or []:
                g.add((URIRef(dataservice), DCAT.servesDataset, dataset_ref))

        except Exception as e:
            log.error(f'{method_log_prefix} [dataset_ref: {dataset_ref}.Unexpected Error {type(e).__name__}: {e}', exc_info=True)

    @log_debug
    def graph_from_distribution(self, g, dataset_dict, dataset_ref, resource_dict, resource_ref, _is_european_export):
        _is_sample = resource_dict.get(DistributionConstants.KEY_DISTRIBUTION_IS_SAMPLE, False)
        _is_nti_dataset = _profile_utils._is_nti_dataset(dataset_dict)
        distribution = URIRef(resource_ref)
        g.add((distribution, RDF_NAMESPACE.type, DCAT.Distribution))
        if _is_sample:
            g.add((dataset_ref, ADMS.sample, distribution))
        else:
            g.add((dataset_ref, DCAT.distribution, distribution))
        
        # access_url
        _profile_serialize_utils.add_resource_list_triple(g, distribution, DCAT.accessURL, self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_ACCESS_URL), encode_url=_is_european_export)

         # Applicable Legislation
        _profile_serialize_utils.add_resource_list_triple(g, distribution, DCATAP.applicableLegislation, self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_HVD_APPLICABLE_LEGISLATION), encode_url=_is_european_export)

        # Description
        self._add_translated_triple_field_from_dict(resource_dict, distribution, DCT.description, DistributionConstants.KEY_DISTRIBUTION_DESCRIPTION, None)
        
        # Availability
        _profile_serialize_utils.add_resource_list_triple(g, distribution, DCATAP.availability, self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_AVAILABILITY), encode_url=_is_european_export)

        # format
        _profile_serialize_utils.add_distribution_format(g, distribution, resource_ref, resource_dict, dataset_dict)

        # resource_license
        _profile_serialize_utils.add_resource_list_triple(g, distribution, DCT.license, self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_LICENSE), encode_url=_is_european_export)

        # access service
        _profile_serialize_utils.add_resource_list_triple(g, distribution, DCAT.accessService, self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_ACCESS_SERVICE), encode_url=_is_european_export)

        # name_translated
        self._add_translated_triple_field_from_dict(resource_dict, distribution, DCT.title, DistributionConstants.KEY_DISTRIBUTION_TITLE_TRANSLATED, None)

        # Documentation
        _profile_serialize_utils.add_resource_list_triple(g, distribution, FOAF.page, self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_PAGE), encode_url=_is_european_export) 

        # MediaType
        _profile_serialize_utils.add_resource_list_triple(g, distribution, DCAT.mediaType, [self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_MEDIA_TYPE)], encode_url=_is_european_export) 

        # Download URL
        _profile_serialize_utils.add_resource_list_triple(g, distribution, DCAT.downloadURL, self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_DOWNLOAD_URL), encode_url=_is_european_export) 

        # Schema
        _profile_serialize_utils.add_resource_list_triple(g, distribution, DCT.conformsTo, self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_CONFORMS_TO), encode_url=_is_european_export) 

        # Issued and modified date
        self._add_date_triple(distribution, DCT.issued, self._get_value_from_dict(dataset_dict, DistributionConstants.KEY_DISTRIBUTION_ISSUED_DATE), Literal)
        self._add_date_triple(distribution, DCT.modified,self._get_value_from_dict(dataset_dict, DistributionConstants.KEY_DISTRIBUTION_MODIFIED_DATE), Literal)

        # Status
        _profile_serialize_utils.add_resource_list_triple(g, distribution, ADMS.status, [self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_STATUS)], encode_url=_is_european_export) 

        # languages
        _profile_serialize_utils.add_resource_list_triple(g, distribution, DCT.language, self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_LANGUAGE), encode_url=_is_european_export)

        # compress format
        _profile_serialize_utils.add_resource_list_triple(g, distribution, DCAT.compressFormat, [self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_COMPRESS_FORMAT)], encode_url=_is_european_export) 

        # package format
        _profile_serialize_utils.add_resource_list_triple(g, distribution, DCAT.packageFormat, [self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_PACKAGE_FORMAT)], encode_url=_is_european_export) 

        # byte_size
        if resource_dict.get(NTIDatasetConstants.KEY_DATASET_RESOURCE_BYTE_SIZE):
            try:
                g.add((distribution, DCAT.byteSize,
                        Literal(int(float(resource_dict[NTIDatasetConstants.KEY_DATASET_RESOURCE_BYTE_SIZE])),
                                datatype=XSD.decimal)))
            except (ValueError, TypeError):
                g.add((distribution, DCAT.byteSize,
                        Literal(resource_dict[NTIDatasetConstants.KEY_DATASET_RESOURCE_BYTE_SIZE])))

        # spatial resolution
        _profile_serialize_utils._add_literal(g, distribution, DCAT.spatialResolutionInMeters, self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_SPATIAL_RESOLUTION_IN_METERS))

        # temporal resolution
        _profile_serialize_utils._add_literal(g, distribution, DCT.temporalResolution, self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_TEMPORAL_RESOLUTION), XSD.Duration)

        # checksum
        _profile_serialize_utils.add_checksum(g, dataset_ref, SPDX.checksum, self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_CHECKSUM), encode_url=_is_european_export)

        # has policy (odlr)
        _profile_serialize_utils.add_resource_list_triple(g, distribution, ODRL.hasPolicy, [self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_HAS_POLICY)], encode_url=_is_european_export)

        # access rights
        _profile_serialize_utils.add_resource_list_triple(g, distribution, DCT.rights, [self._get_dict_value(resource_dict, DistributionConstants.KEY_DISTRIBUTION_RIGHTS)], encode_url=_is_european_export)

        if _is_nti_dataset:
            # identifier
            if resource_dict.get(NTIDatasetConstants.KEY_DATASET_RESOURCE_IDENTIFIER):
                g.add((distribution, DCT.identifier, Literal(str(resource_dict[NTIDatasetConstants.KEY_DATASET_RESOURCE_IDENTIFIER]), datatype=XSD.anyURI)))

            # resource_relation
            if resource_dict.get(NTIDatasetConstants.KEY_DATASET_RESOURCE_RELATION):
                _profile_serialize_utils.add_resource_list_triple(g, distribution, DCT.relation, resource_dict.get(NTIDatasetConstants.KEY_DATASET_RESOURCE_RELATION), encode_url=_is_european_export)

    def graph_from_dataservice(self, dataservice_dict, dataservice_ref):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            _is_european_export = _profile_utils._is_european_export(dataservice_dict)
            allowed_publishers = self._get_available_organizations(dataservice_dict)
            # get config_reader
            _config_reader = self._get_config_reader(dataservice_dict)
            g = self.g
            for prefix, namespace in NAMESPACES.items():
                g.bind(prefix, namespace)

            g.add((dataservice_ref, RDF_NAMESPACE.type, DCAT.DataService))
            #CatalogRecord
            conforms_to_uri = config.get('ckanext.dge_harvest.dcat_ap_es_1_0_0.conforms_to.uri', None)
            _profile_serialize_utils._add_catalog_record(dataservice_ref, dataservice_dict, conforms_to_uri, g)

            # Title
            self._add_translated_triple_field_from_dict(dataservice_dict, dataservice_ref, DCT.title, DataserviceConstants.KEY_DATASERVICE_TITLE_TRANSLATED, None)

            # Applicable Legislation
            _profile_serialize_utils.add_resource_list_triple(g, dataservice_ref, DCATAP.applicableLegislation, self._get_dict_value(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_HVD_APPLICABLE_LEGISLATION), encode_url=_is_european_export)

            # HVD Catagory
            _profile_serialize_utils.add_resource_list_triple(g, dataservice_ref, DCATAP.hvdCategory, self._get_dict_value(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_HVD_CATEGORY), encode_url=_is_european_export)

            # Contact Point
            _profile_serialize_utils.add_vcard_kinds(g, dataservice_ref, DCAT.contactPoint, self._get_dict_value(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_CONTACT_POINT), encode_url=_is_european_export)

            # FOAF Page
            _profile_serialize_utils.add_resource_list_triple(g, dataservice_ref, FOAF.page, self._get_dict_value(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_PAGE), encode_url=_is_european_export)

             # Theme
            themes = self._get_dict_value(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_THEME)
            _profile_serialize_utils.add_resource_list_triple(g, dataservice_ref, DCAT.theme, themes, encode_url=_is_european_export)
            
            # check if is an export to european data portal
            if _is_european_export and not _profile_utils._has_european_data_themes(themes):
                # Add european theme taxonomy
                self._add_european_theme_tanonomies(dataservice_ref, dataservice_dict, themes, g)

            # publisher (extended info)
            publisher = self._get_value_from_dict(dataservice_dict, DatasetConstants.KEY_PUBLISHER_URI)
            if publisher:
                g.add((dataservice_ref, DCT.publisher, URIRef(publisher)))
                _profile_serialize_utils.set_publisher_metadata(publisher, allowed_publishers, g, self.default_locale)

            # EndpointURL
            _profile_serialize_utils.add_resource_list_triple(g, dataservice_ref, DCAT.endpointURL, self._get_dict_value(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_ENDPOINT_URL), encode_url=_is_european_export)

            # EndpointDescription
            _profile_serialize_utils.add_resource_list_triple(g, dataservice_ref, DCAT.endpointDescription, self._get_dict_value(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_ENDPOINT_DESCRIPTION), encode_url=_is_european_export)
            
            # ServesDataset
            _profile_serialize_utils.add_resource_list_triple(g, dataservice_ref, DCAT.servesDataset, self._get_dict_value(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_SERVES_DATASET), encode_url=_is_european_export)

            # Description
            self._add_translated_triple_field_from_dict(dataservice_dict, dataservice_ref, DCT.description, DataserviceConstants.KEY_DATASERVICE_DESCRIPTION, None)

            # AccessRights
            _profile_serialize_utils.add_resource_list_triple(g, dataservice_ref, DCT.accessRights, [self._get_dict_value(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_ACCESS_RIGHTS)], encode_url=_is_european_export)

            # License
            _profile_serialize_utils.add_resource_list_triple(g, dataservice_ref, DCT.license, [self._get_dict_value(dataservice_dict, DataserviceConstants.KEY_DATASERVICE_LICENSE)], encode_url=_is_european_export)

            # Tags
            self._add_translated_list_triple_field_from_dict(dataservice_dict, dataservice_ref, DCAT.keyword, DataserviceConstants.KEY_DATASERVICE_MULTILINGUAL_TAGS, None)

        except Exception as e:
            log.error(f'{method_log_prefix} [dataservice_ref: {dataservice_ref}.Unexpected Error {type(e).__name__}: {e}', exc_info=True)

    def _get_config_reader(self, data_dict):
        DEFAULT_CONFIG_FILEPATH = config.get('ckanext.dge_harvest.dcat_ap_es_1_0_0.config.filepath', '')
        config_reader =  data_dict.get(SerializerConstants.CONFIG_READER, None)
        if not config_reader:
            config_reader = HarvesterConfigReader(DEFAULT_CONFIG_FILEPATH)
        return config_reader

    def _get_available_organizations(self, data_dict):
        available_organizations = None
        if data_dict:
            available_organizations = data_dict.pop(SerializerConstants.AVAILABLE_ORGANIZATIONS, {})
        if not available_organizations:
            available_organizations = dhh.dge_harvest_organizations_available()
        return available_organizations
    
    def _add_european_theme_tanonomies(self, package_ref, package_dict, themes, g):
        # Add european theme taxonomy
        mapping_nti_european_themes_dict = package_dict.get(SerializerConstants.MAPPING_NTI_RISP_THEMES_EUROPEAN_THEMES, {})
        european_themes = set()
        for theme in themes:
            european_theme = mapping_nti_european_themes_dict.get(theme, None)
            if european_theme and european_theme not in european_themes:
                g.add((package_ref, DCAT.theme, URIRef(european_theme)))
                european_themes.add(european_theme)

    def _get_frequency_value(self, subject, predicate):
        f_type, f_value, f_uri = self.base_parse_utils._get_frequency(subject, predicate)
        if (f_type and f_value is not None and f_uri is not None):
            if (f_value > 0 or f_value == -1):
                return {HarvesterConstants.FREQUENCY_TYPE: f_type, 
                        HarvesterConstants.FREQUENCY_VALUE: f_value, 
                        HarvesterConstants.FREQUENCY_URI: f_uri}
            else:
                raise RDFProfileException(HarvesterConstants.WRONG_FREQUENCY_VALUE)

    def _add_to_dictionary_if_value_not_empty(self, data_dict, key, value, do_json_dumps=False):
        if data_dict and value:
            if do_json_dumps:
                data_dict[key] = json.dumps(value)
            else:
                data_dict[key] = value
