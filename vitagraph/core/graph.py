import os
import logging
from neo4j import GraphDatabase
from .schemas import ExtractionResult

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_neo4j_driver():
    """
    Initializes and returns a Neo4j driver using environment variables.
    """
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "password")
    
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        logger.info("Successfully connected to Neo4j database.")
        return driver
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        return None

def insert_extraction_result(driver, result: ExtractionResult):
    """
    Inserts extracted entities and relationships into the Neo4j graph.
    Uses MERGE to prevent duplicate entities.
    """
    if not driver:
        logger.warning("No Neo4j driver provided. Skipping graph insertion.")
        return

    query = """
    UNWIND $relationships AS rel
    
    // Create or find the Source Entity
    MERGE (source:Entity {name: rel.source_entity})
    ON CREATE SET source.created_at = timestamp()
    
    // Create or find the Target Entity
    MERGE (target:Entity {name: rel.target_entity})
    ON CREATE SET target.created_at = timestamp()
    
    // Create or update the Relationship
    // We use apoc.create.relationship or dynamic query, but for a strict set,
    // we usually pass relationship type as a parameter if we use APOC.
    // Without APOC, we can build the query string dynamically, which is safe 
    // here because the relationship types are strictly controlled by our Pydantic schema.
    """
    
    with driver.session() as session:
        for rel in result.relationships:
            # We construct the Cypher query dynamically for the relationship type 
            # since Cypher doesn't allow parameterized relationship types directly without APOC
            rel_type = rel.relationship_type.upper().replace(" ", "_").replace("-", "_")
            
            cypher = f"""
            MERGE (source:Entity {{name: $source_name}})
            ON CREATE SET source.created_at = timestamp()
            
            MERGE (target:Entity {{name: $target_name}})
            ON CREATE SET target.created_at = timestamp()
            
            MERGE (source)-[r:{rel_type}]->(target)
            SET r.evidence = $evidence, r.confidence = $confidence, r.updated_at = timestamp()
            """
            
            parameters = {
                "source_name": rel.source_entity,
                "target_name": rel.target_entity,
                "evidence": rel.evidence,
                "confidence": rel.confidence
            }
            
            try:
                session.run(cypher, parameters)
            except Exception as e:
                logger.error(f"Error inserting relationship {rel.source_entity} -[{rel_type}]-> {rel.target_entity}: {e}")
        
        # We also want to update entity types and synonyms based on the entities list
        for entity in result.entities:
            entity_cypher = """
            MERGE (e:Entity {name: $name})
            SET e.type = $entity_type
            """
            # Add synonyms if any
            if entity.synonyms:
                entity_cypher += " SET e.synonyms = $synonyms"
            
            session.run(entity_cypher, {
                "name": entity.name, 
                "entity_type": entity.entity_type,
                "synonyms": entity.synonyms
            })
            
    logger.info(f"Successfully inserted {len(result.entities)} entities and {len(result.relationships)} relationships into Neo4j.")

if __name__ == "__main__":
    from .schemas import Entity, Relationship
    
    # Test execution
    driver = get_neo4j_driver()
    if driver:
        dummy_result = ExtractionResult(
            entities=[
                Entity(name="Compound X", entity_type="Compound", synonyms=["CX"]),
                Entity(name="Gene Y", entity_type="Target", synonyms=[])
            ],
            relationships=[
                Relationship(
                    source_entity="Compound X",
                    target_entity="Gene Y",
                    relationship_type="Activates",
                    evidence="Compound X Activates Gene Y in vivo.",
                    confidence=0.88
                )
            ]
        )
        insert_extraction_result(driver, dummy_result)
        driver.close()
    else:
        print("Neo4j is not running. Could not test insertion.")
