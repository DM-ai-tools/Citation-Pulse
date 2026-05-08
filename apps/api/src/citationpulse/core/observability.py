from __future__ import annotations

import logging

from citationpulse.core.config import get_settings

_log = logging.getLogger(__name__)


def setup_observability() -> None:
    settings = get_settings()
    if settings.sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration

            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                environment=settings.environment,
                integrations=[FastApiIntegration()],
                traces_sample_rate=0.1 if settings.environment == "production" else 0.0,
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning("Sentry init skipped: %s", exc)
    if settings.otel_exporter_otlp_endpoint:
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            provider = TracerProvider(resource=Resource.create({"service.name": "citationpulse-api"}))
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
            )
            trace.set_tracer_provider(provider)
        except Exception as exc:  # noqa: BLE001
            _log.debug("OTel init skipped: %s", exc)
