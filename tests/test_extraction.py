import pytest
from unittest.mock import patch, MagicMock
from vitagraph.core.schemas import ExtractionResult, Entity, Relationship
from vitagraph.core.extract import extract_relationships

@patch('vitagraph.core.extract.genai.Client')
@patch.dict('os.environ', {'GEMINI_API_KEY': 'fake-key'})
def test_extract_relationships_success(mock_client_class):
    # Setup mock
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    # Mock response text to simulate LLM returning JSON
    mock_response = MagicMock()
    mock_response.text = '''
    {
        "entities": [
            {"name": "Nitazoxanide", "entity_type": "Compound", "synonyms": []},
            {"name": "BMP9", "entity_type": "Target", "synonyms": []}
        ],
        "relationships": [
            {
                "source_entity": "Nitazoxanide",
                "target_entity": "BMP9",
                "relationship_type": "Activates",
                "evidence": "Nitazoxanide Activates BMP9-ALK1-SMAD signaling cascade",
                "confidence": 0.95
            }
        ]
    }
    '''
    mock_client.models.generate_content.return_value = mock_response
    
    result = extract_relationships("Nitazoxanide Activates BMP9.")
    
    assert isinstance(result, ExtractionResult)
    assert len(result.entities) == 2
    assert result.entities[0].name == "Nitazoxanide"
    assert len(result.relationships) == 1
    assert result.relationships[0].relationship_type == "Activates"

@patch.dict('os.environ', clear=True)
def test_extract_relationships_no_api_key():
    # It should return an empty ExtractionResult if no API key is set
    result = extract_relationships("Some text")
    assert len(result.entities) == 0
    assert len(result.relationships) == 0
