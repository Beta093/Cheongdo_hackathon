"""Opt-in traces without automatic body/header/prompt or exception capture."""
import os
import time


def configure_telemetry(app) -> None:
    connection = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if not connection:
        return
    from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": "gamjaba"}))
    provider.add_span_processor(BatchSpanProcessor(AzureMonitorTraceExporter(
        connection_string=connection)))
    tracer = provider.get_tracer("gamjaba.http")
    app.state.telemetry_provider = provider

    @app.middleware("http")
    async def trace_request(request, call_next):
        started = time.time_ns()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            # Route template only. Never include session IDs, query, body, URLs or exceptions.
            route = getattr(request.scope.get("route"), "path", "unmatched")
            span = tracer.start_span("http.request", start_time=started, attributes={
                "http.route": route, "http.request.method": request.method,
                "http.response.status_code": status})
            span.end()

    app.add_event_handler("shutdown", provider.shutdown)
