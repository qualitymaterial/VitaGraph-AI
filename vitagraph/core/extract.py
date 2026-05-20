import os
import logging
from typing import List, Optional
from google import genai
from google.genai import types
from .schemas import ExtractionResult, Entity, Relationship
from ..config import config_manager

logger = logging.getLogger(__name__)

CHUNK_WORDS   = 8_000   # max words per Gemini call
CHUNK_OVERLAP =   500   # word overlap between adjacent chunks

SYSTEM_PROMPT = """
You are an expert biological data curator extracting entities and relationships from scientific text.

## CANONICAL NAMING — MOST IMPORTANT RULE
Every entity name you return MUST be the canonical (standard) form. This is critical for graph
integrity — inconsistent naming creates duplicate nodes that break hypothesis discovery.

Rules by entity type:
- **Genes & Proteins (Target)**: Use the official HGNC gene symbol in ALL CAPS.
  CORRECT: MTOR, TP53, PRKAA1, SIRT1, FOXO3, IGF1R, TERT, CDKN2A
  WRONG:   mTOR, p53, AMPKα1, Sirtuin-1, FoxO3a, IGF-1R, telomerase, p16
- **Compounds**: Use the most widely recognized common name (not brand name, not IUPAC).
  CORRECT: rapamycin, metformin, resveratrol, NAD+, spermidine, quercetin, NMN
  WRONG:   sirolimus, Glucophage, 3,5,4'-trihydroxy-trans-stilbene, nicotinamide mononucleotide
- **Pathways**: Use the canonical pathway name from KEGG or Reactome.
  CORRECT: mTORC1 signaling, AMPK signaling, PI3K-AKT signaling, autophagy, NF-κB signaling
  WRONG:   mTOR pathway, AMP-kinase cascade, phosphatidylinositol pathway
- **Diseases**: Use the standard MeSH/ICD term.
  CORRECT: type 2 diabetes mellitus, Alzheimer disease, sarcopenia, atherosclerosis
  WRONG:   T2DM, AD, muscle wasting, hardening of arteries
- **Biomarkers**: Use the standard clinical or research name.
  CORRECT: telomere length, p16INK4a expression, IGF-1 serum levels, DNA methylation age
  WRONG:   TL, p16, IGF1, epigenetic clock
- **Organisms**: Use the full Latin binomial.
  CORRECT: Caenorhabditis elegans, Mus musculus, Saccharomyces cerevisiae, Drosophila melanogaster
  WRONG:   C. elegans, mice, yeast, flies
- **Cell types**: Use the standard histological or immunological name.
  CORRECT: senescent fibroblast, hematopoietic stem cell, hepatocyte, cardiomyocyte
  WRONG:   old cell, HSC, liver cell, heart cell
- **Phenotypes**: Use a precise, measurable description.
  CORRECT: lifespan extension, reduced oxidative stress, improved insulin sensitivity
  WRONG:   lives longer, less damage, better metabolism

## SYNONYMS — REQUIRED FIELD
Populate synonyms with EVERY alternative name, abbreviation, or alias the text uses for each entity.
Example: canonical name "rapamycin", synonyms ["sirolimus", "RAPA", "AY-9944"]

## ENTITY TYPES
- Compound:   small molecules, drugs, metabolites, dietary supplements
- Target:     genes and proteins — always use HGNC gene symbol
- Pathway:    signaling cascades, metabolic pathways, biological processes
- Disease:    age-related pathologies, conditions, syndromes
- Biomarker:  measurable indicators of biological aging or disease state
- Organism:   model organisms used in longevity experiments
- CellType:   specific cell types or cellular states (e.g., senescent cells)
- Phenotype:  observable biological outcomes (e.g., lifespan extension, healthspan)

## RELATIONSHIP TYPES
- Upregulates:           A increases expression or activity of B
- Downregulates:         A decreases expression or activity of B
- InteractsWith:         physical or functional interaction between A and B
- Inhibits:              A blocks, suppresses, or reduces B
- Activates:             A triggers, induces, or enhances B
- RegulatesExpressionOf: A controls transcription or translation of B (gene regulation)
- AssociatedWith:        epidemiological or correlative association between A and B
- ExtendsLifespanOf:     A (compound/gene/intervention) extends lifespan of B (organism/cell)
- BiomarkerFor:          A is a diagnostic or prognostic biomarker for condition B

For each relationship you MUST extract the exact verbatim sentence from the text as evidence.
Only extract relationships where both entities are clearly named in the text.
"""


def _chunk_text(text: str) -> List[str]:
    """Splits text into overlapping word-based chunks for large documents."""
    words = text.split()
    if len(words) <= CHUNK_WORDS:
        return [text]

    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i : i + CHUNK_WORDS]
        chunks.append(" ".join(chunk_words))
        if i + CHUNK_WORDS >= len(words):
            break
        i += CHUNK_WORDS - CHUNK_OVERLAP

    logger.info(f"Split {len(words):,} words into {len(chunks)} chunks")
    return chunks


def _merge_results(chunk_results: List[ExtractionResult]) -> ExtractionResult:
    """
    Merges extraction results from multiple chunks.
    - Entities: deduplicates by name, combines synonyms
    - Relationships: deduplicates by (source, type, target), keeps highest confidence
    """
    seen_entities: dict[str, Entity] = {}
    seen_rels: dict[tuple, Relationship] = {}

    for result in chunk_results:
        for entity in result.entities:
            if entity.name not in seen_entities:
                seen_entities[entity.name] = entity
            else:
                existing = seen_entities[entity.name]
                merged_synonyms = list(set(existing.synonyms + entity.synonyms))
                seen_entities[entity.name] = existing.model_copy(
                    update={"synonyms": merged_synonyms}
                )

        for rel in result.relationships:
            key = (rel.source_entity, rel.relationship_type, rel.target_entity)
            if key not in seen_rels or rel.confidence > seen_rels[key].confidence:
                seen_rels[key] = rel

    return ExtractionResult(
        entities=list(seen_entities.values()),
        relationships=list(seen_rels.values()),
    )


def _extract_chunk(client, text: str) -> ExtractionResult:
    """Runs a single Gemini extraction call on one chunk of text."""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=ExtractionResult,
            temperature=0.0,
        ),
    )
    return ExtractionResult.model_validate_json(response.text)


def extract_relationships(text: str, paper_title: str = None, doi: str = None,
                          abstract: str = None, source_url: str = None) -> ExtractionResult:
    """
    Extracts biological entities and relationships from the provided text.
    Automatically chunks long documents and merges results — callers see a
    single ExtractionResult regardless of paper length.
    """
    config = config_manager.config
    api_key = config.gemini_api_key

    if not api_key:
        logger.error("GEMINI_API_KEY not found. Extraction failed.")
        return ExtractionResult(entities=[], relationships=[])

    client = genai.Client(api_key=api_key)
    chunks = _chunk_text(text)

    chunk_results = []
    for idx, chunk in enumerate(chunks):
        if len(chunks) > 1:
            logger.info(f"Extracting chunk {idx + 1}/{len(chunks)}...")
        try:
            chunk_results.append(_extract_chunk(client, chunk))
        except Exception as e:
            logger.error(f"Extraction failed on chunk {idx + 1}: {e}")

    if not chunk_results:
        return ExtractionResult(entities=[], relationships=[])

    result = _merge_results(chunk_results) if len(chunk_results) > 1 else chunk_results[0]
    result.paper_title = paper_title
    result.doi = doi
    result.abstract = abstract
    result.source_url = source_url

    logger.info(
        f"Extracted {len(result.entities)} entities and "
        f"{len(result.relationships)} relationships"
        + (f" across {len(chunks)} chunks" if len(chunks) > 1 else "")
    )
    return result


if __name__ == "__main__":
    sample_text = (
        "Nitazoxanide Activates BMP9-ALK1-SMAD signaling cascade and improves HHT vascular "
        "pathology. We found that Nitazoxanide strongly inhibits TGF-beta signaling."
    )
    if os.environ.get("GEMINI_API_KEY"):
        print("Running test extraction...")
        result = extract_relationships(sample_text)
        print(f"Extracted {len(result.entities)} entities and {len(result.relationships)} relationships.")
        for r in result.relationships:
            print(f"{r.source_entity} --[{r.relationship_type}]--> {r.target_entity} (Confidence: {r.confidence})")
            print(f"  Evidence: {r.evidence}")
    else:
        print("Please set GEMINI_API_KEY to run the test extraction.")
