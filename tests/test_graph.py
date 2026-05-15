import pytest
from unittest.mock import MagicMock, patch
from vitagraph.core.schemas import ExtractionResult, Entity, Relationship
from vitagraph.core.graph import get_neo4j_driver, insert_extraction_result

@patch('vitagraph.core.graph.GraphDatabase.driver')
@patch.dict('os.environ', {'NEO4J_URI': 'bolt://fake:7687'})
def test_get_neo4j_driver_success(mock_driver):
    mock_instance = MagicMock()
    mock_driver.return_value = mock_instance
    
    driver = get_neo4j_driver()
    
    assert driver == mock_instance
    mock_instance.verify_connectivity.assert_called_once()

@patch('vitagraph.core.graph.GraphDatabase.driver')
def test_get_neo4j_driver_failure(mock_driver):
    mock_driver.side_effect = Exception("Connection refused")
    
    driver = get_neo4j_driver()
    
    assert driver is None

def test_insert_extraction_result():
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = mock_session
    
    dummy_result = ExtractionResult(
        entities=[
            Entity(name="Compound X", entity_type="Compound", synonyms=[])
        ],
        relationships=[
            Relationship(
                source_entity="Compound X",
                target_entity="Gene Y",
                relationship_type="Activates",
                evidence="Evidence text",
                confidence=0.9
            )
        ]
    )
    
    insert_extraction_result(mock_driver, dummy_result)
    
    # We expect session.run to be called for the relationship and the entity
    assert mock_session.run.call_count == 2
    
    # First call should be the relationship insertion
    rel_call_args, rel_call_kwargs = mock_session.run.call_args_list[0]
    assert "MERGE (source)-[r:ACTIVATES]->(target)" in rel_call_args[0]
    assert rel_call_args[1]["source_name"] == "Compound X"
    assert rel_call_args[1]["confidence"] == 0.9
    
    # Second call should be the entity type update
    ent_call_args, ent_call_kwargs = mock_session.run.call_args_list[1]
    assert "MERGE (e:Entity {name: $name})" in ent_call_args[0]
    assert ent_call_args[1]["name"] == "Compound X"
