import os
import json
from pathlib import Path
from typing import Optional, Any
from pydantic import BaseModel, Field

class Config(BaseModel):
    gemini_api_key: Optional[str] = Field(None, description="Google Gemini API Key")
    neo4j_uri: str = Field("bolt://localhost:7687", description="Neo4j Connection URI")
    neo4j_user: str = Field("neo4j", description="Neo4j Username")
    neo4j_password: str = Field("password", description="Neo4j Password")
    output_dir: str = Field("./data/pdfs", description="Default directory for PDF downloads")

class ConfigManager:
    def __init__(self):
        self.config_dir = Path.home() / ".vitagraph"
        self.config_file = self.config_dir / "config.json"
        self._config: Optional[Config] = None

    def _ensure_dir(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> Config:
        """Loads config from file, environment, or defaults."""
        data = {}
        
        # 1. Load from file if exists
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
            except Exception:
                pass

        # 2. Override with environment variables
        env_map = {
            "GEMINI_API_KEY": "gemini_api_key",
            "NEO4J_URI": "neo4j_uri",
            "NEO4J_USER": "neo4j_user",
            "NEO4J_PASSWORD": "neo4j_password",
            "VITAGRAPH_OUTPUT_DIR": "output_dir"
        }
        
        for env_var, key in env_map.items():
            val = os.environ.get(env_var)
            if val:
                data[key] = val

        self._config = Config(**data)
        return self._config

    def save(self, config: Config):
        """Saves config to the global config file."""
        self._ensure_dir()
        with open(self.config_file, "w") as f:
            json.dump(config.model_dump(), f, indent=4)
        self._config = config

    @property
    def config(self) -> Config:
        if self._config is None:
            return self.load()
        return self._config

# Singleton instance
config_manager = ConfigManager()
