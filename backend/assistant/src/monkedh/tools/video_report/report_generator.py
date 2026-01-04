"""Report generation module for video analysis."""
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from .vision_client import VisionClient
from .report_formatter import markdown_to_html

logger = logging.getLogger(__name__)


CONCLUSION_PROMPT_FR = """Tu es un expert analyste d'incidents pour le Ministère de la Santé en Tunisie.
Basé sur les descriptions frame par frame ci-dessous, crée une CONCLUSION SYNTHÉTIQUE EN FRANÇAIS.

Descriptions des frames:
{descriptions}

{audio_section}

Génère UNIQUEMENT les sections suivantes (pas de répétition des analyses frame par frame):

## 📋 Résumé Exécutif
Aperçu global (3-4 phrases) de l'incident observé dans la vidéo.

## 👥 Synthèse des Observations

### Personnes Identifiées
- Nombre total de personnes observées
- Actions principales effectuées
- État général (debout, au sol, en mouvement, etc.)

### 🚨 Urgences Médicales Détectées
- Victimes en détresse (position, condition visible)
- Type d'urgence identifiée (arrêt cardiaque, chute, hémorragie, etc.)
- Niveau de gravité estimé

### ⚠️ Dangers et Risques
- Dangers environnementaux (feu, fumée, obstacle, etc.)
- Risques pour les intervenants
- Conditions de sécurité du lieu

### ⏱️ Évolution Chronologique
Résumé chronologique des événements clés observés.

{audio_report_section}

## 💡 Recommandations d'Intervention

### Actions Immédiates
- Que faire en premier
- Ressources nécessaires
- Précautions à prendre

### Protocoles Applicables
- Protocoles d'urgence recommandés
- Matériel médical nécessaire

### Contacts d'Urgence Tunisie
- 🚑 SAMU: 190
- 🚒 Protection Civile: 198  
- 👮 Police: 197
- ☎️ Urgences Générales: 193

## ⚖️ Niveau de Gravité
Évaluation finale: [Mineur / Modéré / Grave / Critique]

Sois factuel, précis et professionnel.
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


def get_conclusion_prompt(language: str = "français") -> str:
    """Get the appropriate conclusion prompt based on language."""
    if language == "arabe":
        return SUMMARIZATION_PROMPT_AR
    return CONCLUSION_PROMPT_FR


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
    
    logger.info(f"Generating frame-by-frame report with global conclusion in {language}")
    
    # ============================================
    # PARTIE 1: ANALYSE FRAME PAR FRAME DÉTAILLÉE
    # ============================================
    
    frame_by_frame_report = "# 🎥 Rapport d'Analyse Vidéo d'Incident\n\n"
    frame_by_frame_report += f"**Date**: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
    frame_by_frame_report += f"**Frames analysées**: {len([d for d in descriptions if d.get('status') == 'success'])}\n\n"
    frame_by_frame_report += "---\n\n"
    frame_by_frame_report += "## 🔍 Analyse Frame par Frame (Llava)\n\n"
    
    # Ajouter chaque frame individuellement avec numérotation claire
    for i, desc in enumerate(descriptions):
        if desc.get('status') == 'success':
            frame_num = i + 1
            frame_name = Path(desc['frame_path']).name
            frame_desc = desc['description']
            
            frame_by_frame_report += f"### 📸 Frame {frame_num} - `{frame_name}`\n\n"
            frame_by_frame_report += f"{frame_desc}\n\n"
            frame_by_frame_report += "---\n\n"
        else:
            frame_by_frame_report += f"### ⚠️ Frame {i+1} - Erreur d'analyse\n\n"
            frame_by_frame_report += f"Erreur: {desc.get('description', 'Inconnue')}\n\n"
            frame_by_frame_report += "---\n\n"
    
    # ============================================
    # PARTIE 2: CONCLUSION GÉNÉRALE SYNTHÉTIQUE
    # ============================================
    
    # Format frame descriptions for conclusion generation
    desc_text = "\n\n".join([
        f"**Frame {i+1}**: {d['description']}"
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
            audio_section = f"\n**تحليل الصوت**:\n{audio_summary}"
            audio_report_section = "### 🎧 Analyse Audio\nRésultats de l'analyse audio extraite de la vidéo."
        else:
            audio_section = f"\n**Analyse Audio**:\n{audio_summary}"
            audio_report_section = "### 🎧 Analyse Audio\nRésultats de l'analyse audio extraite de la vidéo."
    
    # Get the appropriate prompt for conclusion
    prompt_template = get_conclusion_prompt(language)
    prompt = prompt_template.format(
        descriptions=desc_text,
        audio_section=audio_section,
        audio_report_section=audio_report_section
    )
    
    conclusion_report = ""
    
    try:
        # Generate conclusion using LLM
        logger.info("Generating global conclusion with Llava...")
        conclusion_content = vision_client.generate_text(prompt)
        
        conclusion_report = "\n\n" + "="*80 + "\n\n"
        conclusion_report += "# 📊 CONCLUSION GÉNÉRALE\n\n"
        conclusion_report += conclusion_content
        
        # Inject detailed audio section if available
        if audio_section and audio_report_section not in conclusion_content:
            conclusion_report += f"\n\n{audio_report_section}\n{audio_section}"
        
    except Exception as e:
        logger.error(f"Failed to generate conclusion with LLM: {e}")
        
        # Fallback: create basic conclusion
        conclusion_report = "\n\n" + "="*80 + "\n\n"
        conclusion_report += "# 📊 CONCLUSION GÉNÉRALE\n\n"
        conclusion_report += "## ⚠️ Synthèse\n\n"
        conclusion_report += f"Analyse de {len([d for d in descriptions if d.get('status') == 'success'])} frames effectuée.\n\n"
        if audio_section:
            conclusion_report += f"{audio_report_section}\n{audio_section}\n\n"
    
    # Combine both parts
    full_report = frame_by_frame_report + conclusion_report
    
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
