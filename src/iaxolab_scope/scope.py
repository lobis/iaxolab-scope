from __future__ import annotations

import pyvisa as visa

from iaxolab_scope.waveform import parse_waveform_preamble_header


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
        self._osc.timeout = 2000
        self._osc.chunk_size = 20 * 1024 * 1024

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

    @property
    def waveform_max_points(self) -> int:
        return int(self.query(":WAV:MAXP?"))

    @waveform_source_channel.setter
    def waveform_source_channel(self, channel: int):
        self.waveform_source = f"C{channel}"

    @property
    def waveform_start(self) -> int:
        return int(self.query(":WAV:START?"))

    @waveform_start.setter
    def waveform_start(self, value: int):
        self.write(f":WAV:START {value}")

    @property
    def waveform_points(self) -> int:
        return int(self.query(":WAV:POINT?"))

    @waveform_points.setter
    def waveform_points(self, value: int):
        self.write(f":WAV:POINT {value}")

    @property
    def waveform_sequence(self) -> (int, int):
        data = self.query(":WAV:SEQUENCE?")
        print(data)
        return tuple(map(int, data.split(",")))

    @waveform_sequence.setter
    def waveform_sequence(self, value: (int, int)):
        self.write(f":WAV:SEQUENCE {value[0]},{value[1]}")

    @property
    def _waveform_preamble_bytes(self) -> bytes:
        self.write(":WAV:PRE?")
        preamble = self._osc.read_raw()
        return preamble[preamble.find(b'#') + 11:]

    @property
    def waveform_preamble(self) -> dict:
        return parse_waveform_preamble_header(self._waveform_preamble_bytes)

    @property
    def waveform_width(self) -> str:
        return self.query(":WAV:WIDTH?")

    @waveform_width.setter
    def waveform_width(self, value: str):
        self.write(f":WAV:WIDTH {value}")

    @property
    def acquire_sequence(self) -> bool:
        return self.query("ACQ:SEQ?") == "ON"

    @acquire_sequence.setter
    def acquire_sequence(self, value: bool):
        self.write("ACQ:SEQ ON" if value else "ACQ:SEQ OFF")

    @property
    def acquire_points(self) -> int:
        return int(float(self.query("ACQ:POINTS?")))  # float to handle scientific notation

    @property
    def acquire_memory_depth(self) -> str:
        return self.query("ACQ:MDEPTH?")

    @acquire_memory_depth.setter
    def acquire_memory_depth(self, value: str):
        # values such as "5k", "10k", "1M", etc. (depends on the model)
        self.write(f"ACQ:MDEPTH {value}")
        # check if the value was set correctly
        if self.acquire_memory_depth != value:
            raise ValueError(
                f"Failed to set memory depth to {value}. "
                f"Current value: {self.acquire_memory_depth}. "
                f"The requested value may not be available on this model"
            )

    @property
    def acquire_number(self) -> int:
        return int(self.query("ACQ:NUMA?"))

    @property
    def acquire_sequence_count(self) -> int:
        return int(self.query("ACQ:SEQ:COUNT?"))

    @property
    def trigger_edge_source(self) -> str:
        return self.query("TRIG:A:EDGE:SOURCE?")

    @trigger_edge_source.setter
    def trigger_edge_source(self, value: str):
        self.write(f"TRIG:A:EDGE:SOURCE {value}")

    @property
    def trigger_edge_source_channel(self) -> int | None:
        source = self.trigger_edge_source
        if source.startswith("C"):
            return int(source[1:])
        return None

    @property
    def trigger_edge_slope(self) -> str:
        return self.query("TRIG:A:EDGE:SLOPE?")

    @trigger_edge_slope.setter
    def trigger_edge_slope(self, value: str):
        self.write(f"TRIG:A:EDGE:SLOPE {value}")

    @trigger_edge_source_channel.setter
    def trigger_edge_source_channel(self, channel: int):
        self.trigger_edge_source = f"C{channel}"

    @acquire_sequence_count.setter
    def acquire_sequence_count(self, value: int):
        self.write(f"ACQ:SEQ:COUNT {value}")

    @property
    def timebase_scale(self) -> float:
        return float(self.query("TIMEBASE:SCALE?"))

    @timebase_scale.setter
    def timebase_scale(self, value: float):
        self.write(f"TIMEBASE:SCALE {value}")

    @property
    def timebase_delay(self) -> float:
        return float(self.query("TIMEBASE:DELAY?"))

    @timebase_delay.setter
    def timebase_delay(self, value: float):
        self.write(f"TIMEBASE:DELAY {value:.2E}")

    def query_channel_scale(self, channel: int) -> float:
        return float(self.query(f"CH{channel}:SCALE?"))

    def set_channel_scale(self, channel: int, value: float):
        self.write(f"CH{channel}:SCALE {value:.2E}")

    def data_raw(self) -> bytes:
        self.write(":WAV:DATA?")
        return self._osc.read_raw()
