import pyvisa as visa


class Scope:
    def __init__(self, name: str = "SDS7AA1D7R0092"):
        self._rm = visa.ResourceManager()
        resources = self._rm.list_resources()
        resources_filtered = [resource for resource in resources if name in resource]

        if len(resources_filtered) == 0:
            raise ValueError(f"No device found with name {name}. Devices: {resources}")
        if len(resources_filtered) > 1:
            raise ValueError(
                f"Multiple devices found with name {name}. Devices: {resources}"
            )

        osc = self._rm.open_resource(resources_filtered[0])
        assert isinstance(osc, visa.resources.MessageBasedResource)
        self._osc: visa.resources.MessageBasedResource = osc

        self._osc.read_termination = "\n"
        self._osc.write_termination = "\n"
        self._osc.timeout = 5000

        identifier = self._osc.query("*IDN?")
        print(f"Connected to '{identifier}' at '{self._osc!s}'")

    @property
    def osc(self):
        return self._osc

    def write(self, message: str, *args, **kwargs) -> int:
        return self._osc.write(message, *args, **kwargs)

    def query(self, message: str, *args, **kwargs) -> str:
        return self._osc.query(message, *args, **kwargs)
