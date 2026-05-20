import os
import logging
from neo4j import GraphDatabase
from .schemas import ExtractionResult
from ..config import config_manager

logger = logging.getLogger(__name__)

def get_neo4j_driver():
    """
    Initializes and returns a Neo4j driver using the global configuration.
    """
    config = config_manager.config
    uri = config.neo4j_uri
    user = config.neo4j_user
    password = config.neo4j_password
    
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
        # Create Paper node if metadata exists
        if result.doi:
            session.run("""
                MERGE (p:Paper {doi: $doi})
                SET p.title = $title, p.updated_at = timestamp()
            """, {"doi": result.doi, "title": result.paper_title or "Unknown"})

        for rel in result.relationships:
            # We construct the Cypher query dynamically for the relationship type 
            rel_type = rel.relationship_type.upper().replace(" ", "_").replace("-", "_")
            
            cypher = f"""
            MERGE (source:Entity {{name: $source_name}})
            ON CREATE SET source.created_at = timestamp()
            
            MERGE (target:Entity {{name: $target_name}})
            ON CREATE SET target.created_at = timestamp()
            
            MERGE (source)-[r:{rel_type}]->(target)
            SET r.evidence = $evidence, r.confidence = $confidence, r.updated_at = timestamp()
            """
            
            # Link relationship to paper if DOI exists
            if result.doi:
                cypher += """
                WITH r
                MATCH (p:Paper {doi: $doi})
                MERGE (p)-[:MENTIONS]->(r)
                """
            
            parameters = {
                "source_name": rel.source_entity,
                "target_name": rel.target_entity,
                "evidence": rel.evidence,
                "confidence": rel.confidence,
                "doi": result.doi
            }
            
            try:
                session.run(cypher, parameters)
            except Exception as e:
                logger.error(f"Error inserting relationship {rel.source_entity} -[{rel_type}]-> {rel.target_entity}: {e}")
        
        # Update entity types and link to paper
        for entity in result.entities:
            entity_cypher = """
            MERGE (e:Entity {name: $name})
            SET e.type = $entity_type
            """
            if entity.synonyms:
                entity_cypher += " SET e.synonyms = $synonyms"
            
            if result.doi:
                entity_cypher += """
                WITH e
                MATCH (p:Paper {doi: $doi})
                MERGE (p)-[:DESCRIBES]->(e)
                """
                
            session.run(entity_cypher, {
                "name": entity.name, 
                "entity_type": entity.entity_type,
                "synonyms": entity.synonyms,
                "doi": result.doi
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
