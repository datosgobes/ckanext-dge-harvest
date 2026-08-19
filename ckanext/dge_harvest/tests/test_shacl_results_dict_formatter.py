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

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import FOAF, RDF, SH

from ckanext.dge_harvest.harvesters.utils.shacl_results_dict_formatter import (
    format_shacl_validation_results_as_dicts,
    summarize_shacl_validation_results,
    summarize_shacl_validation_result,
)


def _build_rdf_list(graph, items):
    head = BNode()
    current = head
    for index, item in enumerate(items):
        graph.add((current, RDF.first, item))
        if index == len(items) - 1:
            graph.add((current, RDF.rest, RDF.nil))
        else:
            next_node = BNode()
            graph.add((current, RDF.rest, next_node))
            current = next_node
    return head


def test_format_shacl_validation_results_as_dicts_returns_full_result_structure():
    results_graph = Graph()
    data_graph = Graph()

    result = URIRef("http://example.test/result/1")
    detail = BNode()
    shape = BNode()
    alt_path = BNode()
    focus_node = URIRef("http://example.test/dataset/1")
    result_path = URIRef("http://purl.org/dc/terms/title")

    results_graph.add((result, RDF.type, SH.ValidationResult))
    results_graph.add((result, SH.resultSeverity, SH.Violation))
    results_graph.add((result, SH.focusNode, focus_node))
    results_graph.add((result, SH.resultPath, result_path))
    results_graph.add((result, SH.resultMessage, Literal("Falta título", lang="es")))
    results_graph.add((result, SH.sourceShape, shape))
    results_graph.add((result, SH.detail, detail))

    results_graph.add((shape, SH.name, Literal("Titulo obligatorio", lang="es")))
    results_graph.add((shape, SH.path, alt_path))
    results_graph.add(
        (alt_path, SH.alternativePath, _build_rdf_list(results_graph, [result_path]))
    )

    results_graph.add((detail, RDF.type, SH.ValidationResult))
    results_graph.add((detail, SH.resultSeverity, SH.Warning))
    results_graph.add((detail, SH.resultMessage, Literal("Detalle", lang="es")))

    structured = format_shacl_validation_results_as_dicts(
        results_graph,
        data_graph,
        lang_preference="es",
    )

    assert len(structured) == 2

    root = next(
        item
        for item in structured
        if item["focusNode"][0]["value"] == str(focus_node)
    )
    assert root["resultMessage"][0]["value"] == "Falta título"
    assert root["resultSeverity"][0]["local_name"] == "Violation"
    assert root["sourceShape"][0]["name"][0]["value"] == "Titulo obligatorio"
    assert root["sourceShape"][0]["path"][0]["alternativePath"][0][0]["value"] == str(
        result_path
    )
    assert root["detail"][0]["resultMessage"][0]["value"] == "Detalle"


def test_format_shacl_validation_results_as_dicts_keeps_each_validation_result():
    results_graph = Graph()
    data_graph = Graph()

    focus_node = URIRef("http://example.test/dataset/1")
    result_path = URIRef("http://purl.org/dc/terms/title")
    result_one = URIRef("http://example.test/result/1")
    result_two = URIRef("http://example.test/result/2")

    for result in (result_one, result_two):
        results_graph.add((result, RDF.type, SH.ValidationResult))
        results_graph.add((result, SH.resultSeverity, SH.Violation))
        results_graph.add((result, SH.focusNode, focus_node))
        results_graph.add((result, SH.resultPath, result_path))
        results_graph.add((result, SH.resultMessage, Literal("Falta título", lang="es")))

    structured = format_shacl_validation_results_as_dicts(
        results_graph,
        data_graph,
        lang_preference="es",
    )

    assert len(structured) == 2


def test_summarize_shacl_validation_result_returns_requested_fields():
    results_graph = Graph()
    data_graph = Graph()

    result = URIRef("http://example.test/result/1")
    shape = BNode()
    focus_node = URIRef("http://example.test/dataset/1")
    result_path = URIRef("http://purl.org/dc/terms/title")
    page = URIRef("https://example.test/help/title")

    results_graph.add((result, RDF.type, SH.ValidationResult))
    results_graph.add((result, SH.resultSeverity, SH.Violation))
    results_graph.add((result, SH.focusNode, focus_node))
    results_graph.add((result, SH.resultPath, result_path))
    results_graph.add((result, SH.value, Literal("titulo vacio", lang="es")))
    results_graph.add((result, SH.resultMessage, Literal("Missing title", lang="en")))
    results_graph.add((result, SH.resultMessage, Literal("Falta título", lang="es")))
    results_graph.add((result, SH.sourceConstraintComponent, SH.MinCountConstraintComponent))
    results_graph.add((result, SH.sourceShape, shape))
    results_graph.add((shape, FOAF.page, page))

    structured = format_shacl_validation_results_as_dicts(
        results_graph,
        data_graph,
        lang_preference="es",
    )

    summary = summarize_shacl_validation_result(structured[0])

    assert summary == {
        "severidad": "http://www.w3.org/ns/shacl#Violation",
        "mensaje": (
            '"Falta título"@es\n'
            "Nodo afectado: http://example.test/dataset/1\n"
            "Propiedad: http://purl.org/dc/terms/title\n"
            "Valor: titulo vacio"
        ),
        "ver_mas": "https://example.test/help/title",
        "constraint": "http://www.w3.org/ns/shacl#MinCountConstraintComponent",
    }


def test_summarize_shacl_validation_results_returns_summary_list():
    results_graph = Graph()
    data_graph = Graph()

    result = URIRef("http://example.test/result/1")
    focus_node = URIRef("http://example.test/dataset/1")
    result_path = URIRef("http://purl.org/dc/terms/title")

    results_graph.add((result, RDF.type, SH.ValidationResult))
    results_graph.add((result, SH.resultSeverity, SH.Warning))
    results_graph.add((result, SH.focusNode, focus_node))
    results_graph.add((result, SH.resultPath, result_path))
    results_graph.add((result, SH.resultMessage, Literal("Missing title", lang="en")))

    summaries = summarize_shacl_validation_results(
        results_graph,
        data_graph,
        lang_preference="es",
    )

    assert summaries == [
        {
            "severidad": "http://www.w3.org/ns/shacl#Warning",
            "mensaje": (
                '"Missing title"@en\n'
                "Nodo afectado: http://example.test/dataset/1\n"
                "Propiedad: http://purl.org/dc/terms/title"
            ),
            "ver_mas": None,
            "constraint": None,
        }
    ]
