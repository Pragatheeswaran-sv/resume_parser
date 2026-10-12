import json
import logging
from typing import Any, Dict, List, Optional, Union
from openai import OpenAI
from anthropic import Anthropic
import ollama

from db.connection import SessionLocal
from src.admin.models import Admin
from src.utils.helper import (
    decrypt_data,
    record_model_usage,
    select_available_model,
)

logger = logging.getLogger(__name__)


class LLMService:
    """Service class for Large Language Model integrations."""

    def call_llm(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        system_prompt: str = "You only return JSON",
        is_json: bool = True,
        # max_tokens: int = 2000,
        # temperature: float = 0.0,
        max_retries: int = 3,
    ) -> Union[Dict[str, Any], str]:
        """
        Unified LLM call function with:
        - Automatic DB model configuration & priority fallback
        - Support for OpenAI, Claude (Anthropic), and Ollama
        - Automatic token usage recording
        - Safe JSON extraction & parsing (if is_json=True)
        """
        db = SessionLocal()
        try:
            admin = db.query(Admin).filter(Admin.is_active == True).first()
            if not admin:
                raise Exception("No active admin found for LLM configuration")
            admin_id = admin.admin_id
            admin_name = admin.name
        finally:
            db.close()

        # Construct messages list if prompt is passed
        if messages is None:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt or ""},
            ]

        failed_ids = set()
        last_error = None

        for attempt in range(max_retries):
            model_info = select_available_model(admin_id, exclude_ids=failed_ids)
            if not model_info:
                break

            model_config_id = model_info.get("model_config_id")
            model = model_info.get("model_name", "ollama").lower()
            version = model_info.get("version_name", "llama3").lower()
            base_url = model_info.get("base_url")
            api_key = decrypt_data(model_info.get("apikey"))

            try:
                content = ""

                # ---------------- 1. OpenAI ----------------
                if model == "openai":
                    if not api_key:
                        raise Exception("OpenAI API key not configured")
                    client = OpenAI(api_key=api_key, base_url=base_url)
                    
                    kwargs = {
                        "model": version,
                        "messages": messages,
                        # "temperature": temperature,
                    }
                    if is_json:
                        kwargs["response_format"] = {"type": "json_object"}

                    response = client.chat.completions.create(**kwargs)
                    content = response.choices[0].message.content.strip()
                    record_model_usage(model_config_id, response.usage.total_tokens, admin_name)

                # ---------------- 2. Claude (Anthropic) ----------------
                elif model == "claude":
                    if not api_key:
                        raise Exception("Claude API key not configured")
                    client = Anthropic(api_key=api_key)

                    # Extract user messages without the system prompt for Anthropic
                    user_msgs = [m for m in messages if m.get("role") != "system"]
                    anthropic_system = next((m["content"] for m in messages if m.get("role") == "system"), system_prompt)

                    response = client.messages.create(
                        model=version,
                        # max_tokens=max_tokens,
                        system=anthropic_system,
                        messages=user_msgs,
                    )
                    content = response.content[0].text.strip()
                    total_tokens = response.usage.input_tokens + response.usage.output_tokens
                    record_model_usage(model_config_id, total_tokens, admin_name)

                # ---------------- 3. Ollama ----------------
                else:
                    chat_kwargs = {
                        "model": version,
                        "messages": messages,
                        # "options": {"temperature": temperature},
                    }
                    if is_json:
                        chat_kwargs["format"] = "json"

                    response = ollama.chat(**chat_kwargs)
                    content = response["message"]["content"].strip()

                # ---------------- Return response ----------------
                if not is_json:
                    return content

                # Parse JSON safely
                start = content.find("{")
                end = content.rfind("}") + 1
                if start == -1 or end == 0:
                    raise ValueError("No valid JSON object found in model response")

                return json.loads(content[start:end])

            except Exception as call_err:
                last_error = call_err
                logger.warning("[call_llm] attempt %d failed on model '%s': %s", attempt + 1, model, call_err)
                failed_ids.add(model_config_id)
                continue

        raise Exception(f"All AI model attempts failed. Last error: {last_error}")


LLMIntegration = LLMService
llm_service = LLMService()

# Backward-compatible function reference
call_llm = llm_service.call_llm