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

"""Raw dictionary formatter for SHACL validation results.

This module exposes each ``sh:ValidationResult`` as a plain dictionary built
from all predicate/object pairs present in the SHACL results graph. Unlike the
human-readable formatter, this output preserves the full result structure so
callers can decide later how to interpret or display it.
"""

from typing import Any, Dict, List, Optional, Set

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import RDF, SH

from .shacl_results_formatter import (
    _get_results_language,
    _is_rdf_list_node,
    serialize_rdf_term,
)
from ...decorators import log_debug


def _predicate_key(predicate) -> str:
    """Return stable dictionary key for one RDF predicate."""
    predicate_data = serialize_rdf_term(predicate) or {}
    return (
        predicate_data.get("local_name")
        or predicate_data.get("display")
        or predicate_data.get("value")
        or str(predicate)
    )


def _first_item(value):
    """Return first item when the serialized predicate value is a list."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _pick_message_display(messages) -> Optional[str]:
    """Pick preferred message display with ``es`` then ``en`` fallback."""
    if not isinstance(messages, list) or not messages:
        return None

    for language in ("es", "en"):
        for message in messages:
            if message.get("language") == language:
                return message.get("value")

    return messages[0].get("value")


def _get_source_shape_page_display(source_shapes) -> Optional[str]:
    """Return first available ``page`` display from serialized source shapes."""
    if not isinstance(source_shapes, list):
        return None

    for source_shape in source_shapes:
        page_values = source_shape.get("page")
        if not isinstance(page_values, list):
            continue
        for page in page_values:
            display = page.get("display")
            if display:
                return display
    return None


def _serialize_rdf_list(
    graph: Graph,
    node,
    _seen: Optional[Set[str]] = None,
) -> List[Any]:
    """Serialize RDF collection preserving item order."""
    items = []
    current = node
    seen = set()
    while current and current != RDF.nil and current not in seen:
        seen.add(current)
        first = graph.value(current, RDF.first)
        if first is not None:
            items.append(_serialize_result_value(graph, first, _seen=_seen))
        current = graph.value(current, RDF.rest)
    return items


def _serialize_result_node(
    graph: Graph,
    node,
    _seen: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Serialize one RDF node with all outgoing predicate/object pairs."""
    _seen = _seen or set()
    node_id = "{}:{}".format(type(node).__name__, str(node))
    node_data = {
        "_node": serialize_rdf_term(node),
    }

    if node_id in _seen:
        node_data["_cyclic_reference"] = True
        return node_data

    _seen.add(node_id)
    grouped: Dict[str, List[Any]] = {}
    for predicate, obj in graph.predicate_objects(node):
        key = _predicate_key(predicate)
        grouped.setdefault(key, []).append(
            _serialize_result_value(graph, obj, _seen=_seen)
        )

    node_data.update(grouped)
    return node_data


def _serialize_result_value(
    graph: Graph,
    value,
    _seen: Optional[Set[str]] = None,
):
    """Serialize one RDF value keeping nested result structure when present."""
    if value is None:
        return None

    if _is_rdf_list_node(graph, value):
        return _serialize_rdf_list(graph, value, _seen=_seen)

    if isinstance(value, Literal):
        return serialize_rdf_term(value)

    if isinstance(value, URIRef):
        if any(True for _ in graph.predicate_objects(value)):
            return _serialize_result_node(graph, value, _seen=_seen)
        return serialize_rdf_term(value)

    if isinstance(value, BNode):
        return _serialize_result_node(graph, value, _seen=_seen)

    return serialize_rdf_term(value)


def extract_shacl_validation_result_as_dict(
    results_graph: Graph,
    result_node,
) -> Dict[str, Any]:
    """Serialize one ``sh:ValidationResult`` node as raw dictionary."""
    return _serialize_result_node(results_graph, result_node)


def summarize_shacl_validation_result(result: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Build concise custom summary from one raw SHACL result dictionary."""
    result_severity = _first_item(result.get("resultSeverity")) or {}
    focus_node = _first_item(result.get("focusNode")) or {}
    result_path = _first_item(result.get("resultPath")) or {}
    result_value = _first_item(result.get("value")) or {}
    source_constraint = _first_item(result.get("sourceConstraintComponent")) or {}
    message_text = _pick_message_display(result.get("resultMessage"))

    message_lines = [
        message_text,
        "Nodo afectado: {}".format(focus_node.get("value")),
        "Propiedad: {} ({})".format(result_path.get("display"), result_path.get("value")),
    ]
    if result_value.get("value") is not None:
        message_lines.append("Valor: {}".format(result_value.get("value")))

    return {
        "severity": result_severity.get("value"),
        "message": "\n".join(
            [line for line in message_lines if line is not None]
        ),
        "more_info_url": _get_source_shape_page_display(result.get("sourceShape")),
        "constraint": source_constraint.get("value"),
        "metadata_uri": result_path.get("value"),
        "resource_uri": focus_node.get("value")
    }


def summarize_shacl_validation_results(
    results_graph: Graph,
    data_graph: Graph,
    lang_preference: Optional[str] = None,
) -> List[Dict[str, Optional[str]]]:
    """Return summarized dictionaries for all SHACL validation results."""
    return [
        summarize_shacl_validation_result(result)
        for result in format_shacl_validation_results_as_dicts(
            results_graph,
            data_graph,
            lang_preference=lang_preference,
        )
    ]


@log_debug
def format_shacl_validation_results_as_dicts(
    results_graph: Graph,
    data_graph: Graph,
    lang_preference: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return all SHACL validation results as raw dictionaries.

    ``data_graph`` and ``lang_preference`` stay in the signature to mirror the
    text formatter entrypoint and ease call-site reuse. Raw serialization reads
    only from ``results_graph`` because it exposes the exact SHACL result data.
    """
    lang_preference = lang_preference or _get_results_language()
    del data_graph
    del lang_preference

    return [
        extract_shacl_validation_result_as_dict(results_graph, result)
        for result in results_graph.subjects(RDF.type, SH.ValidationResult)
    ]
