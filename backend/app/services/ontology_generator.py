import re
from app.utils.llm_client import LLMClient

# Reserved attribute names that cannot be used as entity type names
RESERVED_NAMES = {'Uuid', 'Name', 'Summary', 'CreatedAt'}

# Generic fallback entity types used to pad to exactly 10
GENERIC_FALLBACKS = [
    {'name': 'Person', 'description': 'A human individual referenced in the documents'},
    {'name': 'Organization', 'description': 'A company, institution, agency, or formal group'},
    {'name': 'Location', 'description': 'A geographic place, city, region, or address'},
    {'name': 'Event', 'description': 'A notable occurrence, meeting, or milestone'},
    {'name': 'Document', 'description': 'A written record, report, publication, or file'},
    {'name': 'Concept', 'description': 'An abstract idea, theory, or domain term'},
    {'name': 'Technology', 'description': 'A tool, platform, protocol, or technical system'},
    {'name': 'Product', 'description': 'A good, service, or deliverable'},
    {'name': 'Regulation', 'description': 'A law, policy, standard, or compliance requirement'},
    {'name': 'Metric', 'description': 'A quantitative measure, KPI, or data point'},
]


class OntologyGenerator:
    """Generate ontology (entity types + edge types) from document text via LLM."""

    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client or LLMClient()

    def generate(self, texts: list[str], simulation_requirement: str = '') -> dict:
        """Generate ontology from document texts.

        Returns:
            {
                "entity_types": [{"name": "PascalCase", "description": "..."}],
                "edge_types": [{"name": "UPPER_SNAKE", "description": "...",
                               "source_type": "...", "target_type": "..."}]
            }
        """
        combined = '\n\n---\n\n'.join(texts)
        if len(combined) > 50000:
            combined = combined[:50000] + '\n\n[... truncated ...]'

        requirement_section = ''
        if simulation_requirement:
            requirement_section = f"""
## Simulation/Analysis Requirement
"{simulation_requirement}"
Tailor entity and edge types to support this requirement.
"""

        prompt = f"""You are an expert knowledge-graph ontology designer.

## Task
1. **Analyse the domain**: read the document text below and identify the primary domain (e.g., biomedical, legal, finance, technology, geopolitics).
2. **Design entity types**: produce EXACTLY 10 entity types.
   - 8 MUST be domain-specific, capturing the most important concepts in the documents.
   - 2 MUST be the universal fallbacks **Person** and **Organization** (always include them).
   - Each entity type needs a `name` (PascalCase, e.g. ResearchPaper, GovernmentAgency) and a rich `description` (1-2 sentences explaining what it represents and why it matters for this domain).
3. **Design edge types**: produce 6-10 relationship (edge) types.
   - Each edge type needs: `name` (UPPER_SNAKE_CASE, e.g. WORKS_FOR, PUBLISHED_BY), `description`, `source_type`, `target_type`.
   - `source_type` and `target_type` MUST reference entity type names from step 2.
   - Cover hierarchical, associative, and temporal relationships where applicable.
4. **Constraints**:
   - Entity names must NOT be any of: uuid, name, summary, created_at (these are reserved attributes).
   - No duplicate entity or edge names.
{requirement_section}
## Document Text
{combined}

## Output Format
Return ONLY valid JSON — no markdown fences, no commentary:
{{
  "entity_types": [
    {{"name": "PascalCase", "description": "1-2 sentence description"}}
  ],
  "edge_types": [
    {{"name": "UPPER_SNAKE_CASE", "description": "description", "source_type": "EntityType", "target_type": "EntityType"}}
  ]
}}"""

        result = self.llm.chat_json([{"role": "user", "content": prompt}])

        result = self._validate_ontology(result)
        return result

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_ontology(self, ontology: dict) -> dict:
        """Validate, normalize, deduplicate, and pad/truncate ontology."""
        raw_entities = ontology.get('entity_types', [])
        raw_edges = ontology.get('edge_types', [])

        # --- Entity types ---
        name_map: dict[str, str] = {}  # original -> normalized
        validated_entities: list[dict] = []
        seen: set[str] = set()

        for et in raw_entities:
            original = et.get('name', '')
            if not original:
                continue
            normalized = self._to_pascal_case(original)
            normalized = self._rename_reserved(normalized)
            if normalized in seen:
                continue
            seen.add(normalized)
            name_map[original] = normalized
            validated_entities.append({
                'name': normalized,
                'description': et.get('description', ''),
            })

        # Ensure Person and Organization are present
        for fb in GENERIC_FALLBACKS[:2]:  # Person, Organization
            if fb['name'] not in seen:
                seen.add(fb['name'])
                validated_entities.append(dict(fb))

        # Pad to 10 with generic fallbacks if needed
        for fb in GENERIC_FALLBACKS[2:]:
            if len(validated_entities) >= 10:
                break
            if fb['name'] not in seen:
                seen.add(fb['name'])
                validated_entities.append(dict(fb))

        # Truncate to exactly 10 (keep Person & Organization)
        if len(validated_entities) > 10:
            # Separate mandatory from rest
            mandatory = [e for e in validated_entities if e['name'] in ('Person', 'Organization')]
            rest = [e for e in validated_entities if e['name'] not in ('Person', 'Organization')]
            validated_entities = rest[:8] + mandatory

        valid_entity_names = {e['name'] for e in validated_entities}

        # --- Edge types ---
        validated_edges: list[dict] = []
        seen_edges: set[str] = set()

        for edge in raw_edges:
            raw_name = edge.get('name', '')
            if not raw_name:
                continue
            normalized_edge = self._to_upper_snake(raw_name)
            if normalized_edge in seen_edges:
                continue
            seen_edges.add(normalized_edge)

            # Resolve source/target through name_map, then validate
            src = self._resolve_entity_ref(edge.get('source_type', ''), name_map, valid_entity_names)
            tgt = self._resolve_entity_ref(edge.get('target_type', ''), name_map, valid_entity_names)

            validated_edges.append({
                'name': normalized_edge,
                'description': edge.get('description', ''),
                'source_type': src,
                'target_type': tgt,
            })

        # Cap edges at 10
        validated_edges = validated_edges[:10]

        return {
            'entity_types': validated_entities,
            'edge_types': validated_edges,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_entity_ref(self, raw: str, name_map: dict[str, str], valid: set[str]) -> str:
        """Resolve an entity reference using the name map, falling back to PascalCase conversion."""
        if raw in name_map:
            return name_map[raw]
        normalized = self._to_pascal_case(raw)
        normalized = self._rename_reserved(normalized)
        if normalized in valid:
            return normalized
        # Fallback: return the normalized form even if not in valid set
        return normalized

    @staticmethod
    def _rename_reserved(name: str) -> str:
        """Rename entity types that collide with reserved attribute names."""
        if name in RESERVED_NAMES:
            return name + 'Entity'
        return name

    @staticmethod
    def _to_pascal_case(name: str) -> str:
        """Convert string to PascalCase."""
        words = re.split(r'[^a-zA-Z0-9]', name)
        return ''.join(w.capitalize() for w in words if w)

    @staticmethod
    def _to_upper_snake(name: str) -> str:
        """Convert string to UPPER_SNAKE_CASE."""
        # Insert underscore before uppercase letters (for camelCase input)
        name = re.sub(r'([a-z])([A-Z])', r'\1_\2', name)
        # Replace non-alphanumeric with underscore
        name = re.sub(r'[^a-zA-Z0-9]', '_', name)
        # Collapse multiple underscores
        name = re.sub(r'_+', '_', name)
        return name.upper().strip('_')
