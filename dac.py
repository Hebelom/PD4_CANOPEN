
import numpy as np
import nidaqmx
from nidaqmx.constants import TerminalConfiguration, AcquisitionType
from scipy.signal import butter, filtfilt
from scipy.signal import butter, lfilter, lfilter_zi


def load_cell_read( load_cell_x, load_cell_y, stop_event_load_cell):
    
    
    # ─── Config ───────────────────────────────────────────────────────────────────
    device           = "Dev1"
    channels         = ["ai0", "ai4"]

    sample_rate      = 1000      # Hz
    interval_ms      =   1       # we'll read 1 sample per ms
    read_chunk       = 1         # samples per read

    # ─── Filter design ─────────────────────────────────────────────────────────────
    cutoff_freq = 5              # Hz
    nyquist     = 0.5 * sample_rate
    b, a        = butter(4, cutoff_freq/nyquist, btype='low')

    # ─── DAQ setup ────────────────────────────────────────────────────────────────
    task = nidaqmx.Task()
    for ch in channels:
        task.ai_channels.add_ai_voltage_chan(
            f"{device}/{ch}",
            terminal_config=TerminalConfiguration.RSE,
            min_val=-10.0,
            max_val=10.0
        )
    # give the driver a 1 000-sample buffer
    task.timing.cfg_samp_clk_timing(
        rate=sample_rate,
        sample_mode=AcquisitionType.CONTINUOUS,
        samps_per_chan=sample_rate
    )
    task.start()

    # ─── Initialize filter states with a first sample ─────────────────────────────
    raw0_init, raw4_init = task.read(number_of_samples_per_channel=1, timeout=2.0)
    zi0 = lfilter_zi(b, a) * raw0_init
    zi4 = lfilter_zi(b, a) * raw4_init


    # ─── Calibration ──────────────────────────────────────────────────────────────

    raw0_list = []
    raw4_list = []

    for _ in range(10):
        raw0_chunk, raw4_chunk = task.read(
        number_of_samples_per_channel=read_chunk,
        timeout=2.0
        )
        data0, zi0 = lfilter(b, a, raw0_chunk, zi=zi0)
        data4, zi4 = lfilter(b, a, raw4_chunk, zi=zi4)
        raw0_list.append(data0[0])
        raw4_list.append(data4[0])


    sensitivity  = 0.435  # V per kg
    offset_ai0 = np.mean(raw0_list)
    offset_ai4 = np.mean(raw4_list)

    if (abs(offset_ai0) > 0.2 or  abs(offset_ai4) > 0.2):
        print("Warning: offset is too high, check calibration.")
        print(f"Offset ai0: {offset_ai0:.3f} V, ai4: {offset_ai4:.3f} V")
        print("Calibration failed.")
        print("Please check the load cells and try again.")
        print("If the load cells are not connected, please connect them and try again.")
    else:   
        print("Calibration successful.")
        print(f"Offset ai0: {offset_ai0:.3f} V, ai4: {offset_ai4:.3f} V")

    # ─── Configure AO1 to 0.5 V ───────────────────────────────────────────────────
    ao_task = nidaqmx.Task()
    ao_task.ao_channels.add_ao_voltage_chan(
    f"{device}/ao1",          # output channel 1
    min_val=0.0, max_val=10.0 # adjust to your device’s output range
    )
    ao_task.write(offset_ai0 + 1.05 )            # set 0.5 V
    ao_task.start()


    print(f"Streaming at {sample_rate} Hz, pulling {read_chunk} sample every {interval_ms} ms.")
    sensor_x = 1
    try:
        while True:
            raw0, raw4 = task.read(
                number_of_samples_per_channel=read_chunk,
                timeout=2.0
            )
            # causal IIR
            data0, zi0 = lfilter(b, a, raw0, zi=zi0)
            data4, zi4 = lfilter(b, a, raw4, zi=zi4)

            # predicted weight
            pred0 = ((data0[0] - offset_ai0) / sensitivity)*9.82
            pred4 = ((data4[0]- offset_ai4) / sensitivity)*9.82

            if stop_event_load_cell.is_set():
                ao_task.write(offset_ai0 + 8.57) 
            elif stop_event_load_cell.is_set() == False:
                ao_task.write(offset_ai0 + 1.05 )

            if pred0 < 0:
                pred0 *= -1
            if pred4 < 0:
                pred4 *= -1

            # push each to its queue
            load_cell_x.put({ "x": pred0 })
            load_cell_y.put({ "y": pred4 })


    except KeyboardInterrupt:
        print("Stopping.")
    finally:
        task.stop()
        task.close()
        ao_task.stop()
        ao_task.close()

            
