"""AI Client for patch attribution using SmolVLM"""
import aiohttp
import asyncio
import json
import os
import re
from typing import Optional, Tuple


class XAIClient:
    def __init__(self, base_url: Optional[str] = None):
        if base_url is None:
            base_url = os.getenv("LLAMA_SERVER_URL", "http://host.docker.internal:8080")
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.system_prompt = (
            "You are an explainable-AI assistant scoring cropped patches from emergency footage. "
            "Always respond with compact JSON shaped as {\"score\": <0-1 float>, \"summary\": \"short justification\"}. "
            "The summary must explain what visual evidence justified the score (blood, fire, injured person, etc.)."
        )

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def score_patch(
        self,
        patch_base64: str,
        row: int,
        col: int,
        grid_size: int,
        scene_context: str = "",
    ) -> dict:
        instruction = (
            "Analyse ce patch issu d'une scène d'urgence. "
            "Précise si l'on voit du sang, une blessure, une chute, un feu, de la fumée, des armes ou une menace similaire. "
            f"Contexte scène: {scene_context or 'aucun'}. "
            f"Position: ligne {row + 1} / colonne {col + 1} sur une grille {grid_size}×{grid_size}. "
            "Retourne uniquement le JSON demandé."
        )
        raw = await self._send_chat_completion(instruction, patch_base64)
        data = self._extract_json_dict(raw)
        score: float
        summary: str
        if data:
            score = float(data.get("score", 0.0))
            summary = str(data.get("summary", "")).strip()
        else:
            summary, score = self._build_summary_from_text(raw)
        if not summary:
            summary, _ = self._build_summary_from_text(raw)
        score = max(0.0, min(1.0, score))
        return {"score": score, "summary": summary.strip()[:200]}

    def _extract_json_dict(self, raw: str) -> Optional[dict]:
        if not raw:
            return None
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
            if "```" in cleaned:
                cleaned = cleaned.split("```", 1)[0].strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                snippet = cleaned[start : end + 1]
                try:
                    return json.loads(snippet)
                except json.JSONDecodeError:
                    return None
        return None

    def _build_summary_from_text(self, raw: str) -> Tuple[str, float]:
        text = (raw or "").strip()
        lowered = text.lower()
        cues: list[str] = []
        cues_score = 0.0

        def register(keywords, message, weight):
            nonlocal cues_score
            if any(keyword in lowered for keyword in keywords):
                if message not in cues:
                    cues.append(message)
                cues_score = max(cues_score, weight)
        register(["blood", "bleed", "injur", "wound", "trauma"], "Présence possible de sang / blessure", 0.95)
        register(["fire", "flame", "burn", "smoke"], "Feu ou fumée détecté", 0.9)
        register(["weapon", "gun", "knife", "machete"], "Objet potentiellement dangereux", 0.85)
        register(["unconscious", "collapsed", "lifeless", "lying"], "Personne immobile ou inconsciente", 0.8)
        register(["trapped", "pinned", "stuck"], "Personne coincée", 0.75)
        register(["blood stain", "bloody"], "Tache de sang visible", 0.92)
        register(["calm", "no threat", "safe", "clear"], "Aucun danger évident", 0.2)

        summary = "; ".join(cues)
        if not summary:
            if text:
                summary = text.splitlines()[0][:160]
            else:
                summary = "Observation critique enregistrée"

        if cues_score == 0.0:
            cues_score = 0.25 if "no" not in lowered else 0.1

        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
        if match:
            try:
                val = float(match.group(1))
                if val > 1.0:
                    if val <= 100:
                        val /= 100.0
                    else:
                        val /= 10.0
                cues_score = max(cues_score, val)
            except ValueError:
                pass

        return summary, cues_score

    async def _send_chat_completion(self, instruction: str, image_base64: str, max_tokens: int = 200) -> str:
        session = await self.get_session()
        payload = {
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": self.system_prompt}],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruction},
                        {"type": "image_url", "image_url": {"url": image_base64}},
                    ],
                },
            ],
        }
        try:
            async with session.post(
                f"{self.base_url}/v1/chat/completions", json=payload, timeout=45
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"SmolVLM error {response.status}: {error_text}")
                data = await response.json()
                return data["choices"][0]["message"]["content"]
        except asyncio.TimeoutError as exc:
            raise RuntimeError("SmolVLM patch scoring timed out") from exc


ai_client = XAIClient()
