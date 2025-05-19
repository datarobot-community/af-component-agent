from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.crewai import CrewAIInstrumentor
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor

instrument_requests = RequestsInstrumentor().instrument()
instrument_aiohttp = AioHttpClientInstrumentor().instrument()
instrument_openai = OpenAIInstrumentor().instrument()
instrument_crewai = CrewAIInstrumentor().instrument()
