import os
import logging
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from ..config import config_manager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HypothesisEvaluation(BaseModel):
    is_plausible: bool = Field(..., description="Whether the hypothesis is biologically plausible.")
    reasoning: str = Field(..., description="Detailed biological reasoning for the evaluation.")
    novelty_score: int = Field(..., description="Score from 1-10 on how novel this hypothesis is.")
    suggested_experiment: str = Field(..., description="A brief suggestion for a wet-lab experiment to validate this.")

def find_missing_links(driver) -> list:
    """
    Queries Neo4j for implicit 'missing links' where A -> B and B -> C exist, but A -> C does not.
    """
    if not driver:
        logger.warning("No Neo4j driver provided.")
        return []

    query = """
    MATCH (a:Entity)-[r1]->(b:Entity)-[r2]->(c:Entity)
    WHERE a <> c AND NOT (a)-[]->(c)
    RETURN 
        a.name AS source, 
        r1.evidence AS evidence1,
        b.name AS intermediate,
        r2.evidence AS evidence2,
        c.name AS target
    LIMIT 10
    """
    
    results = []
    try:
        with driver.session() as session:
            records = session.run(query)
            for record in records:
                results.append({
                    "source": record["source"],
                    "intermediate": record["intermediate"],
                    "target": record["target"],
                    "evidence1": record["evidence1"],
                    "evidence2": record["evidence2"]
                })
        logger.info(f"Found {len(results)} potential missing links.")
        return results
    except Exception as e:
        logger.error(f"Error querying Neo4j for missing links: {e}")
        return []

def evaluate_hypothesis(missing_link: dict) -> HypothesisEvaluation:
    """
    Sends the missing link context to the LLM to evaluate biological plausibility.
    """
    config = config_manager.config
    api_key = config.gemini_api_key
    
    if not api_key:
        logger.error("GEMINI_API_KEY not found in config.")
        return HypothesisEvaluation(
            is_plausible=False, 
            reasoning="API key missing, evaluation failed.", 
            novelty_score=0, 
            suggested_experiment="N/A"
        )
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are an expert computational biologist evaluating a novel hypothesis.
    We have observed the following transitive relationship in literature:
    1. {missing_link['source']} relates to {missing_link['intermediate']}. Evidence: "{missing_link['evidence1']}"
    2. {missing_link['intermediate']} relates to {missing_link['target']}. Evidence: "{missing_link['evidence2']}"
    
    However, there is no direct known relationship between {missing_link['source']} and {missing_link['target']} in our database.
    
    Evaluate the plausibility of a direct or meaningful biological interaction between {missing_link['source']} and {missing_link['target']}.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=HypothesisEvaluation,
                temperature=0.2,
            ),
        )
        return HypothesisEvaluation.model_validate_json(response.text)
    except Exception as e:
        logger.error(f"LLM Evaluation failed: {e}")
        return HypothesisEvaluation(
            is_plausible=False, 
            reasoning=f"Error: {e}", 
            novelty_score=0, 
            suggested_experiment="N/A"
        )

def generate_markdown_report(missing_link: dict, eval_result: HypothesisEvaluation, output_path: str):
    """
    Generates a Markdown report for a successfully evaluated hypothesis.
    """
    md_content = f"""# Novel Biological Hypothesis

## Hypothesis
There is a meaningful biological relationship between **{missing_link['source']}** and **{missing_link['target']}**.

## Background (Knowledge Graph Evidence)
- **{missing_link['source']}** -> **{missing_link['intermediate']}**: "{missing_link['evidence1']}"
- **{missing_link['intermediate']}** -> **{missing_link['target']}**: "{missing_link['evidence2']}"

## LLM Evaluation
- **Plausible:** {'Yes' if eval_result.is_plausible else 'No'}
- **Novelty Score:** {eval_result.novelty_score}/10

### Biological Reasoning
{eval_result.reasoning}

### Suggested Experiment
{eval_result.suggested_experiment}
"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(md_content)
    logger.info(f"Generated hypothesis report at {output_path}")

if __name__ == "__main__":
    # Test execution
    dummy_link = {
        "source": "Drug X",
        "intermediate": "Protein Y",
        "target": "Disease Z",
        "evidence1": "Drug X strongly inhibits Protein Y.",
        "evidence2": "Protein Y upregulation is highly correlated with Disease Z severity."
    }
    
    if os.environ.get("GEMINI_API_KEY"):
        eval_result = evaluate_hypothesis(dummy_link)
        generate_markdown_report(dummy_link, eval_result, "output/hypothesis_test.md")
        print("Test complete. Check output/hypothesis_test.md")
    else:
        print("Please set GEMINI_API_KEY to run the LLM evaluation.")
