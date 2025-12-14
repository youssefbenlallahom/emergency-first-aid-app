"""
CrewAI Crew for Video Incident Analysis.

Orchestrates multiple AI agents to analyze video for emergency detection
and generate comprehensive incident reports.
"""
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai import LLM
from typing import List, Optional
from pathlib import Path
import os

from dotenv import load_dotenv

from .tools import (
    FrameExtractionTool,
    VisionAnalysisTool,
    ReportGenerationTool,
    AudioAnalysisTool,
    VideoInfoTool
)

# Load environment variables
env_path = Path(__file__).parent.parent.parent.parent.parent / ".env"
load_dotenv(env_path)


# Configure Azure OpenAI LLM for agents
def get_llm():
    """Get configured LLM for video report agents."""
    azure_key = os.getenv("AZURE_API_KEY")
    azure_base = os.getenv("AZURE_API_BASE")
    
    if azure_key and azure_base:
        return LLM(
            model="azure/gpt-4o",
            api_key=azure_key,
            base_url=azure_base,
            api_version=os.getenv("AZURE_API_VERSION", "2024-12-01-preview"),
        )
    
    # Fallback to TokenFactory Llama
    return LLM(
        model="openai/hosted_vllm/Llama-3.1-70B-Instruct",
        api_key=os.getenv("LLAVA_API_KEY"),
        base_url=os.getenv("LLAVA_BASE_URL", "https://tokenfactory.esprit.tn/api"),
        temperature=0.1,
    )


class VideoReportCrew:
    """
    CrewAI Crew for video incident analysis.
    
    This crew analyzes video files to detect emergencies and generate
    comprehensive incident reports for the Tunisian Ministry of Health.
    """
    
    def __init__(self):
        """Initialize the video report crew with tools."""
        self.frame_tool = FrameExtractionTool()
        self.vision_tool = VisionAnalysisTool()
        self.report_tool = ReportGenerationTool()
        self.audio_tool = AudioAnalysisTool()
        self.video_info_tool = VideoInfoTool()
        self.llm = get_llm()
    
    def frame_extractor_agent(self) -> Agent:
        """Create the frame extraction agent."""
        return Agent(
            role="Spécialiste en Extraction de Frames",
            goal="Extraire des frames de fichiers vidéo à des intervalles optimaux pour une analyse complète",
            backstory="""Vous êtes un expert en traitement vidéo et extraction de frames avec des années
            d'expérience dans les systèmes de surveillance et l'analyse d'incidents. Votre expertise
            réside dans l'extraction efficace de frames clés de vidéos qui capturent des moments
            critiques pour un examen détaillé.""",
            tools=[self.frame_tool, self.video_info_tool],
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )
    
    def vision_analyst_agent(self) -> Agent:
        """Create the vision analysis agent."""
        return Agent(
            role="Expert en Analyse Visuelle - Ministère de la Santé Tunisie",
            goal="Analyser les frames vidéo pour détecter personnes, dangers, situations de détresse et urgences médicales",
            backstory="""Vous êtes un analyste d'incidents hautement qualifié avec une expertise en
            vision par ordinateur et intervention d'urgence pour le Ministère de la Santé en Tunisie.
            Vous excellez dans l'identification des personnes en détresse, la reconnaissance des 
            dangers de sécurité, et la documentation précise des situations d'urgence médicale.""",
            tools=[self.vision_tool],
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )
    
    def audio_analyst_agent(self) -> Agent:
        """Create the audio analysis agent."""
        return Agent(
            role="Expert en Analyse Audio pour les Urgences - Ministère de la Santé Tunisie",
            goal="Analyser la piste audio pour détecter sons critiques, paroles, urgences et contexte émotionnel",
            backstory="""Vous êtes un spécialiste en analyse audio avec une expertise en reconnaissance
            de la parole et détection d'événements sonores. Vous excellez dans l'identification de sons
            critiques (cris, alarmes, sirènes), la transcription de la parole, et la détection des
            émotions dans les conversations d'urgence.""",
            tools=[self.audio_tool],
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )
    
    def report_generator_agent(self) -> Agent:
        """Create the report generation agent."""
        return Agent(
            role="Spécialiste en Rapports d'Incidents - Ministère de la Santé Tunisie",
            goal="Créer des rapports d'incidents complets et bien structurés à partir d'analyses visuelles et audio",
            backstory="""Vous êtes un rédacteur de rapports d'incidents expérimenté pour le Ministère
            de la Santé de la République Tunisienne. Vous excellez dans la synthèse de multiples
            observations en rapports clairs et exploitables pour les premiers intervenants et les
            équipes de sécurité sanitaire.""",
            tools=[self.report_tool],
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )
    
    def create_extraction_task(self, video_path: str, sample_rate: float = 2.0) -> Task:
        """Create frame extraction task."""
        return Task(
            description=f"""Extraire les frames du fichier vidéo situé à: {video_path}
            
            Utiliser un taux d'échantillonnage de {sample_rate} secondes.
            Sauvegarder les frames extraites avec des horodatages clairs.
            Retourner la liste complète des chemins vers les frames extraites.""",
            expected_output="Liste de chemins de fichiers vers toutes les frames extraites.",
            agent=self.frame_extractor_agent()
        )
    
    def create_vision_task(self, language: str = "français") -> Task:
        """Create vision analysis task."""
        return Task(
            description=f"""Analyser chaque frame vidéo extraite pour fournir des observations sur:
            
            1. PERSONNES: Compter et décrire positions, états, conditions
            2. DANGERS: Détecter fumée, feu, accidents, situations dangereuses
            3. URGENCES MÉDICALES: Signes d'arrêt cardiaque, étouffement, hémorragies, brûlures
            4. ACTIONS: Documenter ce que font les personnes
            5. ENVIRONNEMENT: Décrire le cadre général
            
            Langue d'analyse: {language}
            Soyez SPÉCIFIQUE concernant toute personne en détresse.""",
            expected_output="Liste de descriptions détaillées frame par frame.",
            agent=self.vision_analyst_agent()
        )
    
    def create_audio_task(self, video_path: str, language: str = "fr") -> Task:
        """Create audio analysis task."""
        return Task(
            description=f"""Analyser la piste audio de la vidéo: {video_path}
            
            1. Extraire et transcrire la parole (langue: {language})
            2. Identifier les sons critiques (cris, alarmes, sirènes)
            3. Détecter les émotions dans la parole
            4. Créer une chronologie des événements audio importants""",
            expected_output="Résumé complet de l'analyse audio avec transcription et émotions.",
            agent=self.audio_analyst_agent()
        )
    
    def create_report_task(self, language: str = "français") -> Task:
        """Create report generation task."""
        return Task(
            description=f"""Générer un rapport d'incident complet en {language} incluant:
            
            1. Résumé exécutif
            2. Observations détaillées (personnes, dangers, urgences)
            3. Chronologie des événements
            4. Conclusions et recommandations
            5. Numéros d'urgence Tunisie (SAMU 190, Protection Civile 198, Police 197)
            
            Le rapport doit être professionnel et exploitable par les équipes d'intervention.""",
            expected_output="Chemin vers le rapport Markdown et HTML généré.",
            agent=self.report_generator_agent(),
            output_file='output/report.md'
        )
    
    def analyze_video(
        self,
        video_path: str,
        sample_rate: float = 2.0,
        language: str = "français",
        include_audio: bool = True
    ) -> dict:
        """
        Run complete video analysis pipeline.
        
        Args:
            video_path: Path to video file
            sample_rate: Frame extraction rate in seconds
            language: Report language
            include_audio: Whether to include audio analysis
            
        Returns:
            Dictionary with analysis results and report paths
        """
        print("\n" + "="*60)
        print("🎥 MONKEDH - Video Incident Analysis System")
        print("="*60)
        print(f"\nVideo: {video_path}")
        print(f"Sample Rate: 1 frame every {sample_rate} seconds")
        print(f"Language: {language}")
        print(f"Audio Analysis: {'Enabled' if include_audio else 'Disabled'}")
        print("\n" + "="*60 + "\n")
        
        # Build tasks
        tasks = []
        agents = []
        
        # Frame extraction
        extraction_task = self.create_extraction_task(video_path, sample_rate)
        tasks.append(extraction_task)
        agents.append(self.frame_extractor_agent())
        
        # Vision analysis
        vision_task = self.create_vision_task(language)
        tasks.append(vision_task)
        agents.append(self.vision_analyst_agent())
        
        # Audio analysis (optional)
        if include_audio:
            audio_lang = "ar" if language == "arabe" else "fr"
            audio_task = self.create_audio_task(video_path, audio_lang)
            tasks.append(audio_task)
            agents.append(self.audio_analyst_agent())
        
        # Report generation
        report_task = self.create_report_task(language)
        tasks.append(report_task)
        agents.append(self.report_generator_agent())
        
        # Create and run crew
        crew = Crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=True
        )
        
        result = crew.kickoff()
        
        print("\n" + "="*60)
        print("✅ Analysis Complete!")
        print("="*60)
        
        return {
            "result": result,
            "video_path": video_path,
            "sample_rate": sample_rate,
            "language": language
        }
