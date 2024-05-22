import math
import struct

TDIV_ENUM = [100e-12, 200e-12, 500e-12,
             1e-9, 2e-9, 5e-9, 10e-9, 20e-9, 50e-9, 100e-9, 200e-9, 500e-9,
             1e-6, 2e-6, 5e-6, 10e-6, 20e-6, 50e-6, 100e-6, 200e-6, 500e-6,
             1e-3, 2e-3, 5e-3, 10e-3, 20e-3, 50e-3, 100e-3, 200e-3, 500e-3,
             1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]


def parse_waveform_preamble_header(preamble: bytes) -> dict:
    data_width = preamble[0x20:0x21 + 1]  # 01-16bit,00-8bit
    data_order = preamble[0x22:0x23 + 1]  # 01-MSB,00-LSB
    WAVE_ARRAY_1 = preamble[0x3c:0x3f + 1]
    wave_array_count = preamble[0x74:0x77 + 1]
    first_point = preamble[0x84:0x87 + 1]
    sp = preamble[0x88:0x8b + 1]
    one_fram_pts = preamble[0x74:0x77 + 1]  # pts of single frame,maybe bigger than 12.5M
    read_frame = preamble[0x90:0x93 + 1]  # all sequence frames number return by this command
    sum_frame = preamble[0x94:0x97 + 1]  # all sequence frames number acquired
    v_scale = preamble[0x9c:0x9f + 1]
    v_offset = preamble[0xa0:0xa3 + 1]
    code_per_div = preamble[0xa4:0Xa7 + 1]
    adc_bit = preamble[0xac:0Xad + 1]
    sn = preamble[0xae:0xaf + 1]
    interval = preamble[0xb0:0xb3 + 1]
    delay = preamble[0xb4:0xbb + 1]
    tdiv = preamble[0x144:0x145 + 1]
    probe = preamble[0x148:0x14b + 1]

    width = struct.unpack('h', data_width)[0]
    order = struct.unpack('h', data_order)[0]
    data_bytes = struct.unpack('i', WAVE_ARRAY_1)[0]
    point_num = struct.unpack('i', wave_array_count)[0]
    fp = struct.unpack('i', first_point)[0]
    sp = struct.unpack('i', sp)[0]
    sn = struct.unpack('h', sn)[0]
    one_fram_pts = struct.unpack('i', one_fram_pts)[0]
    read_frame = struct.unpack('i', read_frame)[0]
    sum_frame = struct.unpack('i', sum_frame)[0]
    interval = struct.unpack('f', interval)[0]
    delay = struct.unpack('d', delay)[0]
    tdiv_index = struct.unpack('h', tdiv)[0]
    probe = struct.unpack('f', probe)[0]
    vdiv = struct.unpack('f', v_scale)[0] * probe
    offset = struct.unpack('f', v_offset)[0] * probe
    code = struct.unpack('f', code_per_div)[0]
    adc_bit = struct.unpack('h', adc_bit)[0]
    tdiv = TDIV_ENUM[tdiv_index]

    # return vdiv, offset, interval, delay, tdiv, code, adc_bit, one_fram_pts, read_frame, sum_frame

    # return exactly these fields as dict
    return {
        "vdiv": vdiv,
        "offset": offset,
        "interval": interval,
        "delay": delay,
        "tdiv": tdiv,
        "code": code,
        "adc_bit": adc_bit,
        "one_fram_pts": one_fram_pts,
        "read_frame": read_frame,
        "sum_frame": sum_frame
    }


def read_single_frame(scope, frame_number: int):
    scope.waveform_start = 0
    scope.waveform_points = 0
    scope.waveform_sequence = (frame_number, 0)
    preamble = scope.waveform_preamble

    points_one_frame = preamble["one_fram_pts"]
    adc_bytes = preamble["adc_bit"]
    points_max = scope.waveform_max_points

    if points_one_frame > points_max:
        scope.waveform_points = points_max

    if adc_bytes > 8:
        scope.waveform_width = "WORD"

    read_times = math.ceil(points_one_frame / points_max)
    data = b""

    for i in range(read_times):
        start = i * points_max
        scope.waveform_start = start
        scope.write(":WAV:DATA?")
        block_data = scope._osc.read_raw().rstrip()
        block_start = block_data.find(b'#')
        data_digit = int(block_data[block_start + 1: block_start + 2])
        data_start = block_start + 2 + data_digit
        data += block_data[data_start:]

    struct_string = "%dh" if adc_bytes > 8 else "%db"
    data = struct.unpack(struct_string % len(data), data)

    voltage_values = []
    time_values = []

    vdiv = preamble["vdiv"]
    offset = preamble["offset"]
    tdiv = preamble["tdiv"]
    interval = preamble["interval"]
    delay = preamble["delay"]
    code = preamble["code"]

    HORI_NUM = 10  # number of horizontal divisions (model specific?)

    for i in range(len(data)):
        voltage_values.append(data[i] / code * float(vdiv) - float(offset))
        time_values.append(-(float(tdiv) * HORI_NUM / 2) + i * interval + delay)

    return time_values, voltage_values
