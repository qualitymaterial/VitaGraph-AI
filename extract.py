import os
import logging
from google import genai
from google.genai import types
from schemas import ExtractionResult

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are an expert biological data curator. Your task is to extract biological entities and relationships from the provided scientific text.
Focus on entities relevant to longevity and aging research, such as:
- Compounds (e.g., small molecules, drugs)
- Targets (e.g., genes, proteins, enzymes)
- Pathways (e.g., signaling cascades)
- Diseases (e.g., age-related pathologies)

Extract relationships between these entities. Use standardized relationship types:
- Upregulates
- Downregulates
- InteractsWith
- Inhibits
- Activates

For each relationship, you MUST extract the exact verbatim sentence from the text as evidence.
"""

def extract_relationships(text: str) -> ExtractionResult:
    """
    Extracts biological entities and relationships from the provided text using the Gemini model.
    """
    # Assuming the API key is set in the environment variable GEMINI_API_KEY
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable not set. Cannot extract relationships.")
        return ExtractionResult(entities=[], relationships=[])
        
    client = genai.Client(api_key=api_key)
    
    logger.info("Sending text to LLM for extraction...")
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=ExtractionResult,
                temperature=0.0,
            ),
        )
        
        # Parse the JSON response back into our Pydantic model
        # The SDK returns the text as a JSON string matching the schema
        return ExtractionResult.model_validate_json(response.text)
        
    except Exception as e:
        logger.error(f"Error during LLM extraction: {e}")
        return ExtractionResult(entities=[], relationships=[])

if __name__ == "__main__":
    # Test execution
    sample_text = "Nitazoxanide Activates BMP9-ALK1-SMAD signaling cascade and improves HHT vascular pathology. We found that Nitazoxanide strongly inhibits TGF-beta signaling."
    
    # We only run this if GEMINI_API_KEY is available
    if os.environ.get("GEMINI_API_KEY"):
        print("Running test extraction...")
        result = extract_relationships(sample_text)
        print(f"Extracted {len(result.entities)} entities and {len(result.relationships)} relationships.")
        for r in result.relationships:
            print(f"{r.source_entity} --[{r.relationship_type}]--> {r.target_entity} (Confidence: {r.confidence})")
            print(f"  Evidence: {r.evidence}")
    else:
        print("Please set GEMINI_API_KEY to run the test extraction.")
