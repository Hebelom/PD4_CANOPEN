import numpy as np, matplotlib.pyplot as plt, nidaqmx
from nidaqmx.constants import TerminalConfiguration, AcquisitionType
from scipy.signal import hann

fs        = 5000         # Hz
n_samples = 8192
device    = "Dev1"
channels  = ["ai0"]

task = nidaqmx.Task()
task.ai_channels.add_ai_voltage_chan(f"{device}/ai0",
                                     terminal_config=TerminalConfiguration.RSE)
task.timing.cfg_samp_clk_timing(fs, 
        sample_mode=AcquisitionType.FINITE,
        samps_per_chan=n_samples)

data = task.read(number_of_samples_per_channel=n_samples, timeout=5.0)
task.close()

sig   = np.asarray(data)
win   = hann(n_samples, sym=False)
freqs = np.fft.rfftfreq(n_samples, 1/fs)
psd   = 20 * np.log10(np.abs(np.fft.rfft(sig*win)) / (n_samples/2))

plt.figure(figsize=(8,4))
plt.semilogx(freqs, psd)
plt.title("FFT, log‑frekvens")
plt.xlabel("Frequency (Hz)")
plt.ylabel("Amplitude (dB V)")
plt.grid(True, ls=":")
plt.xlim(1, fs/2)
plt.ylim(-140, 0)
plt.tight_layout()
plt.show()
