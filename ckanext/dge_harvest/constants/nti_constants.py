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

from .constants import PrefixConstants, CatalogConstants, DatasetConstants, HarvesterConstants

'''
Stores constants with
 metadata names
 the error and warning messages used in the harvester
'''



class NTIPrefixConstants(PrefixConstants):
    SPATIAL_PREFIX = 'http://datos.gob.es/recurso/sector-publico/territorio/'
    SPATIAL_PROVINCE_PREFIX = 'http://datos.gob.es/recurso/sector-publico/territorio/Provincia/'
    SPATIAL_CCAA_PREFIX = 'http://datos.gob.es/recurso/sector-publico/territorio/Autonomia/'
    FORMAT_PREFIX_EDP = 'http://publications.europa.eu/resource/authority/file-type/'
    FORMAT_PREFIX_EDP_IANA = 'https://www.iana.org/assignments/media-types/'

class NTICatalogConstants(CatalogConstants):
    # Keys of catalog dictionary
    KEY_CATALOG_SIZE = 'catalog_size'
    KEY_CATALOG_IDENTIFIER = 'catalog_identifier'
    
    KEY_CATALOG_SPATIAL = 'catalog_spatial'
    KEY_CATALOG_HOMEPAGE = 'catalog_homepage'
    KEY_CATALOG_LICENSE = 'catalog_license_id'
    
    KEY_CATALOG_AVAILABLE_DATA = 'available_data'
    KEY_CATALOG_AVAILABLE_THEMES = 'available_themes'
    KEY_CATALOG_AVAILABLE_SPATIAL_COVERAGES = 'available_spatial_coverages'
    KEY_CATALOG_AVAILABLE_RESOURCE_FORMATS = 'available_resource_formats'
    KEY_CATALOG_AVAILABLE_PUBLISHERS = 'available_publishers'

    # metadata names
    METADATA_CATALOG_TITLE = 'Nombre (dct:title)'
    METADATA_CATALOG_DESCRIPTION = 'Descripci\u00F3n (dct:description)'
    METADATA_CATALOG_PUBLISHER = '\u00D3rgano publicador (dct:publisher)'
    METADATA_CATALOG_EXTENT = 'Tama\u00F1o del cat\u00E1logo (dct:extent)'
    METADATA_CATALOG_IDENTIFIER = 'Identificador (dct:identifier)'
    METADATA_CATALOG_ISSUED = 'Fecha de creaci\u00F3n (dct:issued)'
    METADATA_CATALOG_MODIFIED = 'Fecha de actualizaci\u00F3n (dct:modified)'
    METADATA_CATALOG_LANGUAGE = 'Idioma (dc:language o dct:language)'
    METADATA_CATALOG_LANGUAGES = 'Idioma(s) (dc:language o dct:language)'
    METADATA_CATALOG_SPATIAL = 'Cobertura geogr\u00E1fica (dct:spatial)'
    METADATA_CATALOG_THEME_TAXONOMY = 'Tem\u00E1ticas (dcat:themeTaxonomy)'
    METADATA_CATALOG_HOMEPAGE = 'P\u00E1gina web (foaf:homepage)'
    METADATA_CATALOG_LICENSE = 'T\u00E9rminos de uso (dct:license)'
    METADATA_CATALOG_DATASET = 'Dataset (dcat:dataset)'
    METADATA_CATALOG_DATASETS = 'Datasets (dcat:dataset)'

class NTIDatasetConstants(DatasetConstants):
    # Keys of dataset dictionary
    KEY_DATASET_TAGS = 'tags'
    
    KEY_DATASET_DEFAULT_CATALOG_LANGUAGE = 'default_catalog_language'

    KEY_DATASET_PUBLISHER_NAME = 'publisher_display_name'
    KEY_DATASET_LICENSE = 'license_id'
    KEY_DATASET_VALID = 'valid'
    KEY_DATASET_REFERENCE = 'reference'
    
    KEY_DATASET_RESOURCE_LICENSE = 'resource_license'
    KEY_DATASET_RESOURCE_MEDIATYPE = 'media_type'
    KEY_DATASET_RESOURCE_KEY_MEDIATYPE_OR_EXTENT = 'mediatypeorextent_identifer'
    KEY_DATASET_RESOURCE_EXTRA_ACCESS_URL = 'access_url'
    KEY_DATASET_RESOURCE_IDENTIFIER = 'resource_identifier'
    KEY_DATASET_RESOURCE_NAME_TRANSLATED = 'name_translated'
    KEY_DATASET_RESOURCE_ACCESS_URL = 'url'
    KEY_DATASET_RESOURCE_MIMETYPE = 'mimetype'
    KEY_DATASET_RESOURCE_FORMAT = 'format'
    KEY_DATASET_RESOURCE_BYTE_SIZE = 'byte_size'
    KEY_DATASET_RESOURCE_RELATION = 'resource_relation'
    
    KEY_DATASET_HASH = 'hash'

    # metadata names
    METADATA_DATASET_TITLE = 'Nombre (dct:title)'
    METADATA_DATASET_CKAN_TITLE = 'Nombre en CKAN (dct:title)'
    METADATA_DATASET_DESCRIPTION = 'Descripci\u00F3n (dct:description)'
    METADATA_DATASET_THEME = 'Tem\u00E1tica (dcat:theme)'
    METADATA_DATASET_THEME = 'Tem\u00E1ticas (dcat:theme)'
    METADATA_DATASET_KEYWORD = 'Etiqueta (dcat:keyword)'
    METADATA_DATASET_KEYWORDS = 'Etiqueta(s) (dcat:keyword)'
    METADATA_DATASET_IDENTIFIER = 'Identificador (dct:identifier)'
    METADATA_DATASET_ISSUED = 'Fecha de creaci\u00F3n (dct:issued)'
    METADATA_DATASET_MODIFIED = 'Fecha de \u00FAltima actualizaci\u00F3n (dct:modified)'
    METADATA_DATASET_ACCRUAL_PERIODICITY = 'Frecuencia de actualizaci\u00F3n (dct:accrualPeriodicity)'
    METADATA_DATASET_LANGUAGE = 'Idioma(s) (dc:language o dct:language)'
    METADATA_DATASET_PUBLISHER = 'Organismo publicador (dct:publisher)'
    METADATA_DATASET_LICENSE = 'Condiciones de uso (dct:license)'
    METADATA_DATASET_SPATIAL = 'Cobertura geogr\u00E1fica (dct:spatial)'
    METADATA_DATASET_TEMPORAL = 'Cobertura temporal (dct:temporal)'
    METADATA_DATASET_VALID = 'Vigencia del recurso (dct:valid)'
    METADATA_DATASET_REFERENCES = 'Recurso(s) relacionado(s) (dct:references)'
    METADATA_DATASET_CONFORMS_TO = 'Normativa (dct:conformsTo)'
    METADATA_DATASET_DISTRIBUTION = 'Distribuci\u00F3n (dcat:distribution)'
    METADATA_DATASET_DISTRIBUTIONS = 'Distribuci\u00F3n(es) (dcat:distribution)'


    METADATA_DISTRIBUTION_IDENTIFIER = 'Identificador de la distribuci\u00F3n (dct:identifier)'
    METADATA_DISTRIBUTION_TITLE = 'Nombre de la distribuci\u00F3n (dct:title)'
    METADATA_DISTRIBUTION_ACCESS_URL = 'URL de acceso de la distribuci\u00F3n (dcat:accessURL)'
    METADATA_DISTRIBUTION_MEDIA_TYPE = 'Formato de la distribuci\u00F3n (dcat:mediaType)'
    METADATA_DISTRIBUTION_BYTE_SIZE = 'Tama\u00F1o de la distribuci\u00F3n (dcat:byteSize)'
    METADATA_DISTRIBUTION_RELATION = 'Informaci\u00F3n adicional de la distribuci\u00F3n (dct:relation)'
    METADATA_DISTRIBUTION_PREFIX_MESSAGE = 'Error en la distribuci\u00F3n: {}'
    METADATA_DISTRIBUTION_NO_IDENTIFIER = '(Sin identificador)'

class NTIHarvesterConstants(HarvesterConstants):
    
    # ERROR/WARNING CATALOG MESSAGES
    CATALOG_VALIDATION_ERRORS_URL = '[Errores al tratar el cat\u00E1logo en la URL: {}] {}. El feed no ha sido procesado.'
    CATALOG_VALIDATION_ERROR_URL = '[Error al tratar el cat\u00E1logo en la URL: {}] {}. El feed no ha sido procesado.'
    CATALOG_VALIDATION_ERRORS = '[Errores al tratar el cat\u00E1logo] {}. El feed no ha sido procesado.'
    CATALOG_VALIDATION_ERROR = '[Error al tratar el cat\u00E1logo. {}] El feed no ha sido procesado.'
    CATALOG_VALIDATION_WARNINGS_URL = '[Warning al tratar el cat\u00E1logo en la URL: {}] {}.'
    CATALOG_VALIDATION_WARNING_URL = '[Warning al tratar el cat\u00E1logo en la URL: {}] {}.'
    CATALOG_VALIDATION_WARNINGS = '[Warnings al tratar el cat\u00E1logo] {}.'
    CATALOG_VALIDATION_WARNING = '[Warning al tratar el cat\u00E1logo] {}.'
    CATALOG_WRONG_DEFINITION = 'No se ha encontrado la URI del cat\u00E1logo o la etiqueta del cat\u00E1logo no ha sido declarada (rdf:about)'
    CATALOG_LANGUAGE_NOT_FOUND = 'No se ha encontrado el campo: {} del cat\u00E1logo. (Idiomas soportados: {})'
    CATALOG_NO_LANGUAGES = 'No est\u00E1 definido el idioma del cat\u00E1logo'
    DEFAULT_LANGUAGE_NOT_FOUND = 'No se ha encontrado el {} obligatorio {}'

    # ERROR/WARNING DATASET MESSAGES
    DATASET_IMPORT_ERROR = '[Error al importar el dataset en base de datos] {}.'
    DATASET_IMPORT_WARNING = '[Warning al importar el dataset en base de datos] {}.'
    DATASET_VALIDATION_ERROR = '[Error al tratar el dataset] {}.'
    DATASET_VALIDATION_WARNING = '[Warning al tratar el dataset] {}.'
    DATASET_VALIDATION_ERROR_IDENTIFIER = '[Error al tratar el dataset] {}.'
    DATASET_VALIDATION_WARNING_IDENTIFIER = '[Warning al tratar el dataset] {}.'
    DATASET_WRONG_DEFINITION = 'No se ha encontrado la URI del dataset o la etiqueta del dataset no ha sido declarada (rdf:about)'
    DATASET_SAME_ABOUT_DISTRIBUTION = 'Existe al menos una distribuci\u00F3n con la misma URI (rdf:about) que el dataset: {}'
    DATASET_SAME_ABOUT_DATASET = 'Existen al menos dos datasets con la misma URI (rdf:about): {}'
    DATASET_SAME_ABOUT_DATASET = 'Existen al menos dos dataservices con la misma URI (rdf:about): {}'
    DISTRIBUTION_SAME_ABOUT_DISTRIBUTION = 'Existen al menos dos distribuciones con la misma URI (rdf:about): {}'
    CATALOG_SAME_ABOUT_DATASET = 'Existe al menos un dataset con la misma URI (rdf:about) que el cat\u00E1logo: {}'
    CATALOG_SAME_ABOUT_DISTRIBUTION = 'Existe al menos una distribuci\u00F3n con la misma URI (rdf:about) que el cat\u00E1logo: {}'
    DATASET_INTEGRITY_ERROR = 'Es posible que exista otro dataset en el cat\u00E1logo cuyo t\u00EDtulo en es coincida con el de otro dataset en los primeros 300 caracteres'
    DATASET_DUPLICATED_IDENTIFIER = 'El campo %s debe ser \u00FAnico. El siguiente identificador est\u00E1 duplicado: %s'

    # ERROR/WARNING DISTRIBUTION MESSAGES
    DISTRIBUTION_VALIDATION_ERROR = '[Error al tratar el dataset][Error al tratar la distribución]'
    DISTRIBUTION_VALIDATION_ERROR_ID = '[Error al tratar el dataset][Error al tratar la distribución:{}]'
    
    # ERROR/WARNING COMMON MESSAGES
    UNEXPECTED_LANGUAGES = '{} mal definido o no soportado por el portal: {}. (Idiomas soportados: {})'
    NO_LANGUAGES = 'No se define ning\u00FAn {}. (Idiomas soportados: {})'
    EXPECTED_IN_ALL_CATALOG_LANGUAGE = 'El campo {} no est\u00E1 en todos los idiomas del cat\u00E1logo'
    EXPECTED_IN_DEFAULT_CATALOG_LANGUAGE = 'El campo {} no est\u00E1 en al menos el idioma requerido del cat\u00E1logo ({})'
    UNEXPECTED_MULTIPLES_VALUES_SAME_LANGUAGE = 'El campo {} aparece varias veces definido con el idioma {}'
    UNEXPECTED_MULTIPLES_VALUES_WITHOUT_LANGUAGE = 'El campo {} aparece varias veces definido sin idioma'
    VALUE_IN_UNEXPECTED_LANGUAGE = 'El campo {} est\u00E1 en los idiomas ({}) que no son idiomas del cat\u00E1logo'
    VALUE_IN_UNEXPECTED_PORTAL_LANGUAGE = 'El campo {} est\u00E1 en los idiomas ({}) que no son idiomas soportados por el portal'
    EMPTY_VALUE_IN_LANGUAGE = 'El campo {} no tiene valor en los idiomas ({})'
    EMPTY_VALUE_NO_LANGUAGE = 'El campo {} sin idioma definido no tiene valor'
    VALUE_NOT_FOUND_IN_EXPECTED_LANGUAGE = 'El campo {} no est\u00E1 en los idiomas del cat\u00E1logo: {}'
    UNEXPECTED_EMPTY_VALUE = 'El campo {} aparece sin valor'
    OPTIONAL_EMPTY_VALUE = 'El campo no obligatorio {} se ignora porque tiene un valor vac\u00EDo'
    UNEXPECTED_VALUE = 'El campo {} no tiene un valor v\u00E1lido ({})'
    REQUIRED_FIELD_NOT_FOUND = 'No se ha encontrado el campo {}'
    REQUIRED_MULTIPLE_FIELD_NOT_FOUND = 'No se ha encontrado ning\u00FAn campo {}'
    WRONG_URI = 'El campo {} no contiene una URI v\u00E1lida ({})'
    WRONG_URL = 'El campo {} no contiene una URL v\u00E1lida ({})'
    UNEXPECTED_SPATIAL_COVERAGE_VALUES = 'El campo {} no contiene ninguna Autonom\u00EDa ni Provincia v\u00E1lida'
    REQUIRED_VALUE_NOT_FOUND = 'El campo {} no contiene el valor esperado ({})'
    REQUIRED_VALUE_NOT_FOUND_CASE_SENSITIVE = 'El campo {} tienen un valor ({}) que no contiene exactamente el valor esperado ({})'
    UNEXPECTED_THEME_TAXONOMY_NOT_IN_CALOG = 'El campo {} tiene un valor {} que no se corresponde a ninguna tem\u00E1tica del cat\u00E1logo'
    UNEXPECTED_THEME_VALUE = 'El campo {} no tiene ning\u00FAn valor que corresponda a la tem\u00E1tica obligatoria del cat\u00E1logo ({})'
    VALUE_NO_CASE_SENSITIVE = 'El campo {} tiene valores que no coinciden exactamente con las uris especificadas en la norma: ({})'
    FORMAT_NO_CASE_SENSITIVE = 'El campo {} tiene un valor que no coincide exactamente con los aceptados: ({})'
    REQUIRED_LITERAL_OBJECTS = 'El campo {} no es un literal. El posible que el campo no tenga valor o tenga un atributo lang incorrecto'
    UNEXPECTED_KEYWORD_FORMAT = 'El campo {} tiene un valor {}. Debe estar compuesto por caracteres alfanuméricos o alguno de los símbolos siguientes para ser válido: - _ Ç ç L·L l·l '' & .'
    RECEIVED_VALUE = 'El campo {} tiene valor no esperado: {}'
    UNEXPECTED_VALUE = 'El campo {} tiene un valor no v\u00E1lido ({})'
    UNEXPECTED_FIELD_ERROR = 'El campo {} tiene un error {}: {}'
    UNEXPECTED_PUBLISHER = 'El campo {} tiene un valor {} que no corresponde a ninguna organizaci\u00F3n del sistema'
    

    # ERROR MESSAGE THAT NO CONTAIN FIELD_NAME
    FIELD_PLUS_MESSAGE = 'El campo {} {}'
    UNEXPECTED_COMPLETE_DEFINITION = 'no est\u00E1 bien definido. {}: {}'
    UNEXPECTED_DEFINITION = 'no est\u00E1 bien definido'
    UNEXPECTED_MULTIPLE_OBJECTS = 'aparece definido varias veces'
    UNEXPECTED_MULTIPLE_SUBOBJECTS = 'tiene varios nodos {}'
    UNEXPECTED_MULTIPLE_SUB_SUBOBJECTS = 'tiene varios subnodos {} bajo el nodo {}'
    UNEXPECTED_DATE_DATATYPE = 'tiene un tipo de dato incorrecto {} para la fecha {}. Los tipos permitidos son: {} '
    UNEXPECTED_DATE_FORMAT = 'no tiene formato ISO-8601 {}'
    UNEXPECTED_DATE_VALUE = 'no tiene un valor v\u00E1lido {}. {}'
    UNEXPECTED_INTEGER_VALUE = 'no contiene un valor convertible a n\u00FAmero entero ({})'
    UNEXPECTED_INCOMPLETE_VALUE = 'aparece sin valor'

    EXPORT_AVAILABLE_RESOURCE_FORMATS = 'export_available_resource_formats'
    EXPORT_AVAILABLE_PUBLISHERS = 'export_available_publishers'
    EXPORT_AVAILABLE_THEMES = 'export_available_themes'

    CATALOG_ERROR_SUMMARY = 'Resumen: {} warning(s) y {} error(es) se ha(n) generado en la validaci\u00F3n del cat\u00E1logo. Ning\u00FAn dataset ha sido procesado'
    SUMMARY = '''Resumen: CAT\u00C1LOGO: {} warning(s) se ha(n) generado en la validaci\u00F3n del cat\u00E1logo.
                        DATASETS: Se han proceso {} datasets, de los cuales {} han producido error y no se han podido federar.
                        Se han generado {} error(es) y {} warning(s) diferentes en la validación de todos los datasets procesados.'''
    
    LOG_SUMMARY = '''ERROR/WARNING SUMMARY IN GATHER STAGE:
                        \n\tcatalog warnings={},
                        \n\ttotal dataset={},
                        \n\tdataset with errors={},
                        \n\ttotal errors={},
                        \n\ttotal warnings={}'''
