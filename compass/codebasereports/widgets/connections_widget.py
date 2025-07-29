from compass.codebasereports.widgets import BaseWidget
from compass.integrations.integrations import get_codebase_reports_providers
from mvp.models import DataProviderConnection, ModuleChoices
from mvp.services import ConnectedIntegrationsService


class ConnectionsWidget(BaseWidget):
    MODULES_COMPLIANCE = [
        ModuleChoices.OPEN_SOURCE,
        ModuleChoices.CODE_SECURITY,
        ModuleChoices.CYBER_SECURITY,
    ]

    MODULES_PRODUCT = [
        ModuleChoices.CODE_QUALITY,
        ModuleChoices.PROCESS,
        ModuleChoices.TEAM,
    ]

    def get_widgets(self, modules=None):
        connections = self.get_connections(modules)

        active_connections = self.filter_active_connections(connections)
        updated_at = self.get_most_recent_date(active_connections)

        return {
            "connections": active_connections,
            "modules": self.get_modules(connections),
            "updated_at": int(updated_at.timestamp()) if updated_at else None,
        }

    def get_connections(self, modules=None):
        providers = get_codebase_reports_providers()
        if modules:
            providers = [provider for provider in providers if set(provider.modules) & set(modules)]

        connections = DataProviderConnection.objects.filter(
            organization=self.organization,
            provider__in=providers,
            data__isnull=False,
        ).prefetch_related("provider")

        return [
            connection for connection in connections if ConnectedIntegrationsService.is_connection_connected(connection)
        ]

    def filter_active_connections(self, connections):
        active = {}
        for connection in connections:
            if connection.data is None:
                continue

            active[connection.provider.name] = connection.last_fetched_at

        return active

    def get_connected_modules(self, connections):
        modules = set()
        for connection in connections:
            if connection.data is not None:
                modules.update(connection.provider.modules)

        return list(modules)

    def get_modules(self, connections):
        connected_modules = self.get_connected_modules(connections)

        icon_path = "images/icons/module-{icon}.png"
        return {
            "Product": {
                "code_quality": {
                    "name": "Code Quality",
                    "icon": icon_path.format(icon="code-quality"),
                    "connected": ModuleChoices.CODE_QUALITY in connected_modules,
                },
                "process": {
                    "name": "Process",
                    "icon": icon_path.format(icon="process"),
                    "connected": ModuleChoices.PROCESS in connected_modules,
                },
                "team": {
                    "name": "Team",
                    "icon": icon_path.format(icon="team"),
                    # GitHub activates Team too since we can get developers' activity
                    "connected": ModuleChoices.TEAM in connected_modules,
                },
            },
            "Compliance": {
                "open_source": {
                    "name": "Open Source",
                    "icon": icon_path.format(icon="open-source"),
                    "connected": ModuleChoices.OPEN_SOURCE in connected_modules,
                },
                "code_security": {
                    "name": "Code Security",
                    "icon": icon_path.format(icon="code-security"),
                    "connected": ModuleChoices.CODE_SECURITY in connected_modules,
                },
                "cyber_security": {
                    "name": "Cyber Security",
                    "icon": icon_path.format(icon="cyber-security"),
                    "connected": ModuleChoices.CYBER_SECURITY in connected_modules,
                },
            },
        }

    def get_most_recent_date(self, connections):
        updated_at = None
        for date in connections.values():
            if not date:
                continue

            if updated_at is None or date > updated_at:
                updated_at = date

        return updated_at
