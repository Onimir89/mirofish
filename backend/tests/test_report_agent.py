"""Tests for ReportAgent parsing and tool execution."""

import json

import networkx as nx

from app.services.report_agent import (
    ReportAgent,
    _graph_search,
    _graph_statistics,
)


def _small_graph() -> nx.DiGraph:
    """Build a small graph for testing."""
    G = nx.DiGraph()
    G.add_node('n1', name='Alice', type='Person', description='AI researcher')
    G.add_node('n2', name='OpenAI', type='Organization', description='AI lab')
    G.add_node('n3', name='GPT-4', type='Technology', description='Large language model')
    G.add_edge('n1', 'n2', relation='WORKS_FOR', fact='Alice works at OpenAI')
    G.add_edge('n2', 'n3', relation='DEVELOPED', fact='OpenAI developed GPT-4')
    return G


class TestParseToolCall:
    def test_basic_tool_call(self):
        response = 'Let me search. <tool_call>graph_search|AI</tool_call>'
        name, args = ReportAgent._parse_tool_call(response)
        assert name == 'graph_search'
        assert args == ['AI']

    def test_tool_call_no_args(self):
        response = '<tool_call>graph_statistics|</tool_call>'
        name, args = ReportAgent._parse_tool_call(response)
        assert name == 'graph_statistics'
        assert args == ['']

    def test_tool_call_multiple_args(self):
        response = '<tool_call>agent_interview|a1|What do you think?</tool_call>'
        name, args = ReportAgent._parse_tool_call(response)
        assert name == 'agent_interview'
        assert args == ['a1', 'What do you think?']

    def test_no_tool_call(self):
        response = 'Just a regular response with no tool calls.'
        name, args = ReportAgent._parse_tool_call(response)
        assert name == ''
        assert args == []

    def test_first_tool_call_extracted(self):
        response = (
            '<tool_call>graph_statistics|</tool_call> '
            '<tool_call>graph_search|test</tool_call>'
        )
        name, args = ReportAgent._parse_tool_call(response)
        assert name == 'graph_statistics'


class TestExtractFinalAnswer:
    def test_extracts_after_marker(self):
        response = 'Some thinking.\n\nFinal Answer:\nHere is the report.'
        result = ReportAgent._extract_final_answer(response)
        assert result == 'Here is the report.'

    def test_no_marker_returns_full_text(self):
        response = 'No marker here.'
        result = ReportAgent._extract_final_answer(response)
        assert result == 'No marker here.'

    def test_strips_whitespace(self):
        response = 'Final Answer:   \n\n  Content here.  '
        result = ReportAgent._extract_final_answer(response)
        assert result == 'Content here.'


class TestGraphSearch:
    def test_finds_entity_by_name(self):
        G = _small_graph()
        result = _graph_search(G, 'Alice')
        data = json.loads(result)
        assert len(data['entities']) >= 1
        assert data['entities'][0]['name'] == 'Alice'

    def test_finds_entity_by_description(self):
        G = _small_graph()
        result = _graph_search(G, 'researcher')
        data = json.loads(result)
        assert any(e['name'] == 'Alice' for e in data['entities'])

    def test_finds_edge_by_fact(self):
        G = _small_graph()
        result = _graph_search(G, 'developed')
        data = json.loads(result)
        assert len(data['edges']) >= 1

    def test_no_results_message(self):
        G = _small_graph()
        result = _graph_search(G, 'zzzznonexistent')
        assert 'No results found' in result

    def test_case_insensitive(self):
        G = _small_graph()
        result = _graph_search(G, 'alice')
        data = json.loads(result)
        assert len(data['entities']) >= 1


class TestGraphStatistics:
    def test_returns_valid_json(self):
        G = _small_graph()
        result = _graph_statistics(G)
        data = json.loads(result)
        assert data['node_count'] == 3
        assert data['edge_count'] == 2

    def test_entity_types_counted(self):
        G = _small_graph()
        data = json.loads(_graph_statistics(G))
        assert data['entity_types']['Person'] == 1
        assert data['entity_types']['Organization'] == 1

    def test_top_connected_present(self):
        G = _small_graph()
        data = json.loads(_graph_statistics(G))
        assert 'top_connected' in data
        assert len(data['top_connected']) > 0

    def test_empty_graph(self):
        G = nx.DiGraph()
        data = json.loads(_graph_statistics(G))
        assert data['node_count'] == 0
        assert data['edge_count'] == 0
