"""Tracing: where a worker's spans are sent, and the prices the tracing tool uses."""

import json
import re
import urllib.request
from typing import Any

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from docintel.extraction.prices import Prices

# Phoenix files every trace under this project.
PROJECT_NAME = "docintel"

MODELS_QUERY = """
query ($after: String) {
  generativeModels(first: 500, after: $after) {
    pageInfo { hasNextPage endCursor }
    edges { node { id name kind } }
  }
}
"""
CREATE_MODEL = """
mutation ($input: CreateModelMutationInput!) {
  createModel(input: $input) { model { id } }
}
"""
UPDATE_MODEL = """
mutation ($input: UpdateModelMutationInput!) {
  updateModel(input: $input) { model { id } }
}
"""


class PhoenixError(Exception):
    """Phoenix refused a request, and said why."""


def make_tracer_provider(phoenix_url: str, api_key: str) -> TracerProvider:
    """Sends spans to Phoenix in batches, from a thread of their own.

    A batch that cannot be sent is dropped and the exporter logs it, so a
    contract is processed the same way whether the tracing tool is up or not.
    """
    resource = Resource.create(
        {"service.name": "docintel-worker", "openinference.project.name": PROJECT_NAME}
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=f"{phoenix_url}/v1/traces",
        headers={"authorization": f"Bearer {api_key}"},
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def write_prices(
    phoenix_url: str, api_key: str, price_list: dict[str, Prices]
) -> list[str]:
    """Gives Phoenix each model's list prices, so it costs an answer as the report does.

    Phoenix works out a span's cost from its tokens and a price it holds for the
    model; it ignores a cost written on the span. A model that already has a
    price of ours is updated, not added twice.

    Returns:
        What was done, one line for each model.
    """
    custom_models = read_custom_models(phoenix_url, api_key)
    done = []
    for model, prices in price_list.items():
        fields = {
            "name": model,
            "namePattern": f"^{re.escape(model)}$",
            "costs": [
                {
                    "tokenType": "input",
                    "kind": "PROMPT",
                    "costPerMillionTokens": float(prices.input),
                },
                {
                    "tokenType": "cache_read",
                    "kind": "PROMPT",
                    "costPerMillionTokens": float(prices.cached_input),
                },
                {
                    "tokenType": "output",
                    "kind": "COMPLETION",
                    "costPerMillionTokens": float(prices.output),
                },
            ],
            "startTime": f"{prices.read_on.isoformat()}T00:00:00Z",
        }
        if model in custom_models:
            fields["id"] = custom_models[model]
            ask_phoenix(phoenix_url, api_key, UPDATE_MODEL, {"input": fields})
            done.append(f"Updated the prices of {model}, read on {prices.read_on}.")
        else:
            fields["modelType"] = "LLM"
            ask_phoenix(phoenix_url, api_key, CREATE_MODEL, {"input": fields})
            done.append(f"Added the prices of {model}, read on {prices.read_on}.")
    return done


def read_custom_models(phoenix_url: str, api_key: str) -> dict[str, str]:
    """Gives the id of each model Phoenix holds a price of ours for, by its name."""
    ids = {}
    after = None
    while True:
        reply = ask_phoenix(phoenix_url, api_key, MODELS_QUERY, {"after": after})
        page = reply["generativeModels"]
        for edge in page["edges"]:
            # The others are Phoenix's own price table.
            if edge["node"]["kind"] == "CUSTOM":
                ids[edge["node"]["name"]] = edge["node"]["id"]
        if not page["pageInfo"]["hasNextPage"]:
            return ids
        after = page["pageInfo"]["endCursor"]


def ask_phoenix(
    phoenix_url: str, api_key: str, query: str, variables: dict[str, Any]
) -> dict[str, Any]:
    """Sends one query to Phoenix's GraphQL API and returns its data.

    Raises:
        PhoenixError: Phoenix answered with errors.
    """
    request = urllib.request.Request(
        f"{phoenix_url}/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        reply = json.load(response)
    if reply.get("errors"):
        raise PhoenixError(reply["errors"][0]["message"])
    data: dict[str, Any] = reply["data"]
    return data
