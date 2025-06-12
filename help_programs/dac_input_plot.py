import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
import nidaqmx
from nidaqmx.constants import TerminalConfiguration, AcquisitionType
from scipy.signal import butter, filtfilt
import time

# ─── Config ───────────────────────────────────────────────────────────────────
device           = "Dev1"
channels         = ["ai0", "ai4"]
sample_rate      = 500    # Hz
interval_ms      =  1                       # → redraw every 50 ms
samples_per_chan = int(sample_rate * 32/1000)  # → 7 samples
window_duration  = 1      # seconds of history to show


# ─── Filter design (zero‐phase) ───────────────────────────────────────────────
cutoff_freq = 5  # Hz
nyquist     = 0.5 * sample_rate
b, a        = butter(4, cutoff_freq/nyquist, btype='low')

# ─── Calibration ──────────────────────────────────────────────────────────────
offset_ai4 = 0.025
offset_ai0   = 0.01    # V zero‐point
sensitivity = 0.435   # V per kg

# ─── Buffers ──────────────────────────────────────────────────────────────────
time_buffer  = []
data0_buffer = []
data4_buffer = []
start_time   = time.time()
prev_ymin, prev_ymax = -1, 1

# ─── Plot setup ───────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 4))

# ai0 traces
line0,      = ax.plot([], [], 'b-',  label="ai0 (filtered)")
avg5_0,     = ax.plot([], [], 'g--', label="ai0 Avg5")
pred0_line, = ax.plot([], [], 'r-.', label="ai0 Pred kg")

# ai4 traces
line4,      = ax.plot([], [], 'k-',  label="ai4 (filtered)")
avg5_4,     = ax.plot([], [], 'c--', label="ai4 Avg5")
pred4_line, = ax.plot([], [], 'm-.', label="ai4 Pred kg")

ax.set_xlabel("Time (s)")
ax.set_ylabel("Voltage (V) / Weight (kg)")
# initial placeholder; will update each frame
title = ax.set_title("Predicted Weight — ai0: 0.000 kg | ai4: 0.000 kg")
ax.grid(True)
ax.legend(loc="upper left")

# ─── Single NI-DAQ Task for both channels ─────────────────────────────────────
task = nidaqmx.Task()
for ch in channels:
    task.ai_channels.add_ai_voltage_chan(
        f"{device}/{ch}",
        terminal_config=TerminalConfiguration.RSE,
        min_val=-10.0,
        max_val=10.0
    )
task.timing.cfg_samp_clk_timing(
    rate=sample_rate,
    sample_mode=AcquisitionType.CONTINUOUS,
    samps_per_chan=samples_per_chan
)
task.start()

# ─── Animation update ─────────────────────────────────────────────────────────
def update(frame):
    global prev_ymin, prev_ymax

    # Read both channels
    raw = task.read(number_of_samples_per_channel=samples_per_chan, timeout=5.0)
    try:
        raw0, raw4 = raw  # if it's a list of two arrays
    except (ValueError, TypeError):
        arr = np.array(raw).reshape(-1, 2)
        raw0, raw4 = arr[:, 0], arr[:, 1]

    # Filter (zero-phase)
    data0 = filtfilt(b, a, raw0)
    data4 = filtfilt(b, a, raw4)

    # Timestamps for this batch
    now   = time.time() - start_time
    dt    = 1.0 / sample_rate
    times = [now + i*dt for i in range(len(data0))]

    # Append & trim buffers
    time_buffer.extend(times)
    data0_buffer.extend(data0)
    data4_buffer.extend(data4)
    while time_buffer and (time_buffer[-1] - time_buffer[0] > window_duration):
        time_buffer.pop(0)
        data0_buffer.pop(0)
        data4_buffer.pop(0)

    # 5‐sample averages
    avg5_0_val = np.mean(data0_buffer[-5:]) if len(data0_buffer) >= 5 else np.mean(data0_buffer)
    avg5_4_val = np.mean(data4_buffer[-5:]) if len(data4_buffer) >= 5 else np.mean(data4_buffer)

    # Predicted weights
    pred0_val = (avg5_0_val - offset_ai0) / sensitivity
    pred4_val = (avg5_4_val - offset_ai4) / sensitivity

    # Update ai0 lines
    t0, t1 = time_buffer[0], time_buffer[-1]
    line0.set_data(time_buffer, data0_buffer)
    avg5_0.set_data([t0, t1], [avg5_0_val, avg5_0_val])
    pred0_line.set_data([t0, t1], [pred0_val, pred0_val])

    # Update ai4 lines
    line4.set_data(time_buffer, data4_buffer)
    avg5_4.set_data([t0, t1], [avg5_4_val, avg5_4_val])
    pred4_line.set_data([t0, t1], [pred4_val, pred4_val])

    # Adjust axes
    ax.set_xlim(t0, t1)
    y_min = min(np.min(data0_buffer), np.min(data4_buffer))
    y_max = max(np.max(data0_buffer), np.max(data4_buffer))
    margin = 0.1 * (y_max - y_min + 1e-6)
    prev_ymin = min(prev_ymin, y_min - margin)
    prev_ymax = max(prev_ymax, y_max + margin)
    ax.set_ylim(prev_ymin, prev_ymax)

    # Dynamically update title with live predicted weights
    title.set_text(f"Predicted Weight ai0: {avg5_0_val:.3f} V = {pred0_val:.3f} kg | ai4: {avg5_4_val:.3f} V =  {pred4_val:.3f} kg")

    return line0, avg5_0, pred0_line, line4, avg5_4, pred4_line

# ─── Run the animation ────────────────────────────────────────────────────────
ani = animation.FuncAnimation(
    fig, update,
    interval=interval_ms,
    cache_frame_data=False
)

plt.tight_layout()
plt.show()

# ─── Clean up ────────────────────────────────────────────────────────────────
task.stop()
task.close()
