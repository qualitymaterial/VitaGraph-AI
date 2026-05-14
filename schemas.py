from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class EntityType(str, Enum):
    COMPOUND = "Compound"
    TARGET = "Target"
    PATHWAY = "Pathway"
    DISEASE = "Disease"

class RelationshipType(str, Enum):
    UPREGULATES = "Upregulates"
    DOWNREGULATES = "Downregulates"
    INTERACTSWITH = "InteractsWith"
    INHIBITS = "Inhibits"
    ACTIVATES = "Activates"

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
    entities: List[Entity] = Field(default_factory=list, description="All biological entities extracted from the text.")
    relationships: List[Relationship] = Field(default_factory=list, description="All relationships extracted between the entities.")
