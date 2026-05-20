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

def _resolve_canonical(session, name: str) -> str:
    """
    Looks up an entity by case-insensitive name or synonym match.
    Returns the canonical name of an existing node, or the input name if none found.
    This prevents duplicate nodes for the same entity referenced differently across papers.
    """
    result = session.run("""
        MATCH (e:Entity)
        WHERE toLower(trim(e.name)) = toLower(trim($name))
           OR toLower(trim($name)) IN [s IN coalesce(e.synonyms, []) | toLower(trim(s))]
        RETURN e.name AS canonical
        LIMIT 1
    """, {"name": name})
    record = result.single()
    return record["canonical"] if record else name


def _merge_entity_pair(session, keep_name: str, drop_name: str):
    """
    Merges the 'drop' entity into the 'keep' entity by redirecting all
    relationships, combining synonyms, and deleting the duplicate node.
    Does not use APOC — works with standard Cypher.
    """
    if keep_name == drop_name:
        return

    # Collect results to lists before running further queries in this session
    out_rows = list(session.run("""
        MATCH (b:Entity {name: $drop})-[r]->(t:Entity)
        WHERE t.name <> $keep
        RETURN type(r) AS rel_type, t.name AS target,
               r.evidence AS evidence, r.confidence AS confidence
    """, {"drop": drop_name, "keep": keep_name}))

    in_rows = list(session.run("""
        MATCH (s:Entity)-[r]->(b:Entity {name: $drop})
        WHERE s.name <> $keep
        RETURN type(r) AS rel_type, s.name AS source,
               r.evidence AS evidence, r.confidence AS confidence
    """, {"drop": drop_name, "keep": keep_name}))

    for row in out_rows:
        rel_type = row["rel_type"]
        session.run(f"""
            MATCH (a:Entity {{name: $keep}}), (t:Entity {{name: $target}})
            MERGE (a)-[r:{rel_type}]->(t)
            ON CREATE SET r.evidence = $evidence, r.confidence = $confidence,
                          r.updated_at = timestamp()
        """, {"keep": keep_name, "target": row["target"],
              "evidence": row["evidence"], "confidence": row["confidence"]})

    for row in in_rows:
        rel_type = row["rel_type"]
        session.run(f"""
            MATCH (s:Entity {{name: $source}}), (a:Entity {{name: $keep}})
            MERGE (s)-[r:{rel_type}]->(a)
            ON CREATE SET r.evidence = $evidence, r.confidence = $confidence,
                          r.updated_at = timestamp()
        """, {"source": row["source"], "keep": keep_name,
              "evidence": row["evidence"], "confidence": row["confidence"]})

    # Combine synonyms and delete the duplicate
    session.run("""
        MATCH (a:Entity {name: $keep}), (b:Entity {name: $drop})
        SET a.synonyms = [s IN coalesce(a.synonyms, []) + [b.name] + coalesce(b.synonyms, [])
                          WHERE s <> a.name AND s <> '']
        DETACH DELETE b
    """, {"keep": keep_name, "drop": drop_name})


def normalize_entities(driver) -> dict:
    """
    Post-insert normalization pass. Finds and merges duplicate entity nodes caused by:
    1. Case-insensitive name variants (mTOR vs MTOR vs mtor)
    2. Synonym overlap (entity A's name appears in entity B's synonyms list)
    Safe to run at any time — idempotent.
    """
    total_merged = 0

    with driver.session() as session:
        # Round 1: case-insensitive duplicates
        while True:
            result = session.run("""
                MATCH (a:Entity), (b:Entity)
                WHERE id(a) < id(b)
                  AND toLower(trim(a.name)) = toLower(trim(b.name))
                RETURN a.name AS keep, b.name AS drop
                LIMIT 1
            """)
            pair = result.single()
            if not pair:
                break
            logger.info(f"Merging case variant: '{pair['drop']}' → '{pair['keep']}'")
            _merge_entity_pair(session, pair["keep"], pair["drop"])
            total_merged += 1

        # Round 2: synonym-based duplicates
        while True:
            result = session.run("""
                MATCH (a:Entity), (b:Entity)
                WHERE id(a) < id(b)
                  AND (b.name IN coalesce(a.synonyms, [])
                       OR a.name IN coalesce(b.synonyms, []))
                RETURN a.name AS keep, b.name AS drop
                LIMIT 1
            """)
            pair = result.single()
            if not pair:
                break
            logger.info(f"Merging synonym variant: '{pair['drop']}' → '{pair['keep']}'")
            _merge_entity_pair(session, pair["keep"], pair["drop"])
            total_merged += 1

    return {"merged": total_merged}


def insert_extraction_result(driver, result: ExtractionResult):
    """
    Inserts extracted entities and relationships into the Neo4j graph.
    Resolves canonical entity names before MERGE to prevent duplicates from
    case variants or synonym mismatches across papers.
    """
    if not driver:
        logger.warning("No Neo4j driver provided. Skipping graph insertion.")
        return

    with driver.session() as session:
        if result.doi:
            session.run("""
                MERGE (p:Paper {doi: $doi})
                SET p.title      = $title,
                    p.abstract   = $abstract,
                    p.source_url = $source_url,
                    p.updated_at = timestamp()
            """, {
                "doi":        result.doi,
                "title":      result.paper_title or "Unknown",
                "abstract":   result.abstract or "",
                "source_url": result.source_url or "",
            })

        for rel in result.relationships:
            rel_type = rel.relationship_type.upper().replace(" ", "_").replace("-", "_")

            # Resolve to existing canonical names before MERGE
            source_name = _resolve_canonical(session, rel.source_entity)
            target_name = _resolve_canonical(session, rel.target_entity)

            cypher = f"""
            MERGE (source:Entity {{name: $source_name}})
            ON CREATE SET source.created_at = timestamp()

            MERGE (target:Entity {{name: $target_name}})
            ON CREATE SET target.created_at = timestamp()

            MERGE (source)-[r:{rel_type}]->(target)
            SET r.evidence    = $evidence,
                r.confidence  = $confidence,
                r.doi         = $doi,
                r.updated_at  = timestamp()
            """

            try:
                session.run(cypher, {
                    "source_name": source_name,
                    "target_name": target_name,
                    "evidence":    rel.evidence,
                    "confidence":  rel.confidence,
                    "doi":         result.doi,
                })
            except Exception as e:
                logger.error(f"Error inserting {source_name} -[{rel_type}]-> {target_name}: {e}")

        for entity in result.entities:
            canonical_name = _resolve_canonical(session, entity.name)

            # If we resolved to a different canonical, treat the original as a synonym
            new_synonyms = list(entity.synonyms)
            if canonical_name != entity.name:
                new_synonyms.append(entity.name)

            entity_cypher = """
            MERGE (e:Entity {name: $name})
            ON CREATE SET e.created_at = timestamp()
            SET e.type = $entity_type,
                e.synonyms = [s IN coalesce(e.synonyms, []) + $new_synonyms
                              WHERE s <> $name AND s <> '']
            """

            if result.doi:
                entity_cypher += """
                WITH e
                MATCH (p:Paper {doi: $doi})
                MERGE (p)-[:DESCRIBES]->(e)
                """

            session.run(entity_cypher, {
                "name": canonical_name,
                "entity_type": entity.entity_type,
                "new_synonyms": new_synonyms,
                "doi": result.doi,
            })

    logger.info(f"Inserted {len(result.entities)} entities and {len(result.relationships)} relationships.")

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
