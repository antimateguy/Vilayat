"""The LLMClient port, implemented with the Gemini API."""

import json

from google import genai
from google.genai import types

from infrastructure.gemini.sdk import SDK_ERRORS, describe, is_daily_quota_error
from ports.llm import JsonObject, LLMClient, LLMUnavailableError
from ports.usage import DailyLimitReachedError, RequestBudget

# The model is never given tools to call; saying so also silences an SDK notice.
_NO_TOOLS = types.AutomaticFunctionCallingConfig(disable=True)


class GeminiClient(LLMClient):
    """Adapter: turns the two port methods into Gemini API calls.

    Every failure (network, timeout, quota, an empty or malformed reply) becomes
    LLMUnavailableError, so callers handle one error and fall back. Each request
    is first counted against the model's daily budget; none is sent once the
    budget is spent.
    Temperature is 0, so the same prompt gives the same reply as far as the
    service allows; that keeps the evaluation repeatable.
    """

    def __init__(self, client: genai.Client, model: str, budget: RequestBudget) -> None:
        self._client = client
        self._model = model
        self._budget = budget

    @property
    def model_name(self) -> str:
        return self._model

    def generate_text(self, prompt: str) -> str:
        config = types.GenerateContentConfig(temperature=0, automatic_function_calling=_NO_TOOLS)
        return self._generate(prompt, config)

    def generate_json(self, prompt: str, schema: JsonObject) -> JsonObject:
        config = types.GenerateContentConfig(
            temperature=0,
            automatic_function_calling=_NO_TOOLS,
            response_mime_type="application/json",
            response_json_schema=dict(schema),
        )
        text = self._generate(prompt, config)
        try:
            reply = json.loads(text)
        except json.JSONDecodeError as error:
            raise LLMUnavailableError(f"{self._model} replied with invalid JSON") from error
        if not isinstance(reply, dict):
            raise LLMUnavailableError(f"{self._model} replied with JSON that is not an object")
        return reply

    def _generate(self, prompt: str, config: types.GenerateContentConfig) -> str:
        self._budget.spend()
        try:
            response = self._client.models.generate_content(
                model=self._model, contents=prompt, config=config
            )
        except SDK_ERRORS as error:
            if is_daily_quota_error(error):
                self._budget.use_up()
                raise DailyLimitReachedError(
                    self._model, self._budget.status().resets_at
                ) from error
            raise LLMUnavailableError(f"{self._model}: {describe(error)}") from error
        text = (response.text or "").strip()
        if not text:
            raise LLMUnavailableError(f"{self._model} returned no text")
        return text
