from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Startet den MCP-Server (Streamable HTTP) fuer MoneyPlan."

    def add_arguments(self, parser):
        parser.add_argument('--host', default=settings.MCP_SERVER_HOST)
        parser.add_argument('--port', type=int, default=settings.MCP_SERVER_PORT)

    def handle(self, *args, **options):
        if not settings.MCP_ACCESS_TOKEN:
            raise CommandError(
                "MCP_ACCESS_TOKEN ist nicht gesetzt. Bitte in der Umgebung/.env konfigurieren, "
                "z.B. mit: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )

        import uvicorn

        from mcp_server.asgi import application

        self.stdout.write(self.style.SUCCESS(
            f"MCP-Server startet auf {options['host']}:{options['port']} "
            f"(HTTPS erforderlich: {settings.MCP_REQUIRE_HTTPS})"
        ))
        uvicorn.run(application, host=options['host'], port=options['port'], log_level='info')
