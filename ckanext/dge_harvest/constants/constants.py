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

'''
Stores common constants with
 metadata names
 the error and warning messages used in the harvester
'''

class ConfigConstants:

    # Keys of harvest source config properties
    HS_PROP_USER = 'user'
    HS_PROP_READ_ONLY = 'read_only'
    HS_PROP_DEFULT_CATALOG_LANGUAGE = 'default_catalog_language'
    HS_PROP_RDF_FORMAT = 'rdf_format'

    # Keys of ckan config properties
    CKAN_PROP_LOCALES_OFFERED = 'ckan.locales_offered'
    CKAN_PROP_LOCALE_DEFAULT = 'ckan.locale_default'
    CKAN_PROP_LOCALE_ORDER = 'ckan.locale_order'
    CKAN_PROP_HTTP_PROXY = 'ckanext.dge_harvest.http_proxy'
    CKAN_PROP_HTTPS_PROXY = 'ckanext.dge_harvest.https_proxy'
    CKAN_PROPERTIES_PREFIX = 'ckanext.dge_harvest.catalog.'


    # Extras keys from organization
    ORG_PROP_ID_UD_ORGANICA = 'C_ID_UD_ORGANICA'
    ORG_PROP_ID_UD_PRINCIPAL = 'C_ID_DEP_UD_PRINCIPAL'
    ORG_PROP_NOMBRE_UD_RAIZ = 'C_DNM_DEP_UD_PRINCIPAL'

    DEFAULT_TIMEZONE = 'Europe/Madrid'

    DATASETS_PER_PAGE = 500
    TRIPLES_PER_QUERY = 2000

class PrefixConstants():
    THEME_PREFIX = 'http://datos.gob.es/kos/sector-publico/sector'
    THEME_PREFIX_SLASH = 'http://datos.gob.es/kos/sector-publico/sector/'
    PUBLISHER_PREFIX = 'http://datos.gob.es/recurso/sector-publico/org/Organismo/'
    LANGUAGE_PREFIX_EDP = 'http://publications.europa.eu/resource/authority/language/'

class CatalogConstants:
    # Keys of catalog dictionary
    KEY_CATALOG_LANGUAGE = 'catalog_language'
    KEY_CATALOG_THEME_TAXONOMY = 'catalog_theme_taxonomy'
    KEY_CATALOG_URI = 'catalog_uri'
    KEY_CATALOG_ERRORS = 'catalog_errors'
    KEY_CATALOG_WARNINGS = 'catalog_warnings'
    KEY_CATALOG_PUBLISHER = 'catalog_publisher'
    KEY_CATALOG_PUBLISHER_NAME = 'catalog_publisher_display_name'
    KEY_CATALOG_PUBLISHER_URI = 'catalog_publisher_uri'
    KEY_CATALOG_PUBLISHER_ID_MINHAP = 'catalog_publisher_id_minhap'
    KEY_CATALOG_TITLE_TRANSLATE = 'catalog_title_translated'
    KEY_CATALOG_DESCRIPTION = 'catalog_description'
    KEY_CATALOG_ISSUED_DATE = 'catalog_issued_date'
    KEY_CATALOG_MODIFIED_DATE = 'catalog_modified_date'
    KEY_CATALOG_SPATIAL = 'catalog_spatial'


class CommonPackageConstants:
    KEY_URI = 'uri'
    KEY_NAME = 'name'
    KEY_TITLE = 'title'
    KEY_OWNER_ORG = 'owner_org'
    KEY_EXTRAS = 'extras'
    KEY_ID = 'id'
    KEY_STATE = 'state'
    KEY_PUBLISHER_ID_MINHAP = 'publisher_id_minhap'
    KEY_PUBLISHER = 'publisher'
    KEY_PUBLISHER_URI = 'publisher_uri'
    KEY_PUBLISHER_NAME = 'publisher_name'
    KEY_ERRORS = 'errors'
    KEY_WARNINGS = 'warnings'
    KEY_EXTRAS_GUID = 'guid'
    KEY_EXTRAS_HVD = 'hvd'
    KEY_EXTRAS_CKAN_URI = 'ckan_uri'
    KEY_EXTRAS_SOURCE_URI = 'source_uri'
    KEY_EXTRAS_APPLICATION_PROFILE = 'application_profile'
    KEY_EXTRAS_APPLICATION_PROFILE_NTI_VALUE = 'nti'
    KEY_EXTRAS_APPLICATION_PROFILE_DCAT_AP_ES_100_VALUE = 'dcatapes_100'
    KEY_TYPE = 'type'
    KEY_RESOURCES = 'resources'
    KEY_METADATA_MODIFIED = 'metadata_modified'
    KEY_METADATA_CREATED = 'metadata_created'
    CATALOG_RECORD_URI_SUFFIX = '/record'
    CONFORMS_TO_SHACL = 'conforms_to_shacl'
    KEY_TYPE_DATASET_VALUE = 'dataset'
    KEY_TYPE_DATASERVICE_VALUE = 'dataservice'
    KEY_VISIBILIDAD = 'visibilidad'
    VALUE_VISIBILIDAD = 'publico'

class DatasetConstants(CommonPackageConstants):
    # Keys of dataset dictionary
    KEY_DATASET_IDENTIFIER = 'identifier'
    KEY_DATASET_MULTILINGUAL_TAGS = 'multilingual_tags'
    KEY_DATASET_ISSUED_DATE = 'issued_date'
    KEY_DATASET_MODIFIED_DATE = 'modified_date'
    KEY_DATASET_THEME = 'theme'
    KEY_DATASET_DESCRIPTION = 'description'
    KEY_DATASET_TITLE_TRANSLATED = 'title_translated'
    KEY_DATASET_FREQUENCY = 'frequency'
    KEY_DATASET_LANGUAGE = 'language'
    KEY_DATASET_SPATIAL = 'spatial'
    KEY_DATASET_TEMPORAL_COVERAGE = 'coverage_new'
    KEY_DATASET_NORMATIVE = 'conforms_to'


class DataserviceConstants(CommonPackageConstants):
    # DICTIONARY KEY
    KEY_DATASERVICE_TITLE_TRANSLATED = DatasetConstants.KEY_DATASET_TITLE_TRANSLATED
    KEY_DATASERVICE_DESCRIPTION = DatasetConstants.KEY_DATASET_DESCRIPTION
    KEY_DATASERVICE_ENDPOINT_URL = 'endpoint_url'
    KEY_DATASERVICE_ENDPOINT_DESCRIPTION = 'endpoint_description'
    KEY_DATASERVICE_SERVES_DATASET = 'serves_dataset'
    KEY_DATASERVICE_ACCESS_RIGHTS = 'access_rights'
    KEY_DATASERVICE_LICENSE = 'license_id'
    KEY_DATASERVICE_THEME = 'theme'
    KEY_DATASERVICE_MULTILINGUAL_TAGS = 'multilingual_tags'

class HarvesterConstants:
    #ERROR ACCESS, DOWNLOAD AND PARSER TO RDF URL
    CATALOG_ACCESS_ERROR_URL = '[Error al acceder al cat\u00E1logo en la URL: {}] {}. El feed no ha sido procesado.'
    CATALOG_ACCESS_ERROR = '[Error al acceder al cat\u00E1logo. {}] El feed no ha sido procesado.'
    CATALOG_DOWNLOAD_ERROR_URL = '[Error al descargar al cat\u00E1logo en la URL: {}] {}. El feed no ha sido procesado.'
    CATALOG_DOWNLOAD_ERROR = '[Error al descargar el cat\u00E1logo] {}. El feed no ha sido procesado.'
    CATALOG_PARSER_ERROR_URL = '[Error al parsear el cat\u00E1logo en la URL: {}] {}. El feed no ha sido procesado.'
    CATALOG_PARSER_ERROR = '[Error al parsear el cat\u00E1logo dcat] {}. El feed no ha sido procesado.'
    CATALOG_FILE_SOFT_LIMIT_INFO = '[INFO] El RDF federado ha sobrepasado el umbral advertido de {} MB. Es necesario paginar el fichero para evitar futuros fallos en la federaci\u00F3n al superar el tama\u00F1o soportado.'

    UNEXPECTED_ERROR = '{}: {}'

    UNEXPECTED_MULTIPLE_OBJECTS = "Varios objetos encontrados"

    UNEXPECTED_PUBLISHER_CATALOG_OWNER_SOURCE = 'La organizaci\u00F3n publicadora del cat\u00E1logo no se corresponde con la organizaci\u00F3n asociada al harvest source'

    LOG_CATALOG_ERROR_SUMMARY = '''ERROR/WARNING SUMMARY IN GATHER STAGE FOR THE CATALOG WITH URIRef {}:
                        \n\tcatalog warnings={},
                        \n\tcatalog errors={}'''

    GRAPH_NAME_SEPARATOR_CHARACTER = ':'
    SUFFIX_GRAPH_NAME_OF_PREVIOUS_HARVEST = f'{GRAPH_NAME_SEPARATOR_CHARACTER}old'

    FAILED_REQUESTS_HEAD_STATUS_CODES_FOR_REQUESTS_GET = [405, 400, 404, 403]

class ExportCatalogConstants:

    # parts of rfd
    CATALOG = 'Cat\u00E1logo'
    DATASET = 'Dataset'
    DISTRIBUTION = 'Distribuci\u00F3n'
    DATASERVICE = 'DataService'

class RDFStoreConstants:

    # Type of triple elements
    SUBJECT = 's'
    PREDICATE = 'p'
    OBJECT = 'o'

    # Vocabularies
    ADMS_URI = 'http://www.w3.org/ns/adms#'

class ViewsConstants:

    QUEUE_DELETE_DATASETS = "delete_dataset"
    DATASET_TYPE_NAME = "harvest"

