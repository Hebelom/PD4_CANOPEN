import time
import numpy as np
import nidaqmx
from nidaqmx.constants import TerminalConfiguration, AcquisitionType
from scipy.signal import butter, lfilter, lfilter_zi

# ─── Config ───────────────────────────────────────────────────────────────────
device      = "Dev1"
channels    = ["ai0", "ai4"]
sample_rate = 1000      # Hz
read_chunk  = 1         # samples per read

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
        min_val=-10.0, max_val=10.0
    )
task.timing.cfg_samp_clk_timing(
    rate=sample_rate,
    sample_mode=AcquisitionType.CONTINUOUS,
    samps_per_chan=sample_rate
)
task.start()

# ─── Init filter states ─────────────────────────────────────────────────────────
raw0_init, raw4_init = task.read(number_of_samples_per_channel=1, timeout=2.0)
zi0 = lfilter_zi(b, a) * raw0_init
zi4 = lfilter_zi(b, a) * raw4_init

# ─── Kalibrering ────────────────────────────────────────────────────────────────
raw0_list, raw4_list = [], []
for _ in range(10):
    raw0_chunk, raw4_chunk = task.read(number_of_samples_per_channel=read_chunk, timeout=2.0)
    data0, zi0 = lfilter(b, a, raw0_chunk, zi=zi0)
    data4, zi4 = lfilter(b, a, raw4_chunk, zi=zi4)
    raw0_list.append(data0[0])
    raw4_list.append(data4[0])

avg_data0 = np.mean(raw0_list)
avg_data4 = np.mean(raw4_list)

print(f"Average of first 10 samples: ai0 = {avg_data0:.3f} V, ai4 = {avg_data4:.3f} V")

# ─── Configure AO1 to 0.5 V ───────────────────────────────────────────────────
ao_task = nidaqmx.Task()
ao_task.ao_channels.add_ao_voltage_chan(
    f"{device}/ao1",          # output channel 1
    min_val=0.0, max_val=10.0 # adjust to your device’s output range
)
ao_task.write(avg_data0 + 1)            # set 0.5 V
ao_task.start()


# ─── Streaming loop med latensmätning ───────────────────────────────────────────
try:
    while True:
        t_loop_start = time.perf_counter()

        # Läs ett sample (blockerar ~1 ms)
        raw0, raw4 = task.read(number_of_samples_per_channel=read_chunk, timeout=2.0)
        t_after_read = time.perf_counter()

        # Filtrera och beräkna
        data0, zi0 = lfilter(b, a, raw0, zi=zi0)
        data4, zi4 = lfilter(b, a, raw4, zi=zi4)
        pred0 = abs((data0[0] - avg_data0) / 0.435) * 9.82
        pred4 = abs((data4[0] - avg_data4) / 0.435) * 9.82

        # Skicka till kö eller skriv ut
        print(f"data0: {data0[0]:.3f} V, ai0: {pred0:.3f} N", end=' – ')
        print(f"data4: {data4[0]:.3f} V, ai4: {pred4:.3f} N", end=' – ')
        t_after_print = time.perf_counter()

        # Beräkna latens
        lat_read_to_print = (t_after_print - t_after_read) * 1000
        lat_total        = (t_after_print - t_loop_start) * 1000
        print(f"lat(read→print): {lat_read_to_print:.3f} ms, total_loop: {lat_total:.3f} ms")

except KeyboardInterrupt:
    print("Stopping.")
finally:
    task.stop()
    task.close()
    ao_task.stop()
    ao_task.close()
