import networkx as nx
import json
import uuid
import os
from datetime import datetime
from app.utils.llm_client import LLMClient


ENTITY_EXTRACTION_PROMPT_TEMPLATE = """\
Extract entities and relationships from the following text.

Entity types allowed: {entity_types}
Relationship types allowed: {edge_types}

Text:
{chunk}

Return JSON:
{{
  "entities": [
    {{"name": "...", "type": "EntityType", "description": "brief description", "attributes": {{}}}}
  ],
  "relations": [
    {{"source": "entity_name", "relation": "RELATION_TYPE", "target": "entity_name", "fact": "description of relationship"}}
  ]
}}

Extract ALL entities and relationships mentioned. Be thorough."""


class GraphBuilder:
    """Build knowledge graphs from text chunks using LLM entity extraction."""

    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client or LLMClient()

    def build_graph(self, project_id: str, text_chunks: list[str],
                    ontology: dict, callback=None) -> tuple[str, dict]:
        """Build knowledge graph from text chunks using LLM entity extraction.

        Args:
            project_id: Project identifier
            text_chunks: List of text chunks to process
            ontology: Ontology with entity_types and edge_types
            callback: Progress callback function(progress=int)

        Returns:
            (graph_id, graph_info_dict)
        """
        graph_id = str(uuid.uuid4())[:8]
        G = nx.DiGraph()

        total = len(text_chunks)
        for i, chunk in enumerate(text_chunks):
            entities, relations = self._extract_from_chunk(chunk, ontology)

            for entity in entities:
                self._get_or_create_node(G, entity)

            for relation in relations:
                self._add_edge(G, relation)

            if callback:
                callback(progress=int((i + 1) / total * 100))

        self._save_graph(graph_id, G)
        return graph_id, self._get_graph_info(G)

    def _extract_from_chunk(self, chunk: str, ontology: dict) -> tuple[list, list]:
        """Use LLM to extract entities and relationships from a text chunk."""
        entity_types = [e['name'] for e in ontology.get('entity_types', [])]
        edge_types = [e['name'] for e in ontology.get('edge_types', [])]

        prompt = ENTITY_EXTRACTION_PROMPT_TEMPLATE.format(
            entity_types=', '.join(entity_types),
            edge_types=', '.join(edge_types),
            chunk=chunk,
        )

        result = self.llm.chat_json([{"role": "user", "content": prompt}])
        return result.get('entities', []), result.get('relations', [])

    def _get_or_create_node(self, G: nx.DiGraph, entity: dict) -> str:
        """Find existing node by name or create new one."""
        entity_name = entity.get('name', '').strip()
        if not entity_name:
            return ''

        # Check if node with same name exists (case-insensitive)
        for node_id, data in G.nodes(data=True):
            if data.get('name', '').lower() == entity_name.lower():
                # Merge descriptions
                if entity.get('description'):
                    existing = data.get('description', '')
                    if entity['description'] not in existing:
                        data['description'] = f"{existing} {entity['description']}".strip()
                return node_id

        node_id = str(uuid.uuid4())[:8]
        G.add_node(
            node_id,
            name=entity_name,
            type=entity.get('type', 'Entity'),
            description=entity.get('description', ''),
            attributes=entity.get('attributes', {}),
            created_at=datetime.now().isoformat(),
        )
        return node_id

    def _add_edge(self, G: nx.DiGraph, relation: dict):
        """Add edge between named entities."""
        source_name = relation.get('source', '').strip().lower()
        target_name = relation.get('target', '').strip().lower()

        if not source_name or not target_name:
            return

        source_id = None
        target_id = None

        for node_id, data in G.nodes(data=True):
            name_lower = data.get('name', '').lower()
            if name_lower == source_name:
                source_id = node_id
            if name_lower == target_name:
                target_id = node_id

        if source_id and target_id:
            G.add_edge(
                source_id, target_id,
                relation=relation.get('relation', 'RELATED_TO'),
                fact=relation.get('fact', ''),
                created_at=datetime.now().isoformat(),
            )

    def _save_graph(self, graph_id: str, G: nx.DiGraph):
        """Save graph as JSON."""
        from app.config import Config
        graph_dir = os.path.join(Config.DATA_DIR, 'graphs')
        os.makedirs(graph_dir, exist_ok=True)

        data = nx.node_link_data(G)
        path = os.path.join(graph_dir, f'{graph_id}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_graph(self, graph_id: str) -> nx.DiGraph:
        """Load graph from JSON."""
        from app.config import Config
        path = os.path.join(Config.DATA_DIR, 'graphs', f'{graph_id}.json')
        if not os.path.exists(path):
            raise FileNotFoundError(f"Graph {graph_id} not found")
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return nx.node_link_graph(data)

    def _get_graph_info(self, G: nx.DiGraph) -> dict:
        """Get graph statistics."""
        type_counts = {}
        for _, data in G.nodes(data=True):
            t = data.get('type', 'Unknown')
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            'node_count': G.number_of_nodes(),
            'edge_count': G.number_of_edges(),
            'entity_types': type_counts,
        }
