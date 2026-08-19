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

from ckanext.dge_harvest.harvesters.utils.shacl_results_formatter import (
    extract_shacl_validation_results,
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


def test_extract_shacl_validation_results_returns_rich_neutral_structure():
    results_graph = Graph()
    data_graph = Graph()

    result = URIRef("http://example.test/result/1")
    detail = BNode()
    shape = BNode()
    choice_shape = BNode()
    alt_one = BNode()
    alt_two = BNode()
    inverse_path = BNode()
    focus_node = URIRef("http://example.test/dataset/1")
    result_path = URIRef("http://purl.org/dc/terms/title")
    page = URIRef("https://example.test/help/title")

    results_graph.add((result, RDF.type, SH.ValidationResult))
    results_graph.add((result, SH.resultSeverity, SH.Violation))
    results_graph.add((result, SH.focusNode, focus_node))
    results_graph.add((result, SH.resultPath, result_path))
    results_graph.add((result, SH.resultMessage, Literal("Falta título", lang="es")))
    results_graph.add((result, SH.resultMessage, Literal("Missing title", lang="en")))
    results_graph.add((result, SH.sourceConstraintComponent, SH.MinCountConstraintComponent))
    results_graph.add((result, SH.sourceShape, shape))
    results_graph.add((result, SH.detail, detail))

    results_graph.add((shape, SH.name, Literal("Título obligatorio", lang="es")))
    results_graph.add((shape, SH.description, Literal("La propiedad debe existir", lang="es")))
    results_graph.add((shape, SH.message, Literal("Debe existir dct:title", lang="es")))
    results_graph.add((shape, FOAF.page, page))
    results_graph.add((shape, SH.path, result_path))
    results_graph.add((shape, SH.minCount, Literal(1)))

    results_graph.add((detail, RDF.type, SH.ValidationResult))
    results_graph.add((detail, SH.resultSeverity, SH.Warning))
    results_graph.add((detail, SH.resultMessage, Literal("Revisa el literal", lang="es")))

    results_graph.add((choice_shape, SH["or"], _build_rdf_list(results_graph, [alt_one, alt_two])))
    results_graph.add((alt_one, SH.path, URIRef("http://purl.org/dc/terms/license")))
    results_graph.add((alt_one, SH.minCount, Literal(1)))
    results_graph.add((alt_two, SH.path, URIRef("http://purl.org/dc/terms/rights")))
    results_graph.add((alt_two, SH.minCount, Literal(1)))

    results_graph.add((inverse_path, SH.inversePath, URIRef("http://www.w3.org/ns/dcat#servesDataset")))

    results_graph.add((shape, SH.property, choice_shape))
    results_graph.add((shape, SH.path, inverse_path))

    data_graph.add((focus_node, RDF.type, URIRef("http://www.w3.org/ns/dcat#Dataset")))

    structured = extract_shacl_validation_results(
        results_graph,
        data_graph,
        lang_preference="es",
    )

    assert len(structured) == 2

    root = next(item for item in structured if item["focus_node"] is not None)
    assert root["severity"]["level"] == "error"
    assert root["message_text"] == "Falta título"
    assert root["source_constraints"][0]["local_name"] == "MinCountConstraintComponent"
    assert root["source_shapes"][0]["name"] == "Título obligatorio"
    assert root["source_shapes"][0]["description"] == "La propiedad debe existir"
    assert root["source_shapes"][0]["message_text"] == "Debe existir dct:title"
    assert root["source_shapes"][0]["primary_more_info_url"] == str(page)
    assert root["more_info_urls"] == [str(page)]
    assert root["primary_more_info_url"] == str(page)
    assert root["source_shapes"][0]["constraint_features"] == ["minCount"]
    assert root["source_shapes"][0]["path"]["path_type"] == "inverse"
    assert root["source_shapes"][0]["path"]["item"]["term"]["local_name"] == "servesDataset"
    property_property = next(
        item
        for item in root["source_shapes"][0]["properties"]
        if item["predicate"]["local_name"] == "property"
    )
    property_shape = next(
        item["nested_shape"]
        for item in property_property["objects"]
        if "nested_shape" in item
    )
    assert property_shape["constraint_features"] == ["or"]
    assert property_shape["properties"][0]["objects"][0]["collection"][0]["nested_shape"]["path"]["term"]["local_name"] == "license"
    assert len(root["details"]) == 1
    assert root["details"][0]["severity"]["level"] == "warning"
    assert root["details"][0]["message_text"] == "Revisa el literal"
