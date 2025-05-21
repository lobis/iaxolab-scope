# -*- coding: utf-8 -*-
"""
Created on Mon May 19 10:45:01 2025

@author: Jorge Marqués García
@description:
    This script is designed to work with the Siglent SDS7000A series oscilloscopes.
    It connects to the oscilloscope, configures it for sequence mode, and captures
    multiple frames of data. The captured data is then processed and can be plotted
    or saved to a CSV file.

    More study is needed in the trigger configuration
"""

import pyvisa
import struct
import os
import time
import math
import os
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import gc

## Global Variables, need to check if they are correct
CHANNEL = "C1"
HORI_NUM = 10
TDIV_NUM = [100e-12, 200e-12, 500e-12, 1e-9, 2e-9, 5e-9, 10e-9, 20e-9, 50e-9, 100e-9, 200e-9, 500e-9, 
            1e-6, 2e-6, 5e-6, 10e-6, 20e-6, 50e-6, 100e-6, 200e-6, 500e-6,
            1e-3, 2e-3, 5e-3, 10e-3, 20e-3, 50e-3, 100e-3, 200e-3, 500e-3,
            1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]


def connect_to_scope(ip="169.254.19.70"):
    rm = pyvisa.ResourceManager()
    sds = rm.open_resource(f"TCPIP0::{ip}::INSTR")
    sds.timeout = 10000
    sds.chunk_size = 20 * 1024 * 1024  # 20 MB
    sds.write("*CLS")  # limpiar errores previos
    sds.clear()        # limpiar buffers

    return sds

def setup_scope_for_sequence(sds, channel="C1", vdiv=0.3, tdiv=2e-3, trig_level=0.1, seq_count=5):
    print("⚙️ Configurando osciloscopio...")
    ch = channel[-1]
    sds.write("*CLS")  # Limpia errores previos
    sds.write(":STOP")  # Detiene cualquier adquisición activa
    sds.write(f":CHAN{ch}:STAT ON")
    sds.write(f":CHAN{ch}:SCAL {vdiv}")
    sds.write(f":TIM:SCAL {tdiv}")
    sds.write(":ACQ:MODE SEQ")
    sds.write(":ACQ:POIN 1.25E08")
    sds.write(f":ACQ:SEQ:COUN {seq_count}")
    sds.write(":TRIG:MODE SING")
    sds.write(":TRIG:TYPE EDGE")
    sds.write(f":TRIG:EDGE:SOUR {channel}")
    sds.write(":TRIG:EDGE:SLOP POS")
    sds.write(f"TRIG:EDGE:LEV {trig_level}")

    print(f"✅ Osciloscopio listo: Esperando {seq_count} disparos en modo secuencia...")

    # Inicializamos DataFrame vacío para acumular los datos
    df_frames = pd.DataFrame(columns=["timestamp", "Voltaje", "Tiempo"])
    return df_frames

def wait_for_trigger(sds):
    while True:
        status = sds.query(":TRIG:STAT?").strip()
        if status == "Stop":
            print("🎯 Adquisición completa.")
            break
        time.sleep(0.5)

def get_preamble(sds):
    sds.write(":WAV:PRE?")
    pre = sds.read_raw()
    preamble = pre[pre.find(b'#') + 11:]
    # Extrae parámetros básicos
    interval = struct.unpack('f', preamble[0xB0:0xB4])[0]
    delay = struct.unpack('d', preamble[0xB4:0xBC])[0]
    tdiv_idx = struct.unpack('h', preamble[0x144:0x146])[0]

    tdiv = TDIV_NUM[tdiv_idx]
    vdiv = struct.unpack('f', preamble[0x9C:0xA0])[0]
    offset = struct.unpack('f', preamble[0xA0:0xA4])[0]
    code = struct.unpack('f', preamble[0xA4:0xA8])[0]
    adc_bit = struct.unpack('h', preamble[0xAC:0xAE])[0]
    one_frame_pts = struct.unpack('i', preamble[0x74:0x78])[0]
    sum_frame = struct.unpack('i', preamble[0x94:0x98])[0]
    read_frame = struct.unpack('i',preamble[0x90:0x93+1])[0]
    
    return {
        "interval": interval, "delay": delay, "tdiv": tdiv, "vdiv": vdiv,
        "offset": offset, "code": code, "adc_bit": adc_bit,
        "one_frame_pts": one_frame_pts, "sum_frame": sum_frame,
        "header": preamble, "read_frame": read_frame
    }



def main_time_stamp_deal(time):
    seconds = time[0x00:0x08]   ## type:long double
    minutes = time[0x08:0x09] ## type:char
    hours = time[0x09:0x0a] ## type:char
    days = time[0x0a:0x0b] ## type:char
    months = time[0x0b:0x0c] ## type:char
    year = time[0x0c:0x0e] ## type:short
    seconds = struct.unpack('d',seconds)[0]
    minutes = struct.unpack('c', minutes)[0]
    hours = struct.unpack('c', hours)[0]
    days = struct.unpack('c', days)[0]
    months = struct.unpack('c', months)[0]
    year = struct.unpack('h', year)[0]
    months = int.from_bytes(months, byteorder='big', signed=False)
    days = int.from_bytes(days, byteorder='big', signed=False)
    hours = int.from_bytes(hours, byteorder='big', signed=False)
    minutes = int.from_bytes(minutes, byteorder='big', signed=False)
    try:
        base_time = datetime.datetime(year, months, days, hours, minutes)
        full_time = base_time + datetime.timedelta(seconds=seconds)
        return full_time
    except Exception as e:
         print(f"❌ Error parsing timestamp: {e}")
         return None

def read_sequence_raw_frames(sds, channel="C1"):
    ##Setup sequence
    sds.write(f":WAV:SOUR {channel}")
    sds.write(":WAV:STAR 0")
    sds.write(":WAV:INT 1")
    sds.write(":WAV:POIN 0")
    sds.write(":WAV:WIDT BYTE")  # 8-bit
    sds.write(":WAVeform:SEQUence 0,0")
    
    
    info = get_preamble(sds)
    interval = info["interval"]
    delay = info["delay"]
    vdiv = info["vdiv"]
    offset = info["offset"]
    code = info["code"]
    one_frame_pts = info["one_frame_pts"]
    total_frames = info["sum_frame"]
    recv = info["header"]
    read_frame = info["read_frame"]
    tdiv = info["tdiv"]
    time_stamps_raw = recv[346:]
    read_times = math.ceil(total_frames/read_frame)
    # print("Read times")
    # print(read_times)
    # print("Read frame")   #Only for debuging 
    # print(read_frame)
    
    for i in range(0,read_times):
        sds.write(":WAVeform:SEQUence {},{}".format(0,read_frame*i+1)) #First sequence acquisition
        if i+1 == read_times:     #frame num of last read time
            read_frame = total_frames -(read_times-1)*read_frame
        info_i = get_preamble(sds)                  #get preamble for each sequence acquisition
        recv_i = info_i["header"]
        tmstp = recv_i[346:]
        
        if info_i["adc_bit"] > 8:
            sds.write(":WAVeform:WIDTh WORD")
        sds.write(":WAVeform:DATA?")        #get data for each sequence acquisition
        raw = sds.read_raw().rstrip()
        block_start = raw.find(b'#')
        data_digit = int(raw[block_start + 1:block_start+2])
        data_start = block_start + 2 + data_digit
        data = raw[data_start:]
        
        for j in range(0,read_frame):
            time = tmstp[16*j:16*(j+1)]
            timestamp = main_time_stamp_deal(time)
            if info_i["adc_bit"] > 8:
                start = int(j * one_frame_pts*2)
                end = int((j + 1) * one_frame_pts*2)
                convert_data = struct.unpack("%dh" % one_frame_pts, data[start:end])
            else:
                start = int(j*one_frame_pts)
                end = int((j+1)*one_frame_pts)
                convert_data = struct.unpack("%db" % one_frame_pts, data[start:end])
            
            volt_value = [val/code*float(vdiv)-float(offset) for val in convert_data]
            time_value = [-(float(tdiv)*HORI_NUM/2)+idx*interval+delay for idx in range(len(convert_data))]
            df_frames.loc[len(df_frames)] = [timestamp, volt_value, time_value]
            del volt_value,time_value,convert_data
            gc.collect()
    del data
    gc.collect()
    return df_frames
                


def plot_specified_frame_from_df(df_frames, frame_number):
    """
    Dibuja el frame especificado usando los datos almacenados en el DataFrame.
    frame_number es el índice (empezando en 0).
    """
    if frame_number < 0 or frame_number >= len(df_frames):
        print("❌ Frame fuera de rango.")
        return

    row = df_frames.iloc[frame_number]
    time_axis = row["Tiempo"]
    volt = row["Voltaje"]
    timestamp = row["timestamp"]

    plt.figure(figsize=(8, 4))
    plt.plot(time_axis, volt, label=f"Frame {frame_number} ({timestamp})")
    plt.title(f"🔬 Frame {frame_number} - {timestamp}")
    plt.xlabel("Tiempo (s)")
    plt.ylabel("Voltaje (V)")
    plt.grid(True)
    plt.legend()
    plt.show()

def plot_all_frames(df_frames):
    """
    Dibuja todos los frames almacenados en el DataFrame.
    """
    for i in range(len(df_frames)):
        plot_specified_frame_from_df(df_frames, i)

def save_frames_to_csv(df_frames, filename="frames.csv"):
    """
    Guarda el DataFrame de frames en un archivo CSV.
    Las columnas de listas se guardan como strings.
    """
    df_frames.to_csv(filename, index=False)
    print(f"✅ Datos guardados en {filename}")


# --- EJECUCIÓN PRINCIPAL ---
if __name__ == "__main__":
    sds = connect_to_scope("169.254.19.70")

    # Configura para capturar 5 pulsos
    df_frames = setup_scope_for_sequence(sds, channel="C1", vdiv=0.3, tdiv=2e-3, trig_level=0.1, seq_count=100)
    # Espera a que se complete la adquisición
    wait_for_trigger(sds)
    # Lee los frames de la secuencia
    df_frames = read_sequence_raw_frames(sds, channel = "C1")
    sds.close()
    #Dibuja el frame especificado
    plot_specified_frame_from_df(df_frames, 3)  # Por ejemplo, para el frame 3
    #Dibuja todos los frames
    #plot_all_frames(df_frames)  
    # Guarda todos los frames en un CSV, es muy lento
    save_frames_to_csv(df_frames, "frames_adquisicion.csv")



   

    
    


    
