"""Report generation module for video analysis."""
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from .vision_client import VisionClient
from .report_formatter import markdown_to_html

logger = logging.getLogger(__name__)


SUMMARIZATION_PROMPT_FR = """Tu es un expert analyste d'incidents pour le Ministère de la Santé en Tunisie. 
Basé sur les descriptions frame par frame ci-dessous, crée un rapport d'incident complet EN FRANÇAIS.

Descriptions des frames:
{descriptions}

{audio_section}

Crée un rapport structuré en Markdown avec ces sections:

# Rapport d'Analyse d'Incident Vidéo

## Résumé Exécutif
Aperçu bref (2-3 phrases) de ce qui s'est passé dans la vidéo.

## Observations Détaillées

### Personnes et Actions
- Nombre de personnes observées
- Leurs positions et mouvements
- Actions clés entreprises (ex: appel aux services d'urgence, assistance fournie)

### Préoccupations de Sécurité
- Personne(s) en détresse ou blessée(s) (sois spécifique sur leur condition et localisation)
- Présence de fumée, feu ou indicateurs d'accident
- Autres dangers ou situations dangereuses

### Indicateurs d'Urgence Médicale
- Signes d'arrêt cardiaque
- Étouffement
- Hémorragies
- Brûlures
- Inconscience
- Autres urgences médicales

### Chronologie des Événements
Description chronologique de ce qui s'est produit à travers les frames analysées.

{audio_report_section}

## Conclusions et Recommandations
- Résumé de la gravité de l'incident
- Actions immédiates recommandées
- Observations supplémentaires
- Numéros d'urgence Tunisie: SAMU 190, Protection Civile 198, Police 197

Sois factuel, spécifique et professionnel. Si quelqu'un est clairement en détresse, indique-le explicitement.
"""


SUMMARIZATION_PROMPT_AR = """أنت محلل خبير في الحوادث لوزارة الصحة في تونس. 
بناءً على الأوصاف الإطارية أدناه، قم بإنشاء تقرير شامل للحادث بالعربية.

أوصاف الإطارات:
{descriptions}

{audio_section}

قم بإنشاء تقرير منظم بصيغة Markdown مع هذه الأقسام:

# تقرير تحليل حادث الفيديو

## الملخص التنفيذي
نظرة عامة موجزة (2-3 جمل) عما حدث في الفيديو.

## الملاحظات التفصيلية

### الأشخاص والإجراءات
- عدد الأشخاص الملاحظين
- مواقعهم وتحركاتهم
- الإجراءات الرئيسية المتخذة

### مخاوف السلامة
- الشخص/الأشخاص في محنة أو مصابين
- وجود دخان أو حريق أو مؤشرات حادث
- مخاطر أخرى أو مواقف خطرة

### مؤشرات الطوارئ الطبية
- علامات السكتة القلبية
- الاختناق
- النزيف
- الحروق
- فقدان الوعي

### الجدول الزمني للأحداث
وصف زمني لما حدث عبر الإطارات المحللة.

{audio_report_section}

## الاستنتاجات والتوصيات
- ملخص خطورة الحادث
- الإجراءات الفورية الموصى بها
- أرقام الطوارئ تونس: الإسعاف 190، الحماية المدنية 198، الشرطة 197

كن واقعيًا ومحددًا ومهنيًا.
"""


def get_summarization_prompt(language: str = "français") -> str:
    """Get the appropriate summarization prompt based on language."""
    if language == "arabe":
        return SUMMARIZATION_PROMPT_AR
    return SUMMARIZATION_PROMPT_FR


def generate_report(
    frame_descriptions: List[Dict[str, Any]],
    audio_results: Optional[Dict[str, Any]] = None,
    vision_client: VisionClient = None,
    output_dir: str = None,
    language: str = "français"
) -> Tuple[str, str]:
    """Generate comprehensive incident report from frame and audio analysis.
    
    Args:
        frame_descriptions: List of frame analysis results
        audio_results: Optional audio analysis results
        vision_client: VisionClient instance
        output_dir: Directory to save reports
        language: Report language ("français" or "arabe")
        
    Returns:
        Tuple of (markdown_path, html_path)
    """
    if output_dir is None:
        output_dir = Path(__file__).parent / "output" / "reports"
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_file = output_path / f"report_{timestamp}.md"
    html_file = output_path / f"report_{timestamp}.html"
    
    return summarize_report(
        descriptions=frame_descriptions,
        audio_results=audio_results,
        vision_client=vision_client,
        output_path=str(md_file),
        language=language
    )


def summarize_report(
    descriptions: List[Dict[str, Any]],
    audio_results: Optional[Dict[str, Any]] = None,
    vision_client: VisionClient = None,
    output_path: str = "output/report.md",
    language: str = "français"
) -> Tuple[str, Optional[str]]:
    """Generate final incident report from frame descriptions.
    
    Args:
        descriptions: List of frame analysis results
        audio_results: Optional audio analysis results
        vision_client: VisionClient instance
        output_path: Path to save markdown report
        language: Language for the report
        
    Returns:
        Tuple of (markdown_path, html_path)
    """
    if vision_client is None:
        vision_client = VisionClient(provider="llava")
    
    logger.info(f"Generating final report in {language} from {len(descriptions)} frame descriptions")
    
    # Format frame descriptions
    desc_text = "\n\n".join([
        f"**Frame {i+1}** ({Path(d['frame_path']).name}):\n{d['description']}"
        for i, d in enumerate(descriptions)
        if d.get('status') == 'success'
    ])
    
    # Format audio section if available
    audio_section = ""
    audio_report_section = ""
    
    if audio_results and audio_results.get("has_audio"):
        from .audio_analyzer import format_audio_summary
        audio_summary = format_audio_summary(audio_results)
        
        if language == "arabe":
            audio_section = f"\nتحليل الصوت:\n{audio_summary}"
            audio_report_section = "### تحليل الصوت\nنتائج تحليل الصوت المستخرج من الفيديو."
        else:
            audio_section = f"\nAnalyse Audio:\n{audio_summary}"
            audio_report_section = "### Analyse Audio\nRésultats de l'analyse audio extraite de la vidéo."
    
    # Get the appropriate prompt
    prompt_template = get_summarization_prompt(language)
    prompt = prompt_template.format(
        descriptions=desc_text,
        audio_section=audio_section,
        audio_report_section=audio_report_section
    )
    
    try:
        # Generate report using LLM
        report_content = vision_client.generate_text(prompt)
        
        full_report = report_content
        
        # Inject detailed audio section if available before the conclusion
        if audio_section:
            conclusion_headers = ["## Conclusions et Recommandations", "## الاستنتاجات والتوصيات", "## Conclusion"]
            injected = False
            for header in conclusion_headers:
                if header in full_report:
                    full_report = full_report.replace(header, f"---\n\n{audio_section}\n\n{header}")
                    injected = True
                    break
            
            if not injected:
                full_report += "\n\n---\n\n" + audio_section
        
    except Exception as e:
        logger.error(f"Failed to generate report with LLM: {e}")
        
        # Fallback: create basic report without LLM
        if language == "arabe":
            full_report = f"""## أوصاف الإطارات
{desc_text}
{audio_section}
"""
        else:
            full_report = f"""## Descriptions des Frames
{desc_text}
{audio_section}
"""
    
    # Save markdown report
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(full_report)
    
    logger.info(f"Markdown report saved to: {output_path}")
    
    # Generate HTML report
    html_path = str(output_file).replace('.md', '.html')
    try:
        html_file = markdown_to_html(
            full_report,
            frames_count=len(descriptions),
            language=language,
            output_path=html_path
        )
        
        if html_file:
            logger.info(f"HTML report saved to: {html_file}")
            return str(output_file), html_file
    except Exception as e:
        logger.error(f"Failed to generate HTML report: {e}")
    
    return str(output_file), None


def get_report_summary(report_path: str) -> Dict[str, Any]:
    """Extract summary information from a generated report.
    
    Args:
        report_path: Path to markdown report
        
    Returns:
        Dictionary with summary info
    """
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract key info
        lines = content.split('\n')
        
        summary = {
            "path": report_path,
            "title": "",
            "generated_at": "",
            "frames_count": 0,
            "has_audio": "audio" in content.lower(),
            "emergency_detected": any(
                word in content.lower() 
                for word in ["urgence", "emergency", "détresse", "blessé", "injured"]
            )
        }
        
        for line in lines:
            if line.startswith("# "):
                summary["title"] = line[2:].strip()
            elif "Généré le:" in line or "تاريخ الإنشاء:" in line:
                summary["generated_at"] = line.split(":")[-1].strip().rstrip("*")
            elif "Frames analysées:" in line or "الإطارات المحللة:" in line:
                try:
                    summary["frames_count"] = int(line.split(":")[-1].strip().rstrip("*"))
                except:
                    pass
        
        return summary
        
    except Exception as e:
        logger.error(f"Failed to extract report summary: {e}")
        return {"path": report_path, "error": str(e)}
