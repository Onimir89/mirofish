"""Tests for OntologyGenerator validation and helper methods."""

from app.services.ontology_generator import OntologyGenerator, RESERVED_NAMES


class TestToPascalCase:
    def test_simple_words(self):
        assert OntologyGenerator._to_pascal_case('hello world') == 'HelloWorld'

    def test_snake_case(self):
        assert OntologyGenerator._to_pascal_case('research_paper') == 'ResearchPaper'

    def test_already_pascal(self):
        assert OntologyGenerator._to_pascal_case('ResearchPaper') == 'Researchpaper'

    def test_kebab_case(self):
        assert OntologyGenerator._to_pascal_case('government-agency') == 'GovernmentAgency'

    def test_single_word(self):
        assert OntologyGenerator._to_pascal_case('person') == 'Person'

    def test_empty_string(self):
        assert OntologyGenerator._to_pascal_case('') == ''

    def test_with_numbers(self):
        result = OntologyGenerator._to_pascal_case('phase2_result')
        assert result == 'Phase2Result'


class TestToUpperSnake:
    def test_camel_case(self):
        assert OntologyGenerator._to_upper_snake('worksFor') == 'WORKS_FOR'

    def test_pascal_case(self):
        assert OntologyGenerator._to_upper_snake('PublishedBy') == 'PUBLISHED_BY'

    def test_already_upper_snake(self):
        assert OntologyGenerator._to_upper_snake('WORKS_FOR') == 'WORKS_FOR'

    def test_spaces(self):
        assert OntologyGenerator._to_upper_snake('related to') == 'RELATED_TO'

    def test_multiple_separators(self):
        result = OntologyGenerator._to_upper_snake('foo--bar__baz')
        assert result == 'FOO_BAR_BAZ'


class TestRenameReserved:
    def test_reserved_names_get_suffix(self):
        for name in RESERVED_NAMES:
            result = OntologyGenerator._rename_reserved(name)
            assert result == f'{name}Entity'

    def test_non_reserved_unchanged(self):
        assert OntologyGenerator._rename_reserved('Person') == 'Person'
        assert OntologyGenerator._rename_reserved('Organization') == 'Organization'


class TestValidateOntology:
    def _gen(self):
        return OntologyGenerator(llm_client=None)

    def test_enforces_exactly_10_entity_types(self):
        gen = self._gen()
        # Provide 12 entity types — should truncate to 10
        entities = [{'name': f'Type{i}', 'description': f'desc {i}'} for i in range(12)]
        ontology = {'entity_types': entities, 'edge_types': []}
        result = gen._validate_ontology(ontology)
        assert len(result['entity_types']) == 10

    def test_pads_to_10_with_fallbacks(self):
        gen = self._gen()
        entities = [{'name': 'CustomType', 'description': 'test'}]
        ontology = {'entity_types': entities, 'edge_types': []}
        result = gen._validate_ontology(ontology)
        assert len(result['entity_types']) == 10
        # Person and Organization must be present
        names = {e['name'] for e in result['entity_types']}
        assert 'Person' in names
        assert 'Organization' in names

    def test_deduplicates_entity_names(self):
        gen = self._gen()
        entities = [
            {'name': 'Person', 'description': 'first'},
            {'name': 'Person', 'description': 'duplicate'},
            {'name': 'Org', 'description': 'org'},
        ]
        ontology = {'entity_types': entities, 'edge_types': []}
        result = gen._validate_ontology(ontology)
        person_entries = [e for e in result['entity_types'] if e['name'] == 'Person']
        assert len(person_entries) == 1

    def test_reserved_entity_name_renamed(self):
        gen = self._gen()
        entities = [{'name': 'Name', 'description': 'collides with reserved'}]
        ontology = {'entity_types': entities, 'edge_types': []}
        result = gen._validate_ontology(ontology)
        names = {e['name'] for e in result['entity_types']}
        assert 'Name' not in names
        assert 'NameEntity' in names

    def test_edge_types_dedup_and_cap(self):
        gen = self._gen()
        entities = [{'name': f'T{i}', 'description': ''} for i in range(10)]
        edges = [{'name': f'REL_{i}', 'description': '', 'source_type': 'T0', 'target_type': 'T1'}
                 for i in range(15)]
        # Add a duplicate
        edges.append({'name': 'REL_0', 'description': 'dup', 'source_type': 'T0', 'target_type': 'T1'})
        ontology = {'entity_types': entities, 'edge_types': edges}
        result = gen._validate_ontology(ontology)
        assert len(result['edge_types']) <= 10

    def test_empty_ontology_gets_padded(self):
        gen = self._gen()
        result = gen._validate_ontology({'entity_types': [], 'edge_types': []})
        assert len(result['entity_types']) == 10
        assert len(result['edge_types']) == 0

    def test_person_organization_always_present(self):
        gen = self._gen()
        # 10 custom types, none are Person/Organization
        entities = [{'name': f'Custom{i}', 'description': ''} for i in range(10)]
        ontology = {'entity_types': entities, 'edge_types': []}
        result = gen._validate_ontology(ontology)
        names = {e['name'] for e in result['entity_types']}
        assert 'Person' in names
        assert 'Organization' in names
