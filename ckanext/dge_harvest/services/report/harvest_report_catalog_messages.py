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

"""Visible default messages for the harvest report catalog."""

DEFAULT_GENERIC_CONTACT_ERROR_SUFFIX = (
    "Si el problema persiste, contacta con el administrador."
)

DEFAULT_GENERIC_REPEAT_ERROR_SUFFIX = (
    "Vuelve a intentarlo más tarde."
)

def append_support_message(base_message):
    """Append the common support suffix to a visible message."""
    return "{} {}".format(append_repeat_task_message(base_message), DEFAULT_GENERIC_CONTACT_ERROR_SUFFIX)


def append_repeat_task_message(base_message):
    """Append the common support suffix to a visible message."""
    return "{} {}".format(base_message, DEFAULT_GENERIC_REPEAT_ERROR_SUFFIX)
    

# Common

DEFAULT_COMMON_ERROR_MESSAGE = (
    "El recurso federado no ha podido ser procesado."
)
DEFAULT_COMMON_WARN_MESSAGE = (
    "El recurso federado ha generado observaciones en su procesamiento."
)
DEFAULT_COMMON_INFO_MESSAGE = (
    "La validación del recurso ha generado información adicional en su procesamiento."
)
DEFAULT_COMMON_REASON_PORTAL_ORGANIZATION_DATA_MESSAGE = (
    "Datos de la organización reemplazados por la información disponible en datos.gob.es."
)
DEFAULT_COMMON_REASON_UNREFERENCED_DATASET_MESSAGE = (
    "Borrado dataset no referenciado en catálogo"
),
DEFAULT_COMMON_REASON_UNREFERENCED_DATASERVICE_MESSAGE = (
    "Borrado dataservice no referenciado en catálogo"
),
DEFAULT_COMMON_REASON_UNDESCRIBED_DATASET_MESSAGE = (
    "Borrado dataset no descrito"
),
DEFAULT_COMMON_REASON_UNDESCRIBED_DATASERVICE_MESSAGE = (
    "Borrado dataservice no descrito"
),
DEFAULT_COMMON_REASON_UNREFERENCED_DESCRIBED_DATASET_MESSAGE = (
    "Borrado dataset descrito no referenciado en catálogo"
),
DEFAULT_COMMON_REASON_UNREFERENCED_DESCRIBED_DATASERVICE_MESSAGE = (
    "Borrado dataservice descrito no referenciado en catálogo"
),
DEFAULT_COMMON_REASON_UNREFERENCED_NODE_MESSAGE = (
    "Borrado nodo no referenciado"
),
DEFAULT_COMMON_REASON_UNDESCRIBED_CATALOG_MESSAGE = (
    "Borrado catálogo no descrito"
),
DEFAULT_COMMON_REASON_CATALOG_RECORD_MESSAGE = (
    "Borrado CatalogRecord"
),
DEFAULT_COMMON_REASON_DATASET_REFERENCE_IN_MULTIPLE_CATALOGS_MESSAGE = (
    "Borrado dataset referenciado en múltiples catálogos"
),
DEFAULT_COMMON_REASON_DATASERVICE_REFERENCE_IN_MULTIPLE_CATALOGS_MESSAGE = (
    "Borrado dataservice referenciado en múltiples catálogos"
),
DEFAULT_COMMON_DELETED_RESOURCE_INFO_MESSAGE=(
    "Recuros eliminado porque no cumple especificaciones de validacion."
)

DEFAULT_COMMON_RDF_PARSER_ERROR_MESSAGE = (
    "El RDF no está bien formado y no puede procesarse."
)
DEFAULT_COMMON_FILE_NOT_FOUND_ERROR_MESSAGE = (
    "No se ha encontrado el fichero RDF indicado."
)
DEFAULT_COMMON_FILE_TOO_LARGE_ERROR_MESSAGE = (
    "El fichero RDF supera el tamaño máximo permitido."
)
DEFAULT_COMMON_HTTP_ERROR_MESSAGE = (
    "No se ha podido descargar el RDF por un error HTTP."
)
DEFAULT_COMMON_TIMEOUT_ERROR_MESSAGE = (
    "La descarga del RDF ha superado el tiempo máximo permitido."
)
DEFAULT_COMMON_GATHER_PARSER_ERROR_MESSAGE = (
    "No se ha podido interpretar el RDF descargado."
)
DEFAULT_COMMON_VALIDATION_ERROR_MESSAGE = (
    "La validación del RDF ha finalizado con errores."
)

DEFAULT_COMMON_WRONG_CATALOGS_ERROR_MESSAGE= (
    "La validación del RDF ha finalizado con errores en catálogos."
)

DEFAULT_COMMON_REASON_NON_CANONICAL_NAMESPACES_ERROR_MESSAGE= (
    "El catálogo tiene namespaces considerados no canónicos."
),
DEFAULT_COMMON_REASON_ROOT_CATALOG_URI_NOT_FOUND_ERROR_MESSAGE=(
    "No se ha encontrado un catálogo raíz en el RDF"
),

DEFAULT_COMMON_PARSER_ERROR_MESSAGE= (
    "La validación de una entidad del RDF ha finalizado con errores."
)
DEFAULT_COMMON_PARSER_WARN_MESSAGE= (
    "La validación de una entidad del RDF ha finalizado con avisos."
)
DEFAULT_COMMON_NO_VALID_DISTRIBUTION_IN_DASASET= (
    "El dataset no tiene distribuciones válidas."
)
DEFAULT_COMMON_FINISHED_JOB_INFO_MESSAGE=(
    "La tarea de federación ha sido marcada como finalizada antes de copletar su procesamiento completo."
)
DEFAULT_COMMON_ABORTED_JOB_INFO_MESSAGE=(
    "La tarea de federación ha sido abortada."
)
DEFAULT_COMMON_FILE_NEXT_TO_MAX_LARGE_WARN_MESSAGE = (
    "El fichero RDF tiene un tamaño ceracano a tamaño máximo permitido."
)

# SHACL
DEFAULT_SHACL_ERROR_MESSAGE = (
    "Se ha producido un error en la validación SHACL."
)
DEFAULT_SHACL_WARN_MESSAGE = (
    "Se ha producido un aviso en la validación SHACL."
)
DEFAULT_SHACL_INFO_MESSAGE = (
    "Se ha generado información durante la validación SHACL."
)
DEFAULT_SHACL_MIN_COUNT_MESSAGE =(
    "Falta una propiedad obligatoria requerida por la validación SHACL."
)
DEFAULT_SHACL_MAX_COUNT_MESSAGE =(
    "Se ha superado la cardinalidad máxima permitida por la validación SHACL."
)
DEFAULT_SHACL_DATATYPE_MESSAGE =(
    "El valor no tiene el tipo de dato esperado por la validación SHACL."
)
DEFAULT_SHACL_CLASS_MESSAGE =(
    "El recurso no pertenece a la clase RDF esperada por la validación SHACL."
)
DEFAULT_SHACL_NODE_KIND_MESSAGE =(
    "El valor no tiene el tipo de nodo esperado por la validación SHACL."
)
DEFAULT_SHACL_ALLOWED_VALUES_MESSAGE =(
    "El valor no pertenece al conjunto de valores permitidos por la validación SHACL."
)
DEFAULT_SHACL_PATTERN_MESSAGE =(
    "El valor no cumple el patrón o formato requerido por la validación SHACL."
)
DEFAULT_SHACL_MIN_LENGTH_MESSAGE =(
    "El valor no alcanza la longitud mínima requerida por la validación SHACL."
)
DEFAULT_SHACL_MIN_INCLUSIVE_MESSAGE =(
    "El valor es inferior al mínimo permitido por la validación SHACL."
)
DEFAULT_SHACL_UNIQUE_LANG_MESSAGE =(
    "Existen varios valores con el mismo idioma donde la validación SHACL exige idiomas únicos."
)
DEFAULT_SHACL_HAS_VALUE_MESSAGE =(
    "Falta un valor requerido por la validación SHACL."
)
DEFAULT_SHACL_CLOSED_MESSAGE =(
    "Existe una propiedad no permitida por la validación SHACL."
)
DEFAULT_SHACL_NODE_MESSAGE =(
    "El nodo no cumple una restricción de nodo definida en la validación SHACL."
)
DEFAULT_SHACL_PROPERTY_MESSAGE =(
    "El recurso no cumple una restricción de propiedad definida en la validación SHACL."
)
DEFAULT_SHACL_OR_MESSAGE =(
    "El recurso no cumple ninguna de las alternativas permitidas por la validación SHACL."
)
DEFAULT_SHACL_NOT_MESSAGE =(
    "El recurso cumple una condición prohibida por la validación SHACL."
)
DEFAULT_SHACL_XONE_MESSAGE =(
    "El recurso no cumple exactamente una de las alternativas exigidas por la validación SHACL."
)
DEFAULT_SHACL_QUALIFIED_MIN_COUNT_MESSAGE =(
    "No se alcanza la cardinalidad mínima cualificada exigida por la validación SHACL."
)
DEFAULT_SHACL_SPARQL_MESSAGE =(
    "El recurso incumple una restricción SPARQL definida en la validación SHACL."
)

# Vocabulary

DEFAULT_VOCABULARY_INVALID_VALUE_ERROR_MESSAGE = (
    "Se ha detectado un valor fuera del vocabulario controlado."
)

DEFAULT_VOCABULARY_ERROR_MESSAGE = (
    "Se ha registrado un error de vocabularios controlados."
)
DEFAULT_VOCABULARY_WARN_MESSAGE = (
    "Se ha registrado un aviso de vocabularios controlados."
)
DEFAULT_VOCABULARY_INFO_MESSAGE = (
    "Se ha registrado información de vocabularios controlados."
)



# Technical
DEFAULT_TECHNICAL_ERROR_MESSAGE = (
    "Se ha producido un error técnico al federar."
)
DEFAULT_TECHNICAL_WARN_MESSAGE = (
    "Se ha producido un aviso técnico un error técnico al federar."
)
DEFAULT_TECHNICAL_INFO_MESSAGE = (
    "Se ha producido información general técnica un error técnico al federar."
)
DEFAULT_TECHNICAL_SETUP_ERROR_MESSAGE = (
    "Se ha producido un error técnico en la configuración de la ejecución de la tarea de federación."
)
DEFAULT_TECHNICAL_PREPROCESSING_ERROR_MESSAGE = (
    "Se ha producido un error técnico durante el preprocesado del RDF."
)
DEFAULT_TECHNICAL_VALIDATION_ERROR_MESSAGE = (
    "Se ha producido un error técnico durante la validación del RDF."
)
DEFAULT_TECHNICAL_STORAGE_ERROR_MESSAGE = (
    "Se ha producido un error técnico durante el almacenamiento del fichero de la federación."
)
DEFAULT_TECHNICAL_IMPORT_ERROR_MESSAGE = (
    "Se ha producido un error técnico durante la importación de los recursos de la federación."
)

DEFAULT_RDFSTORE_ERROR_MESSAGE = (
    "Se ha producido un error técnico en el almacén RDF."
)
DEFAULT_RDFSTORE_CONNECTION_ERROR_MESSAGE = (
    "No se ha podido conectar con el almacén RDF."
)
DEFAULT_RDFSTORE_QUERY_ERROR_MESSAGE = (
    "Se ha producido un error al consultar el almacén RDF."
)
DEFAULT_RDFSTORE_INTERNAL_ERROR_MESSAGE = (
    "El almacén RDF ha devuelto un error interno."
)
DEFAULT_TECHNICAL_CONNECTION_ERROR_MESSAGE = (
    "Se ha producido un error de conexión durante la federación."
)
DEFAULT_TECHNICAL_HOOK_ERROR_MESSAGE = (
    "Se ha producido un error ejecutando una extensión del proceso de federación."
)

DEFAULT_REASON_EMPTY_OBJECT_CONTENT_MESSAGE = (
    "Contenido vacío del objeto al importar"
),
DEFAULT_REASON_WRONG_PARSE_LOAD_OBJECT_CONTENT_MESSAGE = (
    "Errores al parsear el contenido del objeto a importar"
),
DEFAULT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_THAT_SERVES_DATASET_MESSAGE = (
    "Dataservices relacionados con el dataset no econtrados"
),
DEFAULT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_ACCESSED_BY_DISTRIBUTION_MESSAGE = (
    "Dataservices relacionados con la distribución no econtrados"
),
DEFAULT_REASON_DELETED_DATASET_MESSAGE = (
    "Borrado dataset no válido"
)
DEFAULT_REASON_DELETED_DATASERVICE_MESSAGE = (
    "Borrado dataservice no válido"
)


# Fallback
DEFAULT_FALLBACK_SETUP_ERROR_MESSAGE = (
    "Se ha producido un error no controlado durante la configuración de la federación."
)
DEFAULT_FALLBACK_DOWNLOAD_ERROR_MESSAGE = (
    "Se ha producido un error no controlado durante la descarga del RDF."
)
DEFAULT_FALLBACK_PREPROCESSING_ERROR_MESSAGE = (
    "Se ha producido un error no controlado durante el preprocesado del RDF."
)
DEFAULT_FALLBACK_VALIDATION_ERROR_MESSAGE = (
    "Se ha producido un error no controlado durante la validación del RDF."
)
DEFAULT_FALLBACK_STORAGE_ERROR_MESSAGE = (
    "Se ha producido un error no controlado durante el almacenamiento de la federación."
)
DEFAULT_FALLBACK_IMPORT_ERROR_MESSAGE = (
    "Se ha producido un error no controlado durante la importación de la federación."
)
DEFAULT_FALLBACK_UNKNOWN_ERROR_MESSAGE = (
    "Se ha producido un error no controlado durante la federación."
)
