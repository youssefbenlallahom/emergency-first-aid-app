"""Email sender module for sending analysis reports."""
import os
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailSender:
    """Handles sending emails with report attachments."""
    
    def __init__(
        self,
        smtp_server: Optional[str] = None,
        smtp_port: Optional[int] = None,
        sender_email: Optional[str] = None,
        sender_password: Optional[str] = None
    ):
        """Initialize email sender with SMTP configuration.
        
        Args:
            smtp_server: SMTP server address (defaults to env var SMTP_SERVER)
            smtp_port: SMTP port (defaults to env var SMTP_PORT or 587)
            sender_email: Sender email address (defaults to env var SENDER_EMAIL)
            sender_password: Sender email password (defaults to env var SENDER_PASSWORD)
        """
        self.smtp_server = smtp_server or os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = smtp_port or int(os.getenv('SMTP_PORT', '587'))
        self.sender_email = sender_email or os.getenv('SENDER_EMAIL')
        self.sender_password = sender_password or os.getenv('SENDER_PASSWORD')
        
        if not self.sender_email or not self.sender_password:
            logger.warning("Email credentials not configured. Set SENDER_EMAIL and SENDER_PASSWORD in .env")
    
    def is_configured(self) -> bool:
        """Check if email sender is properly configured."""
        return bool(self.sender_email and self.sender_password)
    
    def send_report(
        self,
        recipient_email: str,
        report_path: str,
        html_report_path: Optional[str] = None,
        subject: Optional[str] = None,
        language: str = "français"
    ) -> bool:
        """Send analysis report via email.
        
        Args:
            recipient_email: Recipient email address
            report_path: Path to markdown report file
            html_report_path: Optional path to HTML report
            subject: Email subject (auto-generated if None)
            language: Report language for email content
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.is_configured():
            logger.error("Email credentials not configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            
            # Set subject
            if subject is None:
                if language == "arabe":
                    subject = f"تقرير تحليل الفيديو - Monkedh - {datetime.now().strftime('%d/%m/%Y')}"
                else:
                    subject = f"Rapport d'Analyse Vidéo - Monkedh - {datetime.now().strftime('%d/%m/%Y')}"
            
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            msg['Subject'] = subject
            
            # Create email body
            if language == "arabe":
                text_body = """
مرحبًا،

يرجى الاطلاع على تقرير تحليل الفيديو المرفق.

تم إنشاء هذا التقرير تلقائيًا بواسطة نظام Monkedh.

مع أطيب التحيات،
فريق Monkedh
وزارة الصحة - الجمهورية التونسية
                """
            else:
                text_body = """
Bonjour,

Veuillez trouver ci-joint le rapport d'analyse vidéo.

Ce rapport a été généré automatiquement par le système Monkedh.

Cordialement,
L'équipe Monkedh
Ministère de la Santé - République Tunisienne
                """
            
            msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
            
            # Attach HTML content if available
            if html_report_path and Path(html_report_path).exists():
                with open(html_report_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            # Attach markdown report
            if Path(report_path).exists():
                self._attach_file(msg, report_path)
            
            # Attach HTML report as file
            if html_report_path and Path(html_report_path).exists():
                self._attach_file(msg, html_report_path)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to: {recipient_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def _attach_file(self, msg: MIMEMultipart, file_path: str) -> None:
        """Attach a file to the email message."""
        try:
            file_path = Path(file_path)
            
            with open(file_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
            
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="{file_path.name}"'
            )
            msg.attach(part)
            
        except Exception as e:
            logger.error(f"Failed to attach file {file_path}: {e}")
    
    def send_emergency_alert(
        self,
        recipient_emails: List[str],
        report_path: str,
        emergency_type: str,
        location: Optional[str] = None
    ) -> bool:
        """Send emergency alert with report to multiple recipients.
        
        Args:
            recipient_emails: List of recipient email addresses
            report_path: Path to report file
            emergency_type: Type of emergency detected
            location: Optional location information
            
        Returns:
            True if all emails sent successfully
        """
        subject = f"🚨 ALERTE URGENCE: {emergency_type} - Intervention Requise"
        
        if location:
            subject += f" - {location}"
        
        success = True
        for email in recipient_emails:
            if not self.send_report(email, report_path, subject=subject):
                success = False
        
        return success
