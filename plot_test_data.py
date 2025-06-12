import csv
import sys
import matplotlib.pyplot as plt


def plot_power_odd_even(filename):
    """
    Läser CSV-filen vid `filename` (med rubrikrad):
    Timestamp, X Power, Y Power, X Direction, Y Direction, Encoder X, Encoder Y

    Och skapar fyra separata matplotlib-figurer:
      1) X-effekt vid udda nummer-prover
      2) X-effekt vid jämna nummer-prover
      3) Y-effekt vid udda nummer-prover
      4) Y-effekt vid jämna nummer-prover
    """
    # --- Läs och parsa CSV ---
    with open(filename, newline='') as f:
        reader = csv.reader(f)
        next(reader)  # hoppa över rubrikrad

        x_power, y_power = [], []
        x_dir, y_dir = [], []
        enc_x, enc_y = [], []

        for row in reader:
            ts, xp, yp, xd, yd, ex, ey = (col.strip() for col in row)
            x_power.append(float(xp))
            y_power.append(float(yp))
            x_dir.append(float(xd))
            y_dir.append(float(yd))
            enc_x.append(int(ex))
            enc_y.append(int(ey))

    # Skapa provindex 1..N
    indices = list(range(1, len(x_power) + 1))

    # Separera udda- och jämna-index
    odd_idx   = [i for i in indices if i % 2 == 1]
    even_idx  = [i for i in indices if i % 2 == 0]
    x_odd     = [x_power[i-1] for i in odd_idx]
    x_even    = [x_power[i-1] for i in even_idx]
    y_odd     = [y_power[i-1] for i in odd_idx]
    y_even    = [y_power[i-1] for i in even_idx]

    # --- Figur 1: X-effekt vid udda prover ---
    plt.figure(figsize=(6,4))
    plt.plot(odd_idx, x_odd, marker='o', linestyle='-')
    plt.xlabel('Provnummer ')
    plt.ylabel('Newton')
    plt.title('Newton vid rörlse fråm joysticken y - riktning')
    plt.grid(True)

    # --- Figur 2: X-effekt vid jämna prover ---
    plt.figure(figsize=(6,4))
    plt.plot(even_idx, x_even, marker='o', linestyle='-')
    plt.xlabel('Provnummer ')
    plt.ylabel('Newton')
    plt.title('Newton vid rörlse mot joysticken y - riktning')
    plt.grid(True)

    # --- Figur 3: Enkoder X vs. X-riktning (två paneler, nedre har dubbla y-axlar) ---
    # beräkna enkoder-delta per prov
    delta     = [enc_x[i] - enc_x[i-1] for i in range(1, len(enc_x))]
    samples_d = indices[1:]

    fig, (ax1, ax2) = plt.subplots(
        2, 1, sharex=True, figsize=(6,8),
        gridspec_kw={'height_ratios': [2, 1]}
    )

    # Övre panel: råa enkoder-räkningar
    ax1.plot(indices, enc_x, color='tab:blue', linewidth=1)
    ax1.set_ylabel('Enkoder X Räknare')
    ax1.set_title('Enkoder X riktning vs. Provnummer')
    ax1.grid(True)

    # Nedre panel: enkoder-delta till vänster, joystick till höger
    ax2.scatter(samples_d, delta,
                s=20, alpha=0.7, label='Δ-enkoder', color='tab:blue')
    ax2.set_ylabel('Δ Enkoder Räknare', color='tab:blue')
    ax2.tick_params(axis='y', labelcolor='tab:blue')
    ax2.grid(True)

    ax3 = ax2.twinx()
    ax3.step(indices, y_dir, where='mid',
             linestyle='--', linewidth=1.5,
             label='X-riktning', color='tab:orange')
    ax3.set_ylabel('X-riktning Kommando', color='tab:orange')
    ax3.tick_params(axis='y', labelcolor='tab:orange')

    # justera vänster-axel för enkoder-delta
    lo, hi = min(delta), max(delta)
    margin = 0.1 * (hi - lo)
    ax2.set_ylim(lo - margin, hi + margin)

    # justera höger-axel till ±150 för joystick
    ax3.set_ylim(-150, 150)

    ax2.set_xlabel('Provnummer')
    # kombinera legender
    h1, l1 = ax2.get_legend_handles_labels()
    h2, l2 = ax3.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, loc='upper left')

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Användning: python {sys.argv[0]} <sökväg_till_csv_fil>")
        sys.exit(1)
    plot_power_odd_even(sys.argv[1])
