from __future__ import annotations

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

        self._address = resources_filtered[0]
        osc = self._rm.open_resource(self._address)
        assert isinstance(osc, visa.resources.MessageBasedResource)
        self._osc: visa.resources.MessageBasedResource = osc

        self._osc.read_termination = "\n"
        self._osc.write_termination = "\n"
        self._osc.timeout = 1000

        # close it to avoid leaving it open, the user can open it when needed
        self.close()

    @property
    def osc(self):
        return self._osc

    @property
    def is_open(self) -> bool:
        # TODO: is there a better way to check this?
        return self._osc._session is not None

    def open(self):
        # It's not okay to open an already open connection
        if not self.is_open:
            self._osc.open()

    def close(self):
        # It's okay to close an already closed connection
        self._osc.close()

    def __enter__(self) -> Scope:
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def identity(self) -> str:
        return self.query("*IDN?")

    def write(self, message: str, *args, **kwargs) -> int:
        self.open()
        return self._osc.write(message, *args, **kwargs)

    def query(self, message: str, *args, **kwargs) -> str:
        self.open()
        return self._osc.query(message, *args, **kwargs).rstrip("\n")

    def query_binary_values(self, message: str, *args, **kwargs):
        self.open()
        return self._osc.query_binary_values(message, *args, **kwargs)

    @property
    def trigger_type(self) -> str:
        return self.query(":TRIG:TYPE?")

    @trigger_type.setter
    def trigger_type(self, value: str):
        self.write(f":TRIG:TYPE {value}")

    @property
    def trigger_mode(self) -> str:
        return self.query(":TRIG:MODE?")

    @trigger_mode.setter
    def trigger_mode(self, value: str):
        allowed_values = ["NORMAL", "AUTO", "SINGLE", "FTRIG"]
        if value.upper() not in allowed_values:
            raise ValueError(f"Trigger mode must be one of '{allowed_values}' but got '{value}' instead")

        self.write(f":TRIG:MODE {value}")

    def stop(self):
        self.write(":TRIG:STOP")

    def run(self):
        self.write(":TRIG:RUN")

    @property
    def waveform_source(self) -> str:
        return self.query(":WAV:SOUR?")

    @waveform_source.setter
    def waveform_source(self, source: str):
        self.write(f":WAV:SOUR {source}")

    @property
    def waveform_source_channel(self) -> int | None:
        source = self.waveform_source
        if source.startswith("C"):
            return int(source[1:])
        return None

    @waveform_source_channel.setter
    def waveform_source_channel(self, channel: int):
        self.waveform_source = f"C{channel}"

    @property
    def acquisition_sequence(self) -> bool:
        return self.query("ACQ:SEQ?") == "ON"

    @acquisition_sequence.setter
    def acquisition_sequence(self, value: bool):
        self.write("ACQ:SEQ ON" if value else "ACQ:SEQ OFF")

    @property
    def acquisition_sequence_count(self) -> int:
        return int(self.query("ACQ:SEQ:COUNT?"))

    @acquisition_sequence_count.setter
    def acquisition_sequence_count(self, value: int):
        self.write(f"ACQ:SEQ:COUNT {value}")

    def data(self):
        return self.query_binary_values(":WAV:DATA?", datatype="B", is_big_endian=True)
