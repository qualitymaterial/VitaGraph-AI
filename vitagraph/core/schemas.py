from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class EntityType(str, Enum):
    COMPOUND  = "Compound"   # small molecules, drugs, metabolites, supplements
    TARGET    = "Target"     # genes and proteins — use HGNC gene symbol
    PATHWAY   = "Pathway"    # signaling cascades and metabolic pathways
    DISEASE   = "Disease"    # age-related pathologies and conditions
    BIOMARKER = "Biomarker"  # measurable indicators (telomere length, IGF-1 levels)
    ORGANISM  = "Organism"   # model organisms (C. elegans, M. musculus, S. cerevisiae)
    CELL_TYPE = "CellType"   # cell types and states (senescent cell, stem cell, hepatocyte)
    PHENOTYPE = "Phenotype"  # observable outcomes (lifespan extension, muscle atrophy)

class RelationshipType(str, Enum):
    UPREGULATES             = "Upregulates"
    DOWNREGULATES           = "Downregulates"
    INTERACTSWITH           = "InteractsWith"
    INHIBITS                = "Inhibits"
    ACTIVATES               = "Activates"
    REGULATES_EXPRESSION_OF = "RegulatesExpressionOf"  # transcriptional/epigenetic regulation
    ASSOCIATED_WITH         = "AssociatedWith"          # epidemiological or correlative association
    EXTENDS_LIFESPAN_OF     = "ExtendsLifespanOf"       # compound/gene extends lifespan in organism
    BIOMARKER_FOR           = "BiomarkerFor"            # entity is a diagnostic/prognostic marker

class Entity(BaseModel):
    name: str = Field(..., description="The standard name of the biological entity.")
    entity_type: EntityType = Field(..., description="Type of the entity, e.g., 'Compound', 'Target', 'Pathway', 'Disease'.")
    synonyms: List[str] = Field(default_factory=list, description="Other names or abbreviations for this entity found in the text.")

class Relationship(BaseModel):
    source_entity: str = Field(..., description="The name of the source entity.")
    target_entity: str = Field(..., description="The name of the target entity.")
    relationship_type: RelationshipType = Field(..., description="The type of relationship, e.g., 'Upregulates', 'Downregulates', 'InteractsWith', 'Inhibits', 'Activates'.")
    evidence: str = Field(..., description="The verbatim sentence from the text that proves this relationship.")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0 based on how strongly the text asserts this.")

class ExtractionResult(BaseModel):
    paper_title: Optional[str] = Field(None, description="Title of the paper knowledge was extracted from.")
    doi: Optional[str] = Field(None, description="DOI of the paper.")
    abstract: Optional[str] = Field(None, description="Abstract or summary of the paper.")
    source_url: Optional[str] = Field(None, description="URL to the original paper.")
    entities: List[Entity] = Field(default_factory=list, description="All biological entities extracted from the text.")
    relationships: List[Relationship] = Field(default_factory=list, description="All relationships extracted between the entities.")

class NoveltyLevel(str, Enum):
    KNOWN        = "known"
    LIKELY_KNOWN = "likely_known"
    NOVEL        = "novel"

class HypothesisEvaluation(BaseModel):
    is_plausible: bool        = Field(..., description="Whether the transitive hypothesis is biologically coherent and plausible.")
    confidence:   float       = Field(..., description="Confidence score 0.0–1.0 based on evidence quality and biological logic.")
    novelty:      NoveltyLevel = Field(..., description="Whether this relationship is already known, suspected, or genuinely novel.")
    reasoning:    str         = Field(..., description="2-3 sentence explanation citing specific biological mechanisms.")
