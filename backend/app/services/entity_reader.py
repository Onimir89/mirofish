import networkx as nx
from app.services.graph_builder import GraphBuilder


class EntityReader:
    """Read and query entities from a knowledge graph."""

    def __init__(self, graph_builder: GraphBuilder = None):
        self.graph_builder = graph_builder or GraphBuilder()

    def get_entities(self, graph_id: str, entity_type: str = None) -> list[dict]:
        """Get all entities from graph, optionally filtered by type.

        Args:
            graph_id: Graph identifier
            entity_type: Optional entity type filter

        Returns:
            List of entity dicts with id, name, type, description, attributes
        """
        G = self.graph_builder.load_graph(graph_id)
        entities = []

        for node_id, data in G.nodes(data=True):
            node_type = data.get('type', 'Unknown')
            if entity_type and node_type != entity_type:
                continue

            entity = {
                'id': node_id,
                'name': data.get('name', ''),
                'type': node_type,
                'description': data.get('description', ''),
                'attributes': data.get('attributes', {}),
            }

            # Add edge info
            entity['edges'] = self._get_node_edges(G, node_id)
            entity['neighbors'] = self._get_neighbors(G, node_id)

            entities.append(entity)

        return entities

    def get_entity(self, graph_id: str, entity_id: str) -> dict | None:
        """Get a single entity by ID with full edge and neighbor info."""
        G = self.graph_builder.load_graph(graph_id)

        if entity_id not in G.nodes:
            return None

        data = G.nodes[entity_id]
        entity = {
            'id': entity_id,
            'name': data.get('name', ''),
            'type': data.get('type', 'Unknown'),
            'description': data.get('description', ''),
            'attributes': data.get('attributes', {}),
            'edges': self._get_node_edges(G, entity_id),
            'neighbors': self._get_neighbors(G, entity_id),
        }
        return entity

    def get_graph_data(self, graph_id: str) -> dict:
        """Get full graph data for D3 visualization.

        Returns:
            {
                "nodes": [{"id": ..., "name": ..., "type": ..., ...}],
                "edges": [{"source": ..., "target": ..., "relation": ..., ...}]
            }
        """
        G = self.graph_builder.load_graph(graph_id)

        nodes = []
        for node_id, data in G.nodes(data=True):
            nodes.append({
                'id': node_id,
                'name': data.get('name', ''),
                'type': data.get('type', 'Unknown'),
                'description': data.get('description', ''),
            })

        edges = []
        for source, target, data in G.edges(data=True):
            edges.append({
                'source': source,
                'target': target,
                'relation': data.get('relation', 'RELATED_TO'),
                'fact': data.get('fact', ''),
            })

        return {'nodes': nodes, 'edges': edges}

    @staticmethod
    def _get_node_edges(G: nx.DiGraph, node_id: str) -> list[dict]:
        """Get all edges connected to a node."""
        edges = []

        # Outgoing edges
        for _, target, data in G.out_edges(node_id, data=True):
            target_data = G.nodes.get(target, {})
            edges.append({
                'direction': 'outgoing',
                'relation': data.get('relation', ''),
                'fact': data.get('fact', ''),
                'target_id': target,
                'target_name': target_data.get('name', ''),
            })

        # Incoming edges
        for source, _, data in G.in_edges(node_id, data=True):
            source_data = G.nodes.get(source, {})
            edges.append({
                'direction': 'incoming',
                'relation': data.get('relation', ''),
                'fact': data.get('fact', ''),
                'source_id': source,
                'source_name': source_data.get('name', ''),
            })

        return edges

    @staticmethod
    def _get_neighbors(G: nx.DiGraph, node_id: str) -> list[dict]:
        """Get all neighbor nodes."""
        neighbors = set()

        # Successors (outgoing)
        for n in G.successors(node_id):
            neighbors.add(n)

        # Predecessors (incoming)
        for n in G.predecessors(node_id):
            neighbors.add(n)

        result = []
        for n_id in neighbors:
            data = G.nodes.get(n_id, {})
            result.append({
                'id': n_id,
                'name': data.get('name', ''),
                'type': data.get('type', 'Unknown'),
            })

        return result
