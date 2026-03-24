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

from .constants import ConfigConstants, PrefixConstants, CatalogConstants, DatasetConstants, DataserviceConstants, HarvesterConstants, CommonPackageConstants
from enum import Enum
from rdflib.namespace import Namespace, RDF, XSD, SKOS, RDFS

# NAMESPACES
XSD_NAMESPACE = XSD._NS #Namespace("http://www.w3.org/2001/XMLSchema#")
SKOS_NAMESPACE = SKOS._NS #Namespace("http://www.w3.org/2004/02/skos/core#")
ADMS = Namespace('http://www.w3.org/ns/adms#')
DCAT = Namespace('http://www.w3.org/ns/dcat#')
DCATAP = Namespace('http://data.europa.eu/r5r/')
DCT = Namespace('http://purl.org/dc/terms/')
DC =  Namespace('http://purl.org/dc/elements/1.1/')
TIME = Namespace('http://www.w3.org/2006/time#')
FOAF = Namespace('http://xmlns.com/foaf/0.1/')
LOCN = Namespace('http://www.w3.org/ns/locn#')
OWL =  Namespace('http://www.w3.org/2002/07/owl#')
ODRL = Namespace('http://www.w3.org/ns/odrl/2/')
PROV = Namespace('http://www.w3.org/ns/prov#')
RDFS_NAMESPACE = RDFS._NS #Namespace('http://www.w3.org/2000/01/rdf-schema#')
RDF_NAMESPACE = RDF._NS #Namespace('http://www.w3.org/1999/02/22-rdf-syntax-ns#')
SCHEMA = Namespace('http://schema.org/')
SPDX =  Namespace('http://spdx.org/rdf/terms#')
VANN = Namespace('http://purl.org/vocab/vann/')
VOAF =  Namespace('http://purl.org/vocommons/voaf#')
VCARD = Namespace('http://www.w3.org/2006/vcard/ns#')
HYDRA = Namespace('http://www.w3.org/ns/hydra/core#')
ELI = Namespace('http://data.europa.eu/eli/ontology#')

XSD_PREFIX = 'xsd'
SKOS_PREFIX = 'skos'
ADMS_PREFIX = 'adms'
DCAT_PREFIX = 'dcat'
DCATAP_PREFIX = 'dcatap'
DCT_PREFIX = 'dct'
DC_PREFIX =  'dc'
TIME_PREFIX = 'time'
FOAF_PREFIX = 'foaf'
LOCN_PREFIX = 'locn'
OWL_PREFIX =  'owl'
ODRL_PREFIX = 'odrl'
PROV_PREFIX = 'prov'
RDFS_PREFIX = 'rdfs'
RDF_PREFIX = 'rdf'
SCHEMA_PREFIX = 'schema'
SPDX_PREFIX =  'spdx'
VANN_PREFIX = 'vann'
VOAF_PREFIX = 'voaf'
VCARD_PREFIX = 'vcard'
HYDRA_PREFIX = 'hydra'
ELI_PREFIX = 'eli'
    
NAMESPACES = {
    XSD_PREFIX: XSD._NS,
    SKOS_PREFIX: SKOS._NS,
    ADMS_PREFIX: ADMS,
    DCAT_PREFIX: DCAT,
    DCATAP_PREFIX: DCATAP,
    DCT_PREFIX: DCT,
    DC_PREFIX: DC,
    TIME_PREFIX: TIME,
    FOAF_PREFIX: FOAF,
    LOCN_PREFIX: LOCN,
    OWL_PREFIX: OWL,
    ODRL_PREFIX: ODRL,
    PROV_PREFIX: PROV,
    RDFS_PREFIX: RDFS._NS,
    RDF_PREFIX: RDF._NS,
    SCHEMA_PREFIX: SCHEMA,
    SPDX_PREFIX: SPDX,
    VANN_PREFIX: VANN,
    VOAF_PREFIX: VOAF,
    VCARD_PREFIX: VCARD,
    ELI_PREFIX: ELI
}

TIME_TYPES = [
    TIME.seconds,
    TIME.minutes,
    TIME.hours,
    TIME.days,
    TIME.weeks,
    TIME.months,
    TIME.years
    ]

'''
Stores constants with
 metadata names
 the error and warning messages used in the harvester
'''
class DCATAPESConfigConstants(ConfigConstants):
    METADATA_VOCABULARIES_DICT = 'METADATA_VOCABULARIES_DICT'
    METADATA_VOCABULARIES_HVD_DICT = 'METADATA_VOCABULARIES_HVD_DICT'
    COMBINED_METADATA_VOCABULARIES_DICT = 'COMBINED_METADATA_VOCABULARIES_DICT' # Combine dictionaries of METADATA_VOCABULARIES_DICT y METADATA_VOCABULARIES_HVD_DICT
    SHACL_SHAPES = "SHACL_SHAPES"
    SHACL_SHAPES_HVD = "SHACL_SHAPES_HVD"
    COMBINED_SHACL_SHAPES = 'COMBINED_SHACL_SHAPES' # Combine SHACL_SHAPES WITH SHACL_SHAPES_HVD
    
    
    SECTION_BASIC = 'basic'
    SECTION_CATALOG = 'catalog'
    SECTION_DATASERVICE = 'dataservice'
    SECTION_DATASET = 'dataset'
    SECTION_DISTRIBUTION = 'distribution'
    SECTION_RDF_EXPORT = 'rdf.export'
    SECTION_CSV_EXPORT = 'csv.export'
    
    PROP_METADATA_VOCABULARIES='.metadata.vocabularies'
    PROP_METADATA_VOCABULARIES_HVD='.metadata.vocabularies.hvd'

    PROP_SHACL_SHAPES = ".shacl.shapes"
    PROP_SHACL_SHAPES_HVD = ".shacl.shapes.hvd"
    
    PROP_EUROPEAN_THEME_TAXONOMY = 'rdf.export.european.theme.taxonomy'
    PROP_MAPPING_NTI_THEME_EUROPEAN_THEME = 'rdf.export.mapping.nti_risp_theme.european_theme'
    
    ROOT_CATALOG_EXPORT_PROPERTIES_PREFIX = 'rdf.export.catalog.'
    SUBCATALOG_EXPORT_PROPERTIES_PREFIX = 'rdf.export.subcatalog.'
    
    PROP_CSV_COLUMNS = 'csv.export.columns.filepath'
    PROP_CSV_FILEPATH = 'csv.export.filepath'

class DCATAPESPrefixConstants(PrefixConstants):
    SPATIAL_PREFIX = 'http://datos.gob.es/recurso/sector-publico/territorio/'
    SPATIAL_PROVINCE_PREFIX = 'http://datos.gob.es/recurso/sector-publico/territorio/Provincia/'
    SPATIAL_CCAA_PREFIX = 'http://datos.gob.es/recurso/sector-publico/territorio/Autonomia/'
    SPATIAL_EU_CONTINENT_PREFIX = 'http://publications.europa.eu/resource/authority/continent'
    SPATIAL_EU_COUNTRY_PREFIX = 'http://publications.europa.eu/resource/authority/country'
    SPATIAL_EU_PLACE_PREFIX = 'http://publications.europa.eu/resource/authority/place/'
    SPATIAL_EU_ATU_PREFIX = 'http://publications.europa.eu/resource/authority/atu'
    SPATIAL_GEONAMES_PREFIX = 'http://sws.geonames.org/'
    SPATIAL_GEONAMES_HTTPS_PREFIX = 'https://sws.geonames.org/'
    FORMAT_PREFIX_EDP = 'http://publications.europa.eu/resource/authority/file-type/'
    FORMAT_PREFIX_EDP_IANA = 'https://www.iana.org/assignments/media-types/'
    FORMAT_PREFIX_EDP_IANA_HTTP = 'http://www.iana.org/assignments/media-types/'
    FREQUENCY_PREFIX = 'http://publications.europa.eu/resource/authority/frequency/'
    THEME_EU_PREFIX = 'http://publications.europa.eu/resource/authority/data-theme'
    THEME_EU_PREFIX_SLASH = 'http://publications.europa.eu/resource/authority/data-theme/'
    INSPIRE_PREFIX = 'http://inspire.ec.europa.eu/'
    SPATIAL_PREFIXES_TUPLE = (
        SPATIAL_PREFIX,
        SPATIAL_EU_CONTINENT_PREFIX,
        SPATIAL_EU_COUNTRY_PREFIX,
        SPATIAL_EU_PLACE_PREFIX,
        SPATIAL_EU_ATU_PREFIX,
        SPATIAL_GEONAMES_PREFIX,
        SPATIAL_GEONAMES_HTTPS_PREFIX
    )

class DCATAPESCatalogConstants(CatalogConstants):
        
    KEY_CATALOG_HOMEPAGE = 'catalog_homepage'
    KEY_CATALOG_RIGHTS = 'catalog_rights'
    KEY_CATALOG_LICENSE = 'catalog_license'
    KEY_CATALOG_CATALOG = 'catalog_catalog'
    KEY_CATALOG_HAS_PART = 'catalog_has_part'
    KEY_CATALOG_IS_PART_OF = 'catalog_is_part_of'
    KEY_CATALOG_CREATOR = 'catalog_creator'
    
    METADATA_CATALOG_DATASERVICE = 'Dataservice (dcat:service)'
    METADATA_CATALOG_LANGUAGE = 'Idioma(s) (dct:language)'
    METADATA_CATALOG_TITLE = 'Nombre (dct:title)'
    METADATA_CATALOG_DESCRIPTION = 'Descripci\u00F3n (dct:description)'
    METADATA_CATALOG_PUBLISHER = '\u00D3rgano publicador (dct:publisher)'
    METADATA_CATALOG_HOMEPAGE = 'P\u00E1gina web (foaf:homepage)'
    METADATA_CATALOG_THEME_TAXONOMY = 'Tem\u00E1ticas (dcat:themeTaxonomy)'
    METADATA_CATALOG_ISSUED = 'Fecha de creaci\u00F3n (dct:issued)'
    METADATA_CATALOG_MODIFIED = 'Fecha de actualizaci\u00F3n (dct:modified)'

class DCATAPESDatasetConstants(DatasetConstants):
    KEY_DATASET_SERVED_BY_DATASERVICE = 'served_by_dataservice'
    KEY_DATASET_TYPE = 'dataset_type'
    KEY_DATASET_VERSION = 'dataset_version'
    KEY_DATASET_VERSION_NOTES = 'version_notes'
    KEY_DATASET_HVD_APPLICABLE_LEGISLATION = 'hvd_applicable_legislation'
    KEY_DATASET_HVD_CATEGORY = 'hvd_category'
    KEY_DATASET_ANOTHER_IDENTIFIER = 'another_identifier'
    KEY_DATASET_LANDING_PAGE = 'landing_page'
    KEY_DATASET_PAGE = 'page'
    KEY_DATASET_SAMPLE = 'sample'
    KEY_DATASET_HAS_VERSION = 'has_version'
    KEY_DATASET_IS_VERSION_OF = 'is_version_of'
    KEY_DATASET_IS_REFERENCED_BY = 'is_referenced_by'
    KEY_DATASET_PROVENANCE = 'provenance'
    KEY_DATASET_RELATION = 'relation'
    KEY_DATASET_WAS_GENERATED_BY = 'was_generated_by'
    KEY_DATASET_SOURCE = 'source'
    KEY_DATASET_ACCESS_RIGHTS = 'access_rights'
    KEY_DATASET_QUALIFIED_RELATION = 'qualified_relation'
    KEY_DATASET_SPATIAL_RESOLUTION_IN_METERS = 'spatial_resolution_in_meters'
    KEY_DATASET_TEMPORAL_RESOLUTION = 'temporal_resolution'
    KEY_DATASET_CREATOR = 'creator'
    KEY_DATASET_QUALIFIED_ATTRIBUTION = 'qualified_attribution'
    KEY_DATASET_CONTACT_POINT = 'contact_point'

class DCATAPESDistributionConstants():
    #KEY_DISTRIBUTION_URI = 'uri'
    KEY_DISTRIBUTION_CKAN_URI = 'ckan_uri'
    KEY_DISTRIBUTION_SOURCE_URI = 'source_uri'
    KEY_DISTRIBUTION_ACCESS_SERVICE = 'access_service'
    KEY_DISTRIBUTION_AN_ACCESS_URL = 'url'
    KEY_DISTRIBUTION_EXTRAS = 'extras'
    KEY_DISTRIBUTION_ACCESS_URL = 'access_url'
    KEY_DISTRIBUTION_DESCRIPTION = 'resource_description'
    KEY_DISTRIBUTION_TITLE = 'title'
    KEY_DISTRIBUTION_TITLE_TRANSLATED = 'name_translated'
    KEY_DISTRIBUTION_FORMAT = 'format'
    KEY_DISTRIBUTION_RESOURCE_FORMAT = 'resource_format'
    KEY_DISTRIBUTION_MEDIA_TYPE = 'media_type'
    KEY_DISTRIBUTION_LICENSE = 'resource_license'
    KEY_DISTRIBUTION_RIGHTS = 'resource_rights'
    KEY_DISTRIBUTION_STATUS = 'resource_status'
    KEY_DISTRIBUTION_PAGE = 'resource_page'
    KEY_DISTRIBUTION_DOWNLOAD_URL = 'download_url'
    KEY_DISTRIBUTION_ISSUED_DATE = 'resource_issued_date'
    KEY_DISTRIBUTION_MODIFIED_DATE = 'resource_modified_date'
    KEY_DISTRIBUTION_LANGUAGE = 'resource_language'
    KEY_DISTRIBUTION_COMPRESS_FORMAT = 'compress_format'
    KEY_DISTRIBUTION_PACKAGE_FORMAT = 'package_format'
    KEY_DISTRIBUTION_HAS_POLICY = 'has_policy'
    KEY_DISTRIBUTION_CONFORMS_TO = 'resource_conforms_to'
    KEY_DISTRIBUTION_BYTE_SIZE = 'byte_size'
    KEY_DISTRIBUTION_SPATIAL_RESOLUTION_IN_METERS = 'resource_spatial_resolution_in_meters'
    KEY_DISTRIBUTION_TEMPORAL_RESOLUTION = 'resource_temporal_resolution'
    KEY_DISTRIBUTION_AVAILABILITY = 'availability'
    KEY_DISTRIBUTION_CHECKSUM = 'checksum'
    KEY_DISTRIBUTION_HVD_APPLICABLE_LEGISLATION = 'resource_hvd_applicable_legislation'
    KEY_DISTRIBUTION_IS_SAMPLE = 'is_sample'
    

class DCATAPESDataserviceConstants(DataserviceConstants):
    KEY_DATASERVICE_HVD_APPLICABLE_LEGISLATION = DCATAPESDatasetConstants.KEY_DATASET_HVD_APPLICABLE_LEGISLATION
    KEY_DATASERVICE_HVD_CATEGORY = DCATAPESDatasetConstants.KEY_DATASET_HVD_CATEGORY
    KEY_DATASERVICE_PAGE = DCATAPESDatasetConstants.KEY_DATASET_PAGE
    KEY_DATASERVICE_CONTACT_POINT = DCATAPESDatasetConstants.KEY_DATASET_CONTACT_POINT
    
    # Constantes de dataService
    METADATA_DATASERVICE_TITLE = 'Nombre (dct:title)'

    # Metadata
    METADATA_DATASERVICE_TITLE = 'Nombre (dct:title)'
    METADATA_DATASERVICE_CKAN_TITLE = 'Nombre en CKAN (dct:title)'
    METADATA_DATASERVICE_DESCRIPTION = 'Descripci\u00F3n (dct:description)'
    METADATA_DATASERVICE_ENDPOINT_URL = 'URL(s) de acceso al servicio de datos (dcat:endpointURL)' 
    METADATA_DATASERVICE_ENDPOINT_DESCRIPTION = 'Descripci\u00F3n del punto de acceso (dcat:endpointDescription)'
    METADATA_DATASERVICE_SERVES_DATASET = 'Dataset que sirve el servicio (dcat:servesDataset)'
    METADATA_DATASERVICE_ACCESS_RIGHTS = 'Acceso (dcat:accessRights)'
    METADATA_DATASERVICE_LICENSE = 'Licencia (dct:license)'
    
    
class DCATAPESHarvesterConstants(HarvesterConstants):
    
    HARVESTER_TYPE = 'dge_dcat_ap_es_rdf'
    HARVESTER_PROFILE = 'dge_dcat_ap_es_profile'
    
    CATALOG_WRONG_DEFINITION = 'No se ha encontrado la URI del cat\u00E1logo o la etiqueta del cat\u00E1logo no ha sido declarada (rdf:about)'
    DATASET_WRONG_DEFINITION = 'No se ha encontrado la URI del dataset o la etiqueta del dataset no ha sido declarada (rdf:about)'
    
    IMPORT_ERROR = '[Error al importar el {} en base de datos] {}.'
    IMPORT_WARNING = '[Warning al importar el {} en base de datos] {}.'
    
    INTEGRITY_ERROR = 'Es posible que exista otro dataset en el cat\u00E1logo cuyo t\u00EDtulo en es coincida con el de otro dataset en los primeros 300 caracteres'
    
    # ERROR/WARNING DATASERVICE MESSAGES
    DATASERVICE_IMPORT_ERROR = '[Error al importar el dataservice en base de datos] {}.'
    DATASERVICE_VALIDATION_ERROR = '[Error al tratar el dataservice] {}.'
    DATASERVICE_VALIDATION_WARNING = '[Warning al tratar el dataservice] {}.'
    DATASERVICE_VALIDATION_ERROR_IDENTIFIER = '[Error al tratar el dataservice] {}.'
    DATASERVICE_VALIDATION_WARNING_IDENTIFIER = '[Warning al tratar el dataservice] {}.'
    DATASERVICE_WRONG_DEFINITION = 'No se ha encontrado la URI del dataset o la etiqueta del dataset no ha sido declarada (rdf:about)'
    DATASERVICE_SAME_ABOUT_DATASET = 'Existe al menos un dataset con la misma URI (rdf:about) que el dataservice: {}'
    DATASERVICE_SAME_ABOUT_DISTRIBUTION = 'Existe al menos una distribuci\u00F3n con la misma URI (rdf:about) que el dataset: {}'
    DATASERVICE_SAME_ABOUT_DATASERVICE = 'Existen al menos dos dataservices con la misma URI (rdf:about): {}'
    CATALOG_SAME_ABOUT_DATASERVICE = 'Existe al menos un dataset con la misma URI (rdf:about) que el cat\u00E1logo: {}'
    DATASET_SAME_ABOUT_DISTRIBUTION = 'Existe al menos una distribuci\u00F3n con la misma URI (rdf:about) que el dataset: {}'
    DATASERVICE_INTEGRITY_ERROR = 'Es posible que exista otro dataservice en el cat\u00E1logo cuyo t\u00EDtulo en es coincida con el de otro dataservice en los primeros 300 caracteres'


    VALIDATION_UNEXPECTED_ERROR_MESSAGE = '[ERROR][Node {}] {}'
    VALIDATION_ERROR_MESSAGE = '[ERROR][Node {}][Metadata {}] {}'
    VALIDATION_WARNING_MESSAGE = '[WARNING][Node {}][Metadata {}] {}'
    
    VALIDATION_SUBNODE_UNEXPECTED_ERROR_MESSAGE = '[ERROR][Node {} of {}] {}'
    VALIDATION_SUBNODE_ERROR_MESSAGE = '[ERROR][Node {} of {}][Metadata {}] {}'
    VALIDATION_SUBNODE_WARNING_MESSAGE = '[WARNING][Node {} of {}][Metadata {}] {}'
    
    WRONG_FREQUENCY_VALUE = 'El valor de la frecuencia no es correcto'
    WRONG_RANGE = 'Rango incorrecto'
    WRONG_VALUE = 'Valor incorrecto'
    NOT_FOUND = 'No encontrado'
    NOT_FOUND_IN_OFFERED_LANGUAGES = 'No encontrado en ning\u00FAn idioma ofrecido por el portal ({})'
    NOT_FOUND_IN_DEFAULT_LANGUAGE = 'No encontrado en el idioma por defecto del portal ({})'
    EMPTY_OR_NOT_VALUE = 'Vacío o sin valor'
    ORGANIZATION_NOT_FOUND = 'No existe una organizaci\u00F3n en el portal para el publicador dado.'
    THEME_TAXONOMY_NOT_FOUND = 'No encontrada la taxonom\u00EDa del portal'
    NO_LANGUAGE_KEY = 'no_language'
    OFFERED_LANGUAGES_NOT_FOUND = 'No encontrado ning\u00FAn idioma ofrecido por el portal ({})'
    DEFAULT_LANGUAGE_NOT_FOUND = 'No encontrado el idioma por defecto del portal ({})' 
    SHACL_VALIDATION_ERROR = 'Error al hacer las validaciones de vocabularios y SHACL de la url {}. Error: {}'
    PRE_VALIDATION_ERROR = 'Error al hacer la validaci\u00F3n RDF de la url {}. Error: {}'
    PREPROCESSING_ERROR = 'Error al hacer el preprocesamiento del RDF de la url {}. Error: {}'
    VIRTUOSO_LOAD_ERROR = 'Error en la carga de virtuoso de la url {}. Error: {}'
    CATALOG_STORE_ERROR_URL = '[Error al almacenar el cat\u00E1logo de la URL: {}] {}. El feed no ha sido procesado.'
    NOT_FOUND_SHACL_CONFIG_ERROR = 'Error al hacer la validation SHACL de la url {}. Faltan detalles de la configuraci\u00F3n. Póngase en contacto con un administrador.'
    
    DELETE_UNDESCRIBED_CATALOG = "[INFO] Se elimin\u00F3 un cat\u00E1logo referenciado no descrito: {}."
    DELETE_UNDESCRIBED_DATASET = "[INFO] Se elimin\u00F3 un conjunto de datos referenciado no descrito: {}."
    DELETE_UNDESCRIBED_DATASERVICE = "[INFO] Se elimin\u00F3 un servicio de datos referenciado no descrito: {}."
    DELETE_UNREFERENCED_DATASET_IN_CATALOG = "[INFO] Se eliminaron las referencias de un conjunto de datos no referenciado en el cat\u00E1logo {}."
    DELETE_UNREFERENCED_DATASERVICE_IN_CATALOG = "[INFO] Se eliminaron las referencias de un servicio de datos no referenciado en el cat\u00E1logo {}."
    DELETE_UNREFERENCED_DESCRIBED_DATASET = "[INFO] Se elimin\u00F3 un conjunto de datos descrito pero no referenciado en el cat\u00E1logo {}."
    DELETE_UNREFERENCED_DESCRIBED_DATASERVICE = "[INFO] Se elimin\u00F3 un servicio de datos descrito pero no referenciado en el cat\u00E1logo {}."
    DELETE_UNREFERENCED_NODE = "[INFO] Se elimin\u00F3 un nodo no referenciado {}."
    DELETE_CATALOG_RECORD = "[INFO] Se eliminaron las referencias y la entidad CatalogRecord {}."
    DELETE_DATASET_REFERENCE_IN_CATALOG = "[INFO] El conjunto de datos {} estaba referenciado en varios cat\u00E1logos. Para dejarlo referenciado solo en uno, se eliminaron las referencias en los siguientes cat\u00E1logos: {}."
    DELETE_DATASERVICE_REFERENCE_IN_CATALOG = "[INFO] El conjunto de datos {} estaba referenciado en varios cat\u00E1logos. Para dejarlo referenciado solo en uno, se eliminaron las referencias en los siguientes cat\u00E1logos: {}."
    DELETE_CATALOG = "[INFO] Se elimin\u00F3 un cat\u00E1logo que no cumple con las especificaciones: {}."
    DELETE_DATASERVICE = "[INFO] Se elimin\u00F3 un servicio de datos que no cumple con las especificaciones: {}."
    DELETE_HVD_DATASERVICE = "[INFO] Se elimin\u00F3 un servicio de datos HVD que no cumple con las especificaciones: {}."
    DELETE_DATASET = "[INFO] Se elimin\u00F3 un conjunto de datos que no cumple con las especificaciones: {}."
    DELETE_AGENT_DATA = "[INFO] URI de la organizaci\u00F3n publicadora recuperado: {}. Los datos proporcionados en el archivo RDF no se utilizar\u00E1n y ser\u00E1n reemplazados por la informaci\u00F3n ya disponible en datos.gob.es."
    DELETE_HVD_DATASET = "[INFO] Se elimin\u00F3 un conjunto de datos HVD que no cumple con las especificaciones: {}."
    NO_VALID_DISTRIBUTION_IN_DATASET ="[ERROR] No hay distribuciones v\u00E1lidas en el conjunto de datos {}."
    NO_DATA_TO_HARVEST = "[INFO] No hay objetos para federar."
    CATALOG_WITH_ERRORS = "[ERROR] Existen cat\u00E1logos con errores. Para realizar la federaci\u00F3n, todos los cat\u00E1logos deben ser v\u00E1lidos."
    
    # profile import stage constants
    CONTACT_POINT_VCARD_CLASSES = (VCARD.Kind, VCARD.Organization, VCARD.Group, VCARD.Individual, VCARD.Location)
    CONTACT_POINT_VCARD_FN = 'fn_translated'
    CONTACT_POINT_VCARD_ORGANIZATION_NAME = 'organization-name_translated'
    CONTACT_POINT_VCARD_HAS_EMAIL = 'has_email'
    CONTACT_POINT_VCARD_HAS_TELEPHONE = 'has_telephone'
    CONTACT_POINT_VCARD_HAS_URL = 'has_url'
    CONTACT_POINT_VCARD_HAS_UID = 'has_uid'

    SPATIAL_URI = 'uri'
    SPATIAL_LOCATION_BBOX = 'bbox'
    SPATIAL_LOCATION_CENTROID = 'centroid'
    SPATIAL_LOCATION_GEOMETRY = 'geometry'

    FREQUENCY_URI = 'uri'
    FREQUENCY_TYPE = 'type'
    FREQUENCY_VALUE = 'value'

    CREATOR_NAME = 'creator_name_translated'
    CREATOR_IDENTIFIER = 'creator_identifier'
    CREATOR_TYPE = 'creator_type'
    
    RELATIONSHIP_HAD_ROLE = 'had_role'
    RELATIONSHIP_RELATION = 'qualified_relation_relation'
    
    ATTRIBUTION_HAD_ROLE = 'had_role'
    ATTRIBUTION_AGENT = 'agent'
    
    CHECKSUM_ALGORITHM = 'algorithm'
    CHECKSUM_CHECKSUM_VALUE = 'checksum_value'
    

class DCATAPESSerializerConstants:
    CONFIG_READER = 'CONFIG_READER' # Contains HarvesterConfigReader
    CATALOG_EXPORT_PROPERTIES_PREFIX = 'CATALOG_EXPORT_PROPERTIES_PREFIX' # Preffix to get properties of HarvesterConfigReader
    EUROPEAN_CATALOG_EXPORT = 'EUROPEAN_CATALOG_EXPORT' # True if is an export to european data portal, False in other case
    MAPPING_NTI_RISP_THEMES_EUROPEAN_THEMES = 'MAPPING_NTI_RISP_THEMES_EUROPEAN_THEMES' # Contains dictionary with mapping between nti - european themes
    CATALOG_URI_REF = 'CATALOG_URI_REF' # Contains the catalog_uri_ref to serialize
    EUROPEAN_THEME_TAXONOMY = 'EUROPEAN_THEME_TAXONOMY'  # Contains de value of european theme taxonomy
    AVAILABLE_ORGANIZATIONS = 'AVAILABLE_ORGANIZATIONS' 

class DcatClassNameEnum(Enum):
    CATALOG = "Catalog"
    DATASET = "Dataset"
    DATASERVICE = "Dataservice"
    DISTRIBUTION ="Distribution"

class HarvestObjectExtraKeyConstants():
    HOE_GRAPH_NAME_KEY = 'graph_name'
    HOE_SOURCE_URI_KEY = 'source_uri'
    HOE_HARVESTER_TYPE = 'harvester_type'
    HOE_CKAN_URI_KEY = 'ckan_uri'
    HOE_CKAN_NAME_KEY = 'ckan_name'
    HOE_PACKAGE_TYPE_KEY = 'package_type'
    HOE_PACKAGE_TYPE_DATASERVICE_VALUE = CommonPackageConstants.KEY_TYPE_DATASERVICE_VALUE
    HOE_PACKAGE_TYPE_DATASET_VALUE = CommonPackageConstants.KEY_TYPE_DATASET_VALUE