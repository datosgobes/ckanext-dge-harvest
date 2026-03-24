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
from rdflib.namespace import Namespace, RDF, SH
from typing import List, Tuple, Set, Optional
from ...decorators import log_debug
from ...constants.dcat_ap_es_constants import NAMESPACES

log = logging.getLogger(__name__)

"""
Module to build human-readable or serialized outputs from SHACL results obtained with pySHACL.
Does not perform validation, only formats the results graph.
"""
USE_PREFIX = None
MAX_DEPTH = 3
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


def format_validation_result_text(graph: Graph, data_graph:Graph, result_node, gt, indent:int=0, lang_preference:str="en"):
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
    focus_node = values["focus_node"]
    result_path = values["result_path"]
    if not (focus_node and result_path):
        return

    dcat_ap_es_page = config.get("ckanext.dge_harvest.dge_dcat_ap_es.url", None)
    dcat_ap_es_prefix = config.get("ckanext.dge_harvest.dge_dcat_ap_es.prefix", "")
    if not dcat_ap_es_page:
        return

    focus_types = list(data_graph.objects(focus_node, RDF.type))
    if not focus_types:
        return

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