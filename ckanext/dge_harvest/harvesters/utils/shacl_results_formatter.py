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
import importlib
import os
import gettext
from ckantoolkit import config
from rdflib import Graph,Literal, BNode, URIRef
from rdflib.namespace import Namespace, RDF, RDFS, SH, FOAF
from typing import List, Tuple, Set, Optional, Dict, Any
from ...decorators import log_debug
from ...constants.dcat_ap_es_constants import NAMESPACES

log = logging.getLogger(__name__)

"""Utilities to extract and format SHACL validation results.

The module does not execute SHACL validation itself. It transforms the results
graph returned by pySHACL into either a human-readable text representation or
into a richer neutral structure that can later be adapted to other reporting
models.
"""
USE_PREFIX = None
MAX_DEPTH = 3
SHAPE_TEXT_PREDICATES = (SH.name, SH.description, RDFS.label)
SHAPE_CONSTRAINT_PREDICATES = {
    SH.minCount,
    SH.maxCount,
    SH.nodeKind,
    SH.datatype,
    SH.pattern,
    SH.hasValue,
    SH["class"],
    SH["in"],
    SH["or"],
    SH.uniqueLang,
    SH.closed,
    SH.languageIn,
}
# -------------------------------------------------------------------------
# Report language settings
# -------------------------------------------------------------------------
def _get_results_language():
    """
    Report language: ckanext.dge_harvest.language_report or ckan.locale_default (fallback).

    :returns: The language code for the report (e.g., 'en', 'es').
    :rtype: str
    """
    return config.get("ckanext.dge_harvest.language_report", config.get("ckan.locale_default", "en"))

def _get_report_gettext():
    """
    Returns (gt, lang), where gt is the local gettext function for the extension's domain,
    loaded for the 'lang' set in ckan.ini. Does not touch CKAN's global '_'.

    :returns: A tuple (gettext_function, language_code).
    :rtype: tuple[callable, str]
    """
    lang = _get_results_language()
    domain = "ckanext-dge_harvest"
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    localedir = os.path.join(base_dir, "i18n")
    trans = gettext.translation(domain=domain, localedir=localedir, languages=[lang], fallback=True)
    return trans.gettext, lang

# -------------------------------------------------------------------------
# Internal utilities
# -------------------------------------------------------------------------
def _get_use_preffix() -> bool: 
    return str(config.get("ckanext.dge_harvest.shacl_report.use_preffix", "")).strip().lower() in ("true")

def _format_uri(uri: URIRef, namespaces: dict[str, str], use_prefixes: bool) -> str:
    """Format an RDF URIRef using known prefixes, or return the full URI."""
    uri_str = str(uri)
    if not use_prefixes:
        return uri_str

    for prefix, ns in namespaces.items():
        if uri_str.startswith(ns):
            local = uri_str[len(ns):]
            return f"{prefix}:{local}"
    return uri_str

def _format_literal(lit: Literal) -> str:
    """Format a Literal including language tag or datatype if present."""
    if lit.language:
        return f'"{lit}"@{lit.language}'
    if lit.datatype:
        return f'"{lit}"^^<{lit.datatype}>'
    return f'"{lit}"'

def _format_bnode(bnode: BNode) -> str:
    """Format a blank node identifier."""
    return f"_:{bnode}"

def format_rdf_term(term, namespaces=None, use_prefixes=None):
    """
    Returns a human-readable string representation of an RDF term.
    It converts an RDFLib term (URIRef, Literal, or BNode) into a text.

    If ``use_prefixes`` is True, the URI is shortened using a known prefix
    from the provided ``namespaces`` mapping. Otherwise, the full URI is
    returned. Literals include language tags or datatypes when present,
    and blank nodes are represented by their identifiers.

    :param term: RDFLib term to format (URIRef, Literal, or BNode).
    :type term: rdflib.term.Identifier
    :param namespaces: Optional dictionary mapping prefixes to namespaces.
                       If None, uses the default ``NAMESPACES`` constant.
    :type namespaces: dict[str, str] | None
    :param use_prefixes: Whether to abbreviate URIs using prefixes.
                         If False, the full URI is returned.
    :type use_prefixes: bool
    :return: Human-readable string representation of the RDF term.
    :rtype: str

    :example:
        >>> from rdflib import URIRef, Literal
        >>> format_rdf_term(URIRef("http://www.w3.org/ns/dcat#Dataset"), use_prefixes=True)
        'dcat:Dataset'
        >>> format_rdf_term(URIRef("http://www.w3.org/ns/dcat#Dataset"), use_prefixes=False)
        'http://www.w3.org/ns/dcat#Dataset'
        >>> format_rdf_term(Literal("Message", lang="en"))
        '"Message"@en'
    """
    namespaces = namespaces or NAMESPACES
    namespaces['sh'] =  Namespace('http://www.w3.org/ns/shacl#')
    use_prefixes = use_prefixes or USE_PREFIX
    # --- Handle URIRefs (RDF resources) ---
    if isinstance(term, URIRef):
        return _format_uri(term, namespaces, use_prefixes)

    # --- Handle Literals (values, text, numbers, etc.) ---
    if isinstance(term, Literal):
        return _format_literal(term)

    # --- Handle Blank Nodes (anonymous resources) ---
    if isinstance(term, BNode):
        return _format_bnode(term)

    # --- Fallback: any other object type ---
    return str(term)

def extract_message(messages, lang_preference):
    """
    Returns the message in the preferred language, or the first available if not found.

    :param messages: A list of rdflib.Literal messages, possibly in different languages.
    :type messages: list[rdflib.Literal]
    :param lang_preference: The preferred language code (e.g., 'en', 'es').
    :type lang_preference: str
    :returns: The message string in the preferred language, or the first message if not found.
    :rtype: str or None
    """
    if not messages:
        return None
    for msg in messages:
        if isinstance(msg, Literal) and msg.language == lang_preference:
            return str(msg)
    return str(messages[0])

def severity_label(severity_iri, gt):
    """
    Returns a normalized textual label for SHACL severity, translated using the local gettext for the report.

    :param severity_iri: The IRI indicating the SHACL severity (e.g., Violation, Warning, Info).
    :type severity_iri: rdflib.term.Identifier or None
    
    :param gt: The gettext translation function for the report's language.
    :type gt: callable
    
    :returns: The translated severity label (e.g., '[SHACL ERROR]', '[SHACL WARNING]', '[SHACL INFO]').
    :rtype: str
    """
    if not severity_iri:
        return f"[{gt('SHACL INFO')}]"
    s = str(severity_iri)
    if s.endswith("Violation"):
        label = "SHACL ERROR"
    elif s.endswith("Warning"):
        label = "SHACL WARNING"
    elif s.endswith("Info"):
        label = "SHACL INFO"
    else: 
        return f"[SHACL {s.split('#')[-1].upper()}]"
    return f"[{gt(label)}]"


def get_severity_info(severity_iri):
    """Return a neutral severity structure from one SHACL severity term."""
    if not severity_iri:
        return {
            "iri": None,
            "name": "Info",
            "level": "info",
        }

    severity_text = str(severity_iri)
    severity_name = severity_text.split("#")[-1]
    level = "info"
    if severity_name == "Violation":
        level = "error"
    elif severity_name == "Warning":
        level = "warning"

    return {
        "iri": severity_text,
        "name": severity_name,
        "level": level,
    }

def get_metadata_or_class(uri_ref: str) -> Tuple[str, str]:
    """
    Extracts the namespace, namespace prefix, and the local name
    (metadata/class name) from a given URI.

    It splits the URI on the last '#' or '/' character.

    :param uri_ref: Full URI string.
    :type uri_ref: str
    :returns: A tuple with (namespace_prefix, metadata_name)
    :rtype: Tuple[str | None, str]

    :example:
        >>> get_metadata_or_class("http://www.w3.org/ns/dcat#Dataset")
        ('dcat', 'Dataset')
        >>> get_metadata_or_class("https://catalog.es/dataset/distribution/hvd")
        (None, 'hvd')
    """
    if not uri_ref:
        return None, '', ''

    # Split by the last '#' or '/', whichever appears later
    parts = uri_ref.rsplit('#', 1) if '#' in uri_ref else uri_ref.rsplit('/', 1)
    namespace = parts[0] + ('#' if '#' in uri_ref else '/')
    metadata_name = parts[1] if len(parts) > 1 else ''

    # Get the namespace prefix if registered
    namespace_prefix = next((k for k, v in NAMESPACES.items() if v == namespace), None)
    return namespace_prefix, metadata_name


def serialize_rdf_term(term, namespaces=None, use_prefixes=None) -> Optional[Dict[str, Any]]:
    """Serialize one RDF term into a neutral dictionary structure."""
    if term is None:
        return None

    namespaces = namespaces or NAMESPACES
    display = format_rdf_term(term, namespaces=namespaces, use_prefixes=use_prefixes)

    if isinstance(term, URIRef):
        namespace_prefix, local_name = get_metadata_or_class(str(term))
        return {
            "term_type": "uri",
            "value": str(term),
            "display": display,
            "namespace_prefix": namespace_prefix,
            "local_name": local_name,
        }

    if isinstance(term, Literal):
        return {
            "term_type": "literal",
            "value": str(term),
            "display": display,
            "language": term.language,
            "datatype": str(term.datatype) if term.datatype else None,
        }

    if isinstance(term, BNode):
        return {
            "term_type": "bnode",
            "value": str(term),
            "display": display,
        }

    return {
        "term_type": "text",
        "value": str(term),
        "display": display,
    }


def _is_rdf_list_node(graph: Graph, node) -> bool:
    """Return whether ``node`` is the head of an RDF collection."""
    return isinstance(node, BNode) and (
        (node, RDF.first, None) in graph or (node, RDF.rest, None) in graph
    )


def _serialize_rdf_collection(graph: Graph, node) -> List[Dict[str, Any]]:
    """Serialize an RDF collection into a plain Python list structure."""
    items = []
    current = node
    seen = set()
    while current and current != RDF.nil and current not in seen:
        seen.add(current)
        first = graph.value(current, RDF.first)
        if first is not None:
            items.append(_serialize_object_structure(graph, first, max_depth=0))
        current = graph.value(current, RDF.rest)
    return items


def _serialize_shacl_path(graph: Graph, path_node) -> Optional[Dict[str, Any]]:
    """Serialize simple and compound SHACL paths into a neutral structure."""
    if path_node is None:
        return None
    if isinstance(path_node, URIRef):
        return {
            "path_type": "predicate",
            "term": serialize_rdf_term(path_node),
        }
    if _is_rdf_list_node(graph, path_node):
        return {
            "path_type": "sequence",
            "items": _serialize_rdf_collection(graph, path_node),
        }
    if isinstance(path_node, BNode):
        for predicate, path_type in (
            (SH.inversePath, "inverse"),
            (SH.alternativePath, "alternative"),
            (SH.zeroOrMorePath, "zero_or_more"),
            (SH.oneOrMorePath, "one_or_more"),
            (SH.zeroOrOnePath, "zero_or_one"),
        ):
            nested = graph.value(path_node, predicate)
            if nested is not None:
                if predicate == SH.alternativePath and _is_rdf_list_node(graph, nested):
                    return {
                        "path_type": path_type,
                        "items": _serialize_rdf_collection(graph, nested),
                    }
                return {
                    "path_type": path_type,
                    "item": _serialize_shacl_path(graph, nested),
                }
    return {
        "path_type": "term",
        "term": serialize_rdf_term(path_node),
    }


def _serialize_object_structure(
    graph: Graph,
    obj,
    max_depth: int,
    lang_preference: str = "en",
    _seen: Optional[Set] = None,
):
    """Serialize one object node, expanding lists and nested shapes when useful."""
    object_data = {
        "term": serialize_rdf_term(obj),
    }
    if _is_rdf_list_node(graph, obj):
        object_data["collection"] = _serialize_rdf_collection(graph, obj)
        return object_data
    if isinstance(obj, BNode) and max_depth > 0:
        object_data["nested_shape"] = extract_shape_structure(
            graph,
            obj,
            lang_preference=lang_preference,
            max_depth=max_depth - 1,
            _seen=_seen,
        )
    return object_data


def _extract_multilingual_text_values(objects, lang_preference: str):
    """Return raw multilingual values plus the preferred text selection."""
    messages = []
    literals = []
    for obj in objects:
        if not isinstance(obj, Literal):
            continue
        literals.append(obj)
        messages.append(
            {
                "value": str(obj),
                "language": obj.language,
                "datatype": str(obj.datatype) if obj.datatype else None,
            }
        )
    return messages, extract_message(literals, lang_preference)

# -------------------------------------------------------------------------
# Generic building block of shapes (sourceShape)
# -------------------------------------------------------------------------
def build_shape_block(g: Graph, shape_node, gt, indent: int = 0, lang_preference: str = "en",
    max_depth: int = 1, _seen: Optional[Set] = None) -> str:
    """
    Recursively dumps all RDF properties of the given SHACL shape node.

    The function iterates over all predicate-object pairs of ``shape_node``
    and builds a readable textual block with indentation. It handles
    multilingual literals (e.g. ``sh:message``) and performs limited recursion
    on blank nodes to avoid infinite loops.

    :param g: RDFLib graph containing the SHACL shape.
    :type g: rdflib.Graph
    :param shape_node: The shape node to inspect.
    :type shape_node: rdflib.term.Identifier
    :param gt: Local gettext function for translations.
    :type gt: callable
    :param indent: Current indentation level (in spaces).
    :type indent: int
    :param lang_preference: Preferred language for multilingual literals.
    :type lang_preference: str
    :param max_depth: Maximum recursion depth for blank nodes.
    :type max_depth: int
    :param _seen: Internal set to track visited blank nodes (prevents cycles).
    :type _seen: set | None
    :return: A formatted string representing all shape properties.
    :rtype: str
    """
    prefix = " " * indent
    lines: list[str] = []
    _seen = _seen or set()

    # Handle cyclic blank nodes
    if isinstance(shape_node, BNode) and shape_node in _seen:
        lines.append(f"{prefix}- (…{gt('cyclic reference detected')} {format_rdf_term(shape_node)}…)")
        return "\n".join(lines)

    if isinstance(shape_node, BNode):
        _seen.add(shape_node)

    # Group all predicate-object pairs by predicate
    grouped = _group_predicate_objects(g, shape_node)

    # Force sh:message to appear first
    ordered_predicates = sorted(grouped.keys(), key=lambda p: (p != SH.message, str(p)))

    for predicate in ordered_predicates:
        objects = grouped[predicate]
        p_str = format_rdf_term(predicate)

        #Check if the predicate corresponds to sh:message.
        if predicate == SH.message:
            line = _format_message_predicate(objects, g, p_str, prefix, lang_preference)
            if line:
                lines.append(line)
            continue

        # Process all other predicates normally
        lines.extend(_format_objects_for_predicate(
                g, predicate, objects, gt, prefix, lang_preference,
                max_depth, _seen, indent))
       
    return "\n".join(lines)

def _group_predicate_objects(g: Graph, node) -> dict:
    """Group all predicate-object pairs for a given node."""
    grouped: dict = {}
    for p, o in g.predicate_objects(node):
        grouped.setdefault(p, []).append(o)
    return grouped

def _format_message_predicate(objects, g, predicate_str, prefix, lang_preference):
    """
    Select and format the most suitable sh:message literal according to language preference.

    Language selection priority:
        1. Literal in the preferred language (`lang_preference`)
        2. Literal in English ('en') if preferred language is not English
        3. The first available literal
        4. None if no literals are available

    :param objects: List of literals for the predicate (usually sh:message).
    :type objects: list
    :param g: RDFLib graph (for formatting terms).
    :type g: rdflib.Graph
    :param predicate_str: String representation of the predicate (e.g. 'sh:message').
    :type predicate_str: str
    :param prefix: Indentation prefix for pretty-printing.
    :type prefix: str
    :param lang_preference: Preferred language (e.g. 'es', 'en').
    :type lang_preference: str
    :return: Formatted message line or None if no message found.
    :rtype: str | None
    """
    # Preferred language
    preferred = next(
        (o for o in objects if getattr(o, "language", None) == lang_preference),
        None
    )

    # Fallback to English if preferred language is not English
    fallback_en = None
    if not preferred and lang_preference.lower() != "en":
        fallback_en = next(
            (o for o in objects if getattr(o, "language", None) == "en"),
            None
        )

    # Default to first literal if no preferred or English message exists
    chosen = preferred or fallback_en or (objects[0] if objects else None)

    # Nothing found → return None
    if not chosen:
        return None

    return f"{prefix}- {predicate_str}: {format_rdf_term(chosen)}"

def _format_objects_for_predicate(
    g, predicate, objects, gt, prefix, lang_preference,  max_depth, _seen, indent):
    """Format all objects for a given predicate, including recursive blank nodes."""
    lines = []
    for obj in objects:
        o_str = format_rdf_term(obj)
        line = f"{prefix}- {format_rdf_term(predicate)}: {o_str}"
        lines.append(line)

        # Handle blank nodes with recursion
        if isinstance(obj, BNode) and max_depth > 0:
            nested = build_shape_block(
                g, obj, gt, indent=indent + 4, lang_preference=lang_preference,
                max_depth=max_depth - 1, _seen=_seen,
            )
            if nested:
                lines.append(nested)
    return lines


def extract_shape_structure(
    graph: Graph,
    shape_node,
    lang_preference: str = "en",
    max_depth: int = 1,
    _seen: Optional[Set] = None,
) -> Dict[str, Any]:
    """Extract a neutral recursive structure for one SHACL shape node."""
    _seen = _seen or set()

    shape_data = {
        "node": serialize_rdf_term(shape_node),
        "messages": [],
        "name": None,
        "label": None,
        "description": None,
        "severity": None,
        "path": None,
        "more_info_urls": [],
        "primary_more_info_url": None,
        "constraint_features": [],
        "properties": [],
    }

    if isinstance(shape_node, BNode):
        if shape_node in _seen:
            shape_data["cyclic_reference"] = True
            return shape_data
        _seen.add(shape_node)

    grouped = _group_predicate_objects(graph, shape_node)
    ordered_predicates = sorted(grouped.keys(), key=lambda p: (p != SH.message, str(p)))

    for predicate in ordered_predicates:
        predicate_data = {
            "predicate": serialize_rdf_term(predicate),
            "objects": [],
        }
        objects = grouped[predicate]
        if predicate in SHAPE_TEXT_PREDICATES:
            text_values, preferred_text = _extract_multilingual_text_values(
                objects,
                lang_preference,
            )
            field_name = (
                "name" if predicate == SH.name else
                "description" if predicate == SH.description else
                "label"
            )
            shape_data[field_name] = preferred_text
            predicate_data["text_values"] = text_values
        if predicate == SH.message:
            shape_data["messages"], shape_data["message_text"] = _extract_multilingual_text_values(
                objects,
                lang_preference,
            )
        if predicate == SH.severity:
            shape_data["severity"] = get_severity_info(objects[0]) if objects else None
        if predicate == SH.path and objects:
            shape_data["path"] = _serialize_shacl_path(graph, objects[0])
        if predicate in SHAPE_CONSTRAINT_PREDICATES:
            predicate_name = predicate_data["predicate"].get("local_name")
            if predicate_name and predicate_name not in shape_data["constraint_features"]:
                shape_data["constraint_features"].append(predicate_name)

        for obj in objects:
            object_data = _serialize_object_structure(
                graph,
                obj,
                max_depth=max_depth,
                lang_preference=lang_preference,
                _seen=_seen,
            )
            if predicate == FOAF.page and isinstance(obj, URIRef):
                shape_data["more_info_urls"].append(str(obj))
            predicate_data["objects"].append(object_data)
        shape_data["properties"].append(predicate_data)

    if shape_data["more_info_urls"]:
        shape_data["primary_more_info_url"] = shape_data["more_info_urls"][0]
    if "message_text" not in shape_data:
        shape_data["message_text"] = None
    return shape_data


def _build_dcat_ap_es_links(data_graph: Graph, values: dict) -> List[str]:
    """Build documentation URLs inferred from focus node type and result path."""
    focus_node = values["focus_node"]
    result_path = values["result_path"]
    if not (focus_node and result_path):
        return []

    dcat_ap_es_page = config.get("ckanext.dge_harvest.dge_dcat_ap_es.url", None)
    dcat_ap_es_prefix = config.get("ckanext.dge_harvest.dge_dcat_ap_es.prefix", "")
    if not dcat_ap_es_page:
        return []

    focus_types = list(data_graph.objects(focus_node, RDF.type))
    if not focus_types:
        return []

    url_list = []
    for focus_type in focus_types:
        class_prefix, class_name = get_metadata_or_class(focus_type)
        meta_prefix, meta_name = get_metadata_or_class(result_path)
        if all([class_prefix, class_name, meta_prefix, meta_name]):
            url = (
                f"{dcat_ap_es_page}#"
                f"{dcat_ap_es_prefix}-{class_prefix.lower()}_{class_name.lower()}"
                f"-{meta_prefix.lower()}_{meta_name.lower()}"
            )
            url_list.append(url)

    return url_list


def extract_validation_result_data(
    graph: Graph,
    data_graph: Graph,
    result_node,
    lang_preference: str = "en",
) -> Dict[str, Any]:
    """Extract one SHACL ``ValidationResult`` into a rich neutral structure."""
    values = _extract_result_values(graph, result_node)
    source_shapes = [
        extract_shape_structure(
            graph,
            shape,
            lang_preference=lang_preference,
            max_depth=MAX_DEPTH,
        )
        for shape in values["source_shapes"]
    ]

    details = [
        extract_validation_result_data(
            graph,
            data_graph,
            detail,
            lang_preference=lang_preference,
        )
        for detail in graph.objects(result_node, SH.detail)
    ]
    more_info_urls = _collect_more_info_urls(source_shapes)

    return {
        "result_node": serialize_rdf_term(result_node),
        "severity": get_severity_info(values["severity"]),
        "message_text": extract_message(values["result_messages"], lang_preference),
        "result_messages": [
            serialize_rdf_term(message) for message in values["result_messages"]
        ],
        "focus_node": serialize_rdf_term(values["focus_node"]),
        "result_path": serialize_rdf_term(values["result_path"]),
        "value": serialize_rdf_term(values["value"]),
        "source_constraints": [
            serialize_rdf_term(constraint)
            for constraint in values["source_constraints"]
        ],
        "source_shapes": source_shapes,
        "more_info_urls": more_info_urls,
        "primary_more_info_url": more_info_urls[0] if more_info_urls else None,
        "documentation_urls": _build_dcat_ap_es_links(data_graph, values),
        "details": details,
    }


def extract_shacl_validation_results(
    results_graph: Graph,
    data_graph: Graph,
    lang_preference: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Extract a rich neutral structure for all SHACL validation results."""
    lang_preference = lang_preference or _get_results_language()
    return [
        extract_validation_result_data(
            results_graph,
            data_graph,
            result,
            lang_preference=lang_preference,
        )
        for result in results_graph.subjects(RDF.type, SH.ValidationResult)
    ]


def _collect_more_info_urls(source_shapes: List[Dict[str, Any]]) -> List[str]:
    """Collect de-duplicated ``foaf:page`` URLs from extracted shape nodes."""
    urls = []
    for shape in source_shapes:
        for url in shape.get("more_info_urls", []):
            if url not in urls:
                urls.append(url)
        for predicate_data in shape.get("properties", []):
            for obj in predicate_data.get("objects", []):
                nested_shape = obj.get("nested_shape")
                if not nested_shape:
                    continue
                for url in _collect_more_info_urls([nested_shape]):
                    if url not in urls:
                        urls.append(url)
    return urls

# -------------------------------------------------------------------------
# Formateo principal (texto legible que usa siempre gt/lang del informe)
# -------------------------------------------------------------------------
def format_validation_result_text(graph: Graph, data_graph:Graph, result_node, gt, indent:int=0, lang_preference:str="es"):
    """
    Build a human-readable textual representation of a SHACL ValidationResult.

    This function recursively formats a ValidationResult and all its details,
    including focus nodes, properties, severity, and shape definitions.

    :param graph: The SHACL results graph returned by pySHACL.
    :type graph: rdflib.Graph
    :param data_graph: The validated data graph (used to resolve RDF types and metadata links).
    :type data_graph: rdflib.Graph
    :param result_node: The ValidationResult node to format.
    :type result_node: rdflib.term.Identifier
    :param gt: Local gettext function for translation.
    :type gt: callable
    :param indent: Current indentation level (in spaces).
    :type indent: int
    :param lang_preference: Preferred language code for messages (e.g., 'en' or 'es').
    :type lang_preference: str
    :return: Multiline formatted text of the validation result.
    :rtype: str
    """
    prefix = " " * indent
    lines: list[str] = []
    
    # Extract values from the result node
    values = _extract_result_values(graph, result_node)

    # Header with severity
    lines.append(f"{prefix}{severity_label(values['severity'], gt)}")

    # Main message
    _append_message_line(lines, prefix, gt, values["result_messages"], lang_preference)

    # Basic data fields
    _append_basic_fields(lines, prefix, gt, graph, values)

    # Associated shape definitions
    _append_shape_definitions(lines, prefix, gt, graph, values, lang_preference, indent)

    # Subresultados (sh:detail)
    for detail in graph.objects(result_node, SH.detail):
        lines.append(f"{prefix}  {gt('Detail')}:")
        lines.append(format_validation_result_text(graph, data_graph, detail, gt, indent + 4, lang_preference))

    # Only add DCAT-AP-ES links at root level
    if indent == 0:
        _append_dcat_ap_es_links(lines, prefix, gt, data_graph, values)
    return '\r\n'.join(lines)

def _extract_result_values(graph: Graph, result_node) -> dict:
    """Extract all key RDF properties of a ValidationResult node."""
    get_val = lambda p: graph.value(result_node, p)
    return {
        "focus_node": get_val(SH.focusNode),
        "result_path": get_val(SH.resultPath),
        "result_messages": list(graph.objects(result_node, SH.resultMessage)),
        "source_constraints": list(graph.objects(result_node, SH.sourceConstraintComponent)),
        "source_shapes": list(graph.objects(result_node, SH.sourceShape)),
        "severity": get_val(SH.resultSeverity),
        "value": get_val(SH.value),
    }

def _append_message_line(lines, prefix, gt, messages, lang_preference):
    """Append the main message (sh:resultMessage) respecting language preference."""
    msg = extract_message(messages, lang_preference)
    if msg:
        lines.append(f"{prefix}  {gt('Message')}: {msg}")

def _append_basic_fields(lines, prefix, gt, graph, values):
    """Append basic result fields such as focus node, property, value, and constraints."""
    if values["focus_node"]:
        lines.append(f"{prefix}  {gt('Focus Node')}: {format_rdf_term(values['focus_node'])}")
    if values["result_path"]:
        lines.append(f"{prefix}  {gt('Property')}: {format_rdf_term(values['result_path'])}")
    if values["value"]:
        lines.append(f"{prefix}  {gt('Value')}: {format_rdf_term(values['value'])}")
    for constraint in values["source_constraints"]:
        lines.append(f"{prefix}  {gt('Constraint')}: {format_rdf_term(constraint)}")

def _append_shape_definitions(lines, prefix, gt, graph, values, lang_preference, indent):
    """Append all shape definitions related to a ValidationResult."""
    source_shapes = values["source_shapes"]
    if not source_shapes:
        return
    for idx, shape in enumerate(source_shapes, start=1):
        # Append header
        lines.append(f"{prefix}  {gt('Shape Definition')}" + (f" #{idx}:" if len(source_shapes) > 1 else ":"))
        # max_depth controls how deep we recurse into blank nodes referenced by the shape
        shape_block = build_shape_block(graph, shape, gt, indent=indent + 4, lang_preference=lang_preference, max_depth=MAX_DEPTH,)
        if shape_block.strip():
            lines.append(shape_block)
        else:
            # If there are no local triples, show the IRI/blank node of the shape
            lines.append(f"{prefix}    - {gt('(no local properties)')}: {format_rdf_term(shape)}")

def _append_dcat_ap_es_links(lines, prefix, gt, data_graph, values):
    """Append DCAT-AP-ES metadata documentation URLs based on RDF types and result path."""
    url_list = _build_dcat_ap_es_links(data_graph, values)
    if url_list:
        lines.append(f"{prefix}  {gt('See more info at')}: {', '.join(url_list)}")


@log_debug
def format_shacl_validation_results(results_graph: Graph, data_graph: Graph) -> List[str]:
    """
    Returns a complete, human-readable text of SHACL validation results from the SHACL results graph.
    Duplicated messages are filtered so identical messages appear only once.

    :param results_graph: The rdflib.Graph returned by pySHACL.validate(), containing SHACL validation results.
    :type results_graph: rdflib.Graph
    :param data_graph: The original data graph that was validated.
    :type data_graph: rdflib.Graph
    :returns: A list of formatted strings, each representing a validation result.
    :rtype: List[str]
    """
    gt, lang = _get_report_gettext()  
    global USE_PREFIX
    USE_PREFIX = _get_use_preffix()  
    out = []
    seen: set[tuple[str, str]] = set()  # (message_text, focus_node) pairs
    for result in results_graph.subjects(RDF.type, SH.ValidationResult):
        text = format_validation_result_text(results_graph, data_graph, result, gt, lang_preference=lang)
        # Extract message + focus node for deduplication
        msg, focus = _extract_message_and_focus(result, results_graph, lang)
        key = (msg or "", focus or "")

        if key in seen:
            continue

        seen.add(key)
        out.append(text)

    return out

def _extract_message_and_focus(result_node, graph, lang_preference="en") -> Tuple[Optional[str], Optional[str]]:
    """
    Extract the message and focus node string for deduplication purposes.

    :returns: Tuple (message_text, focus_node_iri)
    """
    msgs = list(graph.objects(result_node, SH.resultMessage))
    focus = graph.value(result_node, SH.focusNode)
    msg = extract_message(msgs, lang_preference)
    return msg, str(focus) if focus else None