import os
import logging
from google import genai
from google.genai import types
from .schemas import ExtractionResult
from ..config import config_manager

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are an expert biological data curator extracting entities and relationships from scientific text.

## CANONICAL NAMING — MOST IMPORTANT RULE
Every entity name you return MUST be the canonical (standard) form. This is critical for graph
integrity — inconsistent naming creates duplicate nodes that break hypothesis discovery.

Rules by entity type:
- **Genes & Proteins (Target)**: Use the official HGNC gene symbol in ALL CAPS.
  CORRECT: MTOR, TP53, PRKAA1, SIRT1, FOXO3, IGF1R
  WRONG:   mTOR, p53, AMPKα1, Sirtuin-1, FoxO3a, IGF-1R
- **Compounds**: Use the most widely recognized common name (not brand name, not IUPAC).
  CORRECT: rapamycin, metformin, resveratrol, NAD+, spermidine
  WRONG:   sirolimus, Glucophage, 3,5,4'-trihydroxy-trans-stilbene, nicotinamide adenine dinucleotide
- **Pathways**: Use the canonical pathway name from KEGG or Reactome.
  CORRECT: mTORC1 signaling, AMPK signaling, PI3K-AKT signaling, autophagy
  WRONG:   mTOR pathway, AMP-kinase cascade, phosphatidylinositol pathway
- **Diseases**: Use the standard MeSH/ICD term.
  CORRECT: type 2 diabetes mellitus, Alzheimer disease, sarcopenia
  WRONG:   T2DM, AD, muscle wasting

## SYNONYMS — REQUIRED FIELD
You MUST populate synonyms with every alternative name, abbreviation, or alias the text uses
for each entity. Never leave synonyms empty if the paper uses multiple names for the same thing.
Example: canonical name "rapamycin", synonyms ["sirolimus", "AY-9944", "RAPA"]

## ENTITY TYPES
- Compound: small molecules, drugs, metabolites, supplements
- Target: genes, proteins, enzymes — always use HGNC gene symbol
- Pathway: signaling cascades, metabolic pathways, biological processes
- Disease: age-related pathologies, conditions, phenotypes

## RELATIONSHIP TYPES
- Upregulates: A increases expression or activity of B
- Downregulates: A decreases expression or activity of B
- InteractsWith: physical or functional interaction between A and B
- Inhibits: A blocks, suppresses, or reduces B
- Activates: A triggers, induces, or enhances B

For each relationship you MUST extract the exact verbatim sentence from the text as evidence.
Only extract relationships where both entities are clearly named in the text.
"""

def extract_relationships(text: str, paper_title: str = None, doi: str = None,
                          abstract: str = None, source_url: str = None) -> ExtractionResult:
    """
    Extracts biological entities and relationships from the provided text using the Gemini model.
    """
    config = config_manager.config
    api_key = config.gemini_api_key
    
    if not api_key:
        logger.error("GEMINI_API_KEY not found in config. Extraction failed.")
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
        
        result = ExtractionResult.model_validate_json(response.text)
        result.paper_title = paper_title
        result.doi = doi
        result.abstract = abstract
        result.source_url = source_url
        return result
        
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
