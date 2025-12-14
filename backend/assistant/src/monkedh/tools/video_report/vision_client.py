"""
Client multi-providers avec support OpenAI, Anthropic, Google, Llava pour vision.
"""
import os
import base64
import logging
from typing import Optional, Literal
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

ProviderType = Literal["openai", "anthropic", "google", "llava", "azure"]


class VisionClient:
    """Client universel pour analyse d'images avec différents providers."""
    
    def __init__(
        self,
        provider: ProviderType = "llava",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """Initialize vision client.
        
        Args:
            provider: Provider à utiliser (openai, anthropic, google, llava, azure)
            api_key: Clé API (ou utilise variable d'environnement)
            base_url: URL de base pour l'API (pour llava ou custom endpoints)
        """
        self.provider = provider
        self.base_url = base_url
        
        # Déterminer la clé API selon le provider
        if api_key:
            self.api_key = api_key
        elif provider == "openai":
            self.api_key = os.getenv("OPENAI_API_KEY")
        elif provider == "anthropic":
            self.api_key = os.getenv("ANTHROPIC_API_KEY")
        elif provider == "google":
            self.api_key = os.getenv("GOOGLE_API_KEY")
        elif provider == "llava":
            self.api_key = os.getenv("LLAVA_API_KEY")
            self.base_url = base_url or os.getenv("LLAVA_BASE_URL", "https://tokenfactory.esprit.tn/api")
        elif provider == "azure":
            self.api_key = os.getenv("AZURE_API_KEY")
            self.base_url = base_url or os.getenv("AZURE_API_BASE")
        else:
            self.api_key = None
        
        if not self.api_key:
            logger.warning(f"No API key found for provider: {provider}")
    
    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64."""
        with open(image_path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")
    
    def _get_mime_type(self, image_path: str) -> str:
        """Get MIME type from file extension."""
        ext = Path(image_path).suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return mime_types.get(ext, "image/jpeg")
    
    def analyze_image(self, image_path: str, prompt: str) -> str:
        """Analyze image using configured provider.
        
        Args:
            image_path: Path to image file
            prompt: Analysis prompt
            
        Returns:
            Analysis description string
        """
        if self.provider == "llava":
            return self._analyze_with_llava(image_path, prompt)
        elif self.provider == "openai":
            return self._analyze_with_openai(image_path, prompt)
        elif self.provider == "azure":
            return self._analyze_with_azure(image_path, prompt)
        elif self.provider == "anthropic":
            return self._analyze_with_anthropic(image_path, prompt)
        elif self.provider == "google":
            return self._analyze_with_google(image_path, prompt)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _analyze_with_llava(self, image_path: str, prompt: str) -> str:
        """Analyze using Llava via ESPRIT TokenFactory."""
        import httpx
        
        from openai import OpenAI
        
        base64_image = self._encode_image(image_path)
        mime_type = self._get_mime_type(image_path)
        
        # Create HTTP client that disables SSL verification
        http_client = httpx.Client(verify=False, timeout=60.0)
        
        # Use OpenAI client with custom base_url
        client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=http_client
        )
        
        try:
            response = client.chat.completions.create(
                model="hosted_vllm/llava-1.5-7b-hf",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1024,
                temperature=0.2
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Llava API error: {e}")
            raise
        finally:
            http_client.close()
    
    def _analyze_with_openai(self, image_path: str, prompt: str) -> str:
        """Analyze using OpenAI GPT-4 Vision."""
        from openai import OpenAI
        
        client = OpenAI(api_key=self.api_key)
        base64_image = self._encode_image(image_path)
        mime_type = self._get_mime_type(image_path)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            max_tokens=1024
        )
        
        return response.choices[0].message.content
    
    def _analyze_with_azure(self, image_path: str, prompt: str) -> str:
        """Analyze using Azure OpenAI."""
        from openai import AzureOpenAI
        
        client = AzureOpenAI(
            api_key=self.api_key,
            api_version=os.getenv("AZURE_API_VERSION", "2024-12-01-preview"),
            azure_endpoint=self.base_url
        )
        
        base64_image = self._encode_image(image_path)
        mime_type = self._get_mime_type(image_path)
        
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            max_tokens=1024
        )
        
        return response.choices[0].message.content
    
    def _analyze_with_anthropic(self, image_path: str, prompt: str) -> str:
        """Analyze using Anthropic Claude."""
        import anthropic
        
        client = anthropic.Anthropic(api_key=self.api_key)
        base64_image = self._encode_image(image_path)
        mime_type = self._get_mime_type(image_path)
        
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": base64_image
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )
        
        return response.content[0].text
    
    def _analyze_with_google(self, image_path: str, prompt: str) -> str:
        """Analyze using Google Gemini."""
        import google.generativeai as genai
        from PIL import Image
        
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        image = Image.open(image_path)
        response = model.generate_content([prompt, image])
        
        return response.text
    
    def generate_text(self, prompt: str, system_prompt: str = None) -> str:
        """Generate text without image (for report summarization).
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            
        Returns:
            Generated text
        """
        if self.provider == "llava":
            return self._generate_text_llava(prompt, system_prompt)
        elif self.provider == "openai":
            return self._generate_text_openai(prompt, system_prompt)
        elif self.provider == "azure":
            return self._generate_text_azure(prompt, system_prompt)
        else:
            # Fallback to Llava for text generation
            return self._generate_text_llava(prompt, system_prompt)
    
    def _generate_text_llava(self, prompt: str, system_prompt: str = None) -> str:
        """Generate text using Llava/Llama."""
        import httpx
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": "hosted_vllm/Llama-3.1-70B-Instruct",
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.3
        }
        
        url = f"{self.base_url}/v1/chat/completions"
        
        try:
            with httpx.Client(timeout=120.0, verify=False) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Text generation error: {e}")
            raise
    
    def _generate_text_openai(self, prompt: str, system_prompt: str = None) -> str:
        """Generate text using OpenAI."""
        from openai import OpenAI
        
        client = OpenAI(api_key=self.api_key)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=4096
        )
        
        return response.choices[0].message.content
    
    def _generate_text_azure(self, prompt: str, system_prompt: str = None) -> str:
        """Generate text using Azure OpenAI."""
        from openai import AzureOpenAI
        
        client = AzureOpenAI(
            api_key=self.api_key,
            api_version=os.getenv("AZURE_API_VERSION", "2024-12-01-preview"),
            azure_endpoint=self.base_url
        )
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            messages=messages,
            max_tokens=4096
        )
        
        return response.choices[0].message.content
