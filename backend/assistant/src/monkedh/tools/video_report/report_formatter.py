"""Enhanced report formatting with HTML support."""
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
import markdown

logger = logging.getLogger(__name__)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rapport d'Analyse Vidéo - Monkedh</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 10px 50px rgba(0, 0, 0, 0.3);
            border-radius: 12px;
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 40px;
            text-align: center;
            position: relative;
        }}
        
        .header::after {{
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        }}
        
        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
            font-weight: 700;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
        }}
        
        .header .subtitle {{
            font-size: 1.2rem;
            opacity: 0.95;
            font-weight: 300;
        }}
        
        .header .org {{
            margin-top: 15px;
            font-size: 1rem;
            opacity: 0.9;
            border-top: 1px solid rgba(255, 255, 255, 0.3);
            padding-top: 15px;
            font-weight: 500;
        }}
        
        .metadata {{
            background: #f8f9fa;
            padding: 20px 40px;
            border-bottom: 1px solid #e0e0e0;
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
        }}
        
        .metadata-item {{
            display: flex;
            align-items: center;
            margin: 10px 20px;
        }}
        
        .metadata-icon {{
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            margin-right: 12px;
            font-size: 1.2rem;
        }}
        
        .metadata-content {{
            display: flex;
            flex-direction: column;
        }}
        
        .metadata-label {{
            font-size: 0.85rem;
            color: #666;
            font-weight: 600;
        }}
        
        .metadata-value {{
            font-size: 1.1rem;
            color: #333;
            font-weight: 700;
        }}
        
        .content {{
            padding: 40px;
        }}
        
        .section {{
            margin-bottom: 40px;
            animation: fadeIn 0.5s ease-in;
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        h1 {{
            color: #1e3c72;
            font-size: 2.2rem;
            margin-bottom: 20px;
        }}
        
        h2 {{
            color: #1e3c72;
            font-size: 1.8rem;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
            position: relative;
        }}
        
        h2::before {{
            content: '';
            position: absolute;
            bottom: -3px;
            left: 0;
            width: 60px;
            height: 3px;
            background: #764ba2;
        }}
        
        h3 {{
            color: #2a5298;
            font-size: 1.4rem;
            margin: 25px 0 15px;
            padding-left: 15px;
            border-left: 4px solid #667eea;
        }}
        
        p {{
            margin-bottom: 15px;
            text-align: justify;
        }}
        
        ul {{
            margin: 15px 0;
            padding-left: 20px;
        }}
        
        li {{
            margin-bottom: 10px;
            padding-left: 10px;
            position: relative;
            list-style: none;
        }}
        
        li::before {{
            content: '▸';
            color: #667eea;
            font-weight: bold;
            position: absolute;
            left: -15px;
        }}
        
        .alert {{
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
            border-left: 5px solid;
            background: white;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }}
        
        .alert-danger {{
            border-color: #dc3545;
            background: #fff5f5;
        }}
        
        .alert-warning {{
            border-color: #ffc107;
            background: #fffbf0;
        }}
        
        .alert-info {{
            border-color: #17a2b8;
            background: #f0f9ff;
        }}
        
        .alert-success {{
            border-color: #28a745;
            background: #f0fff4;
        }}
        
        .emergency-numbers {{
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            color: white;
            padding: 25px;
            border-radius: 12px;
            margin: 30px 0;
            text-align: center;
        }}
        
        .emergency-numbers h4 {{
            font-size: 1.4rem;
            margin-bottom: 15px;
        }}
        
        .emergency-numbers .numbers {{
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 20px;
        }}
        
        .emergency-numbers .number-item {{
            background: rgba(255, 255, 255, 0.2);
            padding: 15px 25px;
            border-radius: 8px;
        }}
        
        .emergency-numbers .number {{
            font-size: 2rem;
            font-weight: 700;
        }}
        
        .emergency-numbers .label {{
            font-size: 0.9rem;
            opacity: 0.9;
        }}
        
        .footer {{
            background: #1e3c72;
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .footer p {{
            margin: 0;
            opacity: 0.9;
        }}
        
        strong {{
            color: #1e3c72;
        }}
        
        em {{
            color: #666;
            font-style: italic;
        }}
        
        hr {{
            border: none;
            height: 2px;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            margin: 30px 0;
        }}
        
        /* RTL support for Arabic */
        html[lang="ar"] {{
            direction: rtl;
        }}
        
        html[lang="ar"] h3 {{
            padding-left: 0;
            padding-right: 15px;
            border-left: none;
            border-right: 4px solid #667eea;
        }}
        
        html[lang="ar"] li::before {{
            left: auto;
            right: -15px;
            content: '◂';
        }}
        
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            
            .container {{
                box-shadow: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚑 {title}</h1>
            <p class="subtitle">{subtitle}</p>
            <p class="org">🏛️ {organization}</p>
        </div>
        
        <div class="metadata">
            <div class="metadata-item">
                <div class="metadata-icon">📅</div>
                <div class="metadata-content">
                    <span class="metadata-label">{date_label}</span>
                    <span class="metadata-value">{generated_at}</span>
                </div>
            </div>
            <div class="metadata-item">
                <div class="metadata-icon">🖼️</div>
                <div class="metadata-content">
                    <span class="metadata-label">{frames_label}</span>
                    <span class="metadata-value">{frames_count}</span>
                </div>
            </div>
            <div class="metadata-item">
                <div class="metadata-icon">🔍</div>
                <div class="metadata-content">
                    <span class="metadata-label">{status_label}</span>
                    <span class="metadata-value">{status}</span>
                </div>
            </div>
        </div>
        
        <div class="content">
            {content}
            
            <div class="emergency-numbers">
                <h4>{emergency_title}</h4>
                <div class="numbers">
                    <div class="number-item">
                        <div class="number">190</div>
                        <div class="label">SAMU</div>
                    </div>
                    <div class="number-item">
                        <div class="number">198</div>
                        <div class="label">Protection Civile</div>
                    </div>
                    <div class="number-item">
                        <div class="number">197</div>
                        <div class="label">Police</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>{footer_text}</p>
        </div>
    </div>
</body>
</html>"""


def markdown_to_html(
    md_content: str,
    frames_count: int = 0,
    language: str = "français",
    output_path: Optional[str] = None
) -> Optional[str]:
    """Convert markdown content to styled HTML report.
    
    Args:
        md_content: Markdown content to convert
        frames_count: Number of frames analyzed
        language: Report language ("français" or "arabe")
        output_path: Optional path to save HTML file
        
    Returns:
        Path to HTML file if saved, or HTML content string
    """
    # Convert markdown to HTML
    html_content = markdown.markdown(
        md_content,
        extensions=['tables', 'fenced_code', 'nl2br']
    )
    
    # Prepare template variables based on language
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    if language == "arabe":
        template_vars = {
            "lang": "ar",
            "title": "تقرير تحليل حادث الفيديو",
            "subtitle": "تحليل شامل للفيديو بالذكاء الاصطناعي",
            "organization": "وزارة الصحة - الجمهورية التونسية",
            "date_label": "تاريخ الإنشاء",
            "frames_label": "الإطارات المحللة",
            "status_label": "الحالة",
            "status": "مكتمل",
            "emergency_title": "أرقام الطوارئ - تونس",
            "footer_text": f"تم إنشاء هذا التقرير تلقائيًا بواسطة Monkedh - {generated_at}"
        }
    else:
        template_vars = {
            "lang": "fr",
            "title": "Rapport d'Analyse d'Incident Vidéo",
            "subtitle": "Analyse vidéo complète par Intelligence Artificielle",
            "organization": "Ministère de la Santé - République Tunisienne",
            "date_label": "Date de génération",
            "frames_label": "Frames analysées",
            "status_label": "Statut",
            "status": "Complet",
            "emergency_title": "Numéros d'Urgence - Tunisie",
            "footer_text": f"Rapport généré automatiquement par Monkedh - {generated_at}"
        }
    
    # Add common variables
    template_vars["generated_at"] = generated_at
    template_vars["frames_count"] = str(frames_count)
    template_vars["content"] = html_content
    
    # Generate final HTML
    final_html = HTML_TEMPLATE.format(**template_vars)
    
    # Save if path provided
    if output_path:
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(final_html)
            
            logger.info(f"HTML report saved to: {output_path}")
            return str(output_file)
            
        except Exception as e:
            logger.error(f"Failed to save HTML report: {e}")
            return None
    
    return final_html
