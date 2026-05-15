import pytest
import os
from unittest.mock import MagicMock, patch
from vitagraph.core.hypothesis import find_missing_links, evaluate_hypothesis, HypothesisEvaluation, generate_markdown_report

def test_find_missing_links():
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = mock_session
    
    # Mock Neo4j record
    mock_record = {
        "source": "A",
        "intermediate": "B",
        "target": "C",
        "evidence1": "A -> B",
        "evidence2": "B -> C"
    }
    mock_session.run.return_value = [mock_record]
    
    results = find_missing_links(mock_driver)
    
    assert len(results) == 1
    assert results[0]["source"] == "A"
    assert results[0]["target"] == "C"

@patch('vitagraph.core.hypothesis.genai.Client')
@patch.dict('os.environ', {'GEMINI_API_KEY': 'fake-key'})
def test_evaluate_hypothesis(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.text = '''
    {
        "is_plausible": true,
        "reasoning": "Because of biology.",
        "novelty_score": 8,
        "suggested_experiment": "Do a western blot."
    }
    '''
    mock_client.models.generate_content.return_value = mock_response
    
    dummy_link = {
        "source": "A",
        "intermediate": "B",
        "target": "C",
        "evidence1": "ev1",
        "evidence2": "ev2"
    }
    
    result = evaluate_hypothesis(dummy_link)
    
    assert result.is_plausible is True
    assert result.novelty_score == 8
    assert "biology" in result.reasoning

def test_generate_markdown_report(tmp_path):
    dummy_link = {
        "source": "A",
        "intermediate": "B",
        "target": "C",
        "evidence1": "ev1",
        "evidence2": "ev2"
    }
    eval_result = HypothesisEvaluation(
        is_plausible=True,
        reasoning="Because of biology.",
        novelty_score=8,
        suggested_experiment="Do a western blot."
    )
    
    out_file = tmp_path / "report.md"
    generate_markdown_report(dummy_link, eval_result, str(out_file))
    
    assert os.path.exists(out_file)
    content = out_file.read_text()
    assert "Novel Biological Hypothesis" in content
    assert "**Novelty Score:** 8" in content
    assert "Do a western blot." in content
