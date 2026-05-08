# Observability

- **Sentry:** set `SENTRY_DSN` on API and workers (`citationpulse.core.observability`).
- **OpenTelemetry:** set `OTEL_EXPORTER_OTLP_ENDPOINT` for traces to Grafana Cloud.
- **Logs:** structured JSON via `python-json-logger` (wire Logtail/Datadog in production).

Suggested metrics (Grafana / Prometheus): `runs_per_minute`, `citations_captured`, `engine_error_rate`, `cost_per_run`, `sov_volatility`.
