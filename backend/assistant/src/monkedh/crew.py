from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai_tools import SerperDevTool, ScrapeWebsiteTool
from typing import List
import os
from pathlib import Path
from crewai import LLM
from .tools.redis_storage import RedisStorage
from crewai.memory.short_term.short_term_memory import ShortTermMemory
import dotenv
from monkedh.tools.rag import create_first_aid_search_tool
from monkedh.tools.rag.config import QDRANT_URL, QDRANT_API_KEY
from .tools.image_suggestion import search_emergency_image

# Load environment
env_path = Path(__file__).parent.parent.parent / ".env"
dotenv.load_dotenv(env_path)

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ["OTEL_SDK_DISABLED"] = "true"
# Azure OpenAI LLM
llm = LLM(
    model=os.getenv("model"),
    api_key=os.getenv("AZURE_API_KEY"),
    base_url=os.getenv('AZURE_API_BASE'),
    api_version=os.getenv("AZURE_API_VERSION"),
    stream=False,
)

@CrewBase
class Monkedh():
    """Monkedh crew - Optimisé pour rapidité"""

    agents: List[BaseAgent]
    tasks: List[Task]
    
    # Outils configurés pour performance
    serper_tool = SerperDevTool(
        country="tn",  # Tunisie directement
        locale="fr",
        n_results=2,  # Limité à 2 résultats max
    )
    webscraper_tool = ScrapeWebsiteTool()
    rag_tool = create_first_aid_search_tool(
        qdrant_url=QDRANT_URL,
        qdrant_api_key=QDRANT_API_KEY
    )
    image_tool = search_emergency_image
    
    @agent
    def assistant_urgence_medical(self) -> Agent:
        """
        Agent unique optimisé pour rapidité.
        Réduit latence via :
        - Prompts courts
        - max_iter=3 (permet retry mais limite boucles)
        - Cache désactivé (force fraîcheur des données)
        - Verbose=False (réduit overhead logging)
        """
        return Agent(
            config=self.agents_config['assistant_urgence_medical'],
            tools=[
                self.image_tool,       # PRIORITAIRE (toujours)
                self.rag_tool,         # PRIORITAIRE (toujours)
                self.serper_tool,      # CONDITIONNEL (selon urgence)
                self.webscraper_tool,  # CONDITIONNEL (selon urgence)
            ],
            llm=llm,
            max_iter=1,              # Permet retry mais évite boucles infinies
            cache=False,             # Force appel outils (pas de cache périmé)
            verbose=False,           # Réduit overhead
            max_retry_limit=0,       # Max 2 retries par outil
            allow_delegation=False,  # Pas de délégation inter-agents
        )

    @task
    def assistance_medicale_complete(self) -> Task:
        """
        Tâche unique optimisée.
        Output Markdown pour affichage rapide.
        """
        return Task(
            config=self.tasks_config['assistance_medicale_complete'],
            output_file='protocols_urgences.md'
        )

    @crew
    def crew(self) -> Crew:
        """
        Crew optimisé pour urgences médicales.
        
        Optimisations :
        - Short-term memory only (Redis rapide)
        - Process sequential (pas de parallélisation complexe)
        - Cache désactivé (fraîcheur données)
        - Verbose limité
        """
        redis_storage = RedisStorage(
            host=os.getenv("REDIS_HOST", "redis-13350.c339.eu-west-3-1.ec2.redns.redis-cloud.com"),
            port=int(os.getenv("REDIS_PORT", 13350)),
            db=int(os.getenv("REDIS_DB", 0)),
            password=os.getenv("REDIS_PASSWORD", "YoLErdUztvwgDQvhAr1Fgbp0NUdekrRm"),
            namespace="monkedh",
        )
        
        # Mémoire court-terme uniquement (plus rapide)
        short_term_memory = ShortTermMemory(storage=redis_storage)
        
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            short_term_memory=short_term_memory,
            verbose=True,  # Désactiver logs verbeux
            tracing=False,
            cache=False,    # Pas de cache crew-level
            memory=False,   # Désactiver long-term memory (inutile pour urgences)
        )
    