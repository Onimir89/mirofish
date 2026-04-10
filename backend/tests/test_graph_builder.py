"""Tests for GraphBuilder node/edge/graph operations."""

import json
import os
import tempfile

import networkx as nx
import pytest

from app.services.graph_builder import GraphBuilder


@pytest.fixture
def builder():
    return GraphBuilder(llm_client=None)


@pytest.fixture
def graph():
    return nx.DiGraph()


class TestGetOrCreateNode:
    def test_creates_new_node(self, builder, graph):
        entity = {'name': 'Alice', 'type': 'Person', 'description': 'A researcher'}
        node_id = builder._get_or_create_node(graph, entity)
        assert node_id != ''
        assert graph.number_of_nodes() == 1
        assert graph.nodes[node_id]['name'] == 'Alice'
        assert graph.nodes[node_id]['type'] == 'Person'

    def test_dedup_by_name_case_insensitive(self, builder, graph):
        e1 = {'name': 'Alice', 'type': 'Person', 'description': 'First'}
        e2 = {'name': 'alice', 'type': 'Person', 'description': 'Second'}
        id1 = builder._get_or_create_node(graph, e1)
        id2 = builder._get_or_create_node(graph, e2)
        assert id1 == id2
        assert graph.number_of_nodes() == 1

    def test_merges_description_on_dedup(self, builder, graph):
        e1 = {'name': 'Alice', 'type': 'Person', 'description': 'A researcher'}
        e2 = {'name': 'Alice', 'type': 'Person', 'description': 'Works at MIT'}
        builder._get_or_create_node(graph, e1)
        builder._get_or_create_node(graph, e2)
        node_id = list(graph.nodes)[0]
        desc = graph.nodes[node_id]['description']
        assert 'A researcher' in desc
        assert 'Works at MIT' in desc

    def test_empty_name_returns_empty(self, builder, graph):
        entity = {'name': '', 'type': 'Person'}
        node_id = builder._get_or_create_node(graph, entity)
        assert node_id == ''
        assert graph.number_of_nodes() == 0

    def test_whitespace_name_returns_empty(self, builder, graph):
        entity = {'name': '   ', 'type': 'Person'}
        node_id = builder._get_or_create_node(graph, entity)
        assert node_id == ''
        assert graph.number_of_nodes() == 0


class TestAddEdge:
    def test_adds_edge_between_existing_nodes(self, builder, graph):
        builder._get_or_create_node(graph, {'name': 'Alice', 'type': 'Person'})
        builder._get_or_create_node(graph, {'name': 'Bob', 'type': 'Person'})
        builder._add_edge(graph, {
            'source': 'Alice', 'target': 'Bob',
            'relation': 'KNOWS', 'fact': 'They are colleagues',
        })
        assert graph.number_of_edges() == 1

    def test_no_edge_if_source_missing(self, builder, graph):
        builder._get_or_create_node(graph, {'name': 'Bob', 'type': 'Person'})
        builder._add_edge(graph, {
            'source': 'Unknown', 'target': 'Bob', 'relation': 'KNOWS',
        })
        assert graph.number_of_edges() == 0

    def test_no_edge_if_empty_names(self, builder, graph):
        builder._add_edge(graph, {'source': '', 'target': '', 'relation': 'KNOWS'})
        assert graph.number_of_edges() == 0

    def test_edge_stores_relation_and_fact(self, builder, graph):
        builder._get_or_create_node(graph, {'name': 'A', 'type': 'X'})
        builder._get_or_create_node(graph, {'name': 'B', 'type': 'X'})
        builder._add_edge(graph, {
            'source': 'A', 'target': 'B',
            'relation': 'WORKS_FOR', 'fact': 'Since 2020',
        })
        u, v = list(graph.edges)[0]
        data = graph.edges[u, v]
        assert data['relation'] == 'WORKS_FOR'
        assert data['fact'] == 'Since 2020'


class TestSaveLoadGraph:
    def test_save_and_load_roundtrip(self, builder):
        """Save a graph, load it back, and verify contents."""
        G = nx.DiGraph()
        builder._get_or_create_node(G, {'name': 'Node1', 'type': 'T1', 'description': 'd1'})
        builder._get_or_create_node(G, {'name': 'Node2', 'type': 'T2', 'description': 'd2'})
        builder._add_edge(G, {'source': 'Node1', 'target': 'Node2', 'relation': 'LINKED'})

        with tempfile.TemporaryDirectory() as tmpdir:
            import unittest.mock as mock
            with mock.patch('app.config.Config.DATA_DIR', tmpdir):
                builder._save_graph('test123', G)
                loaded = builder.load_graph('test123')

        assert loaded.number_of_nodes() == 2
        assert loaded.number_of_edges() == 1

    def test_load_nonexistent_raises(self, builder):
        with tempfile.TemporaryDirectory() as tmpdir:
            import unittest.mock as mock
            with mock.patch('app.config.Config.DATA_DIR', tmpdir):
                with pytest.raises(FileNotFoundError):
                    builder.load_graph('nonexistent')


class TestGetGraphInfo:
    def test_empty_graph(self, builder):
        G = nx.DiGraph()
        info = builder._get_graph_info(G)
        assert info['node_count'] == 0
        assert info['edge_count'] == 0
        assert info['entity_types'] == {}

    def test_counts_types(self, builder):
        G = nx.DiGraph()
        builder._get_or_create_node(G, {'name': 'A', 'type': 'Person'})
        builder._get_or_create_node(G, {'name': 'B', 'type': 'Person'})
        builder._get_or_create_node(G, {'name': 'C', 'type': 'Org'})
        info = builder._get_graph_info(G)
        assert info['node_count'] == 3
        assert info['entity_types']['Person'] == 2
        assert info['entity_types']['Org'] == 1
