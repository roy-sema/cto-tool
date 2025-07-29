from importlib import import_module


class IntegrationFactory:
    def get_integration(self, provider_name):
        try:
            integration = getattr(
                import_module("compass.integrations.integrations"),
                f"{provider_name}Integration",
            )
        except AttributeError:
            raise ValueError(f"Integration for {provider_name} is not implemented.")

        return integration()
