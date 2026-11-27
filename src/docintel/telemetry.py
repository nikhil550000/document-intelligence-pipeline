"""Tracing: where a worker's spans are sent."""

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Phoenix files every trace under this project.
PROJECT_NAME = "docintel"


def make_tracer_provider(endpoint: str, api_key: str) -> TracerProvider:
    """Sends spans to the endpoint in batches, from a thread of their own.

    A batch that cannot be sent is dropped and the exporter logs it, so a
    contract is processed the same way whether the tracing tool is up or not.
    """
    resource = Resource.create(
        {"service.name": "docintel-worker", "openinference.project.name": PROJECT_NAME}
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=endpoint, headers={"authorization": f"Bearer {api_key}"}
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider
