"""
factory_reset_node1.py
----------------------
Reset PD4‑E (or any Nanotec drive) node‑ID 1 back to factory defaults
without NanoLib.  Uses only python‑canopen.


"""

import time
import canopen

# ── USER SETTINGS ────────────────────────────────────────────────────
CHANNEL   = 0          # Kvaser channel, usually 0
BITRATE   = 1000000  # 1 Mbit is Nanotec default
NODE_ID   = 9999           # the motor you want to reset
# ─────────────────────────────────────────────────────────────────────

# CANopen index helper: combine index & subindex  → (index, sub)
RESTORE_ALL      = (0x1011, 0x01)   # Restore ALL categories
RESTORE_TUNING   = (0x1011, 0x06)   # Restore Tuning (motor parameters)
STORE_DONE_FLAG  = (0x1010, 0x01)   # Turns to 1 when flash finished
LOAD_MAGIC       = 0x64616F6C       # ASCII "load"  (little‑endian int)

print("Opening CAN bus …")
net = canopen.Network()
net.connect(bustype='kvaser', channel=CHANNEL, bitrate=BITRATE)

print("Adding node", NODE_ID)
node = canopen.BaseNode402(NODE_ID, "eds/m.eds")  # EDS not needed for raw SDOs
net.add_node(node)
LOAD     = 0x64616F6C # ASCII "load"


try:
    print("→ Restore ALL categories")
    node.sdo[0x1011][1].raw = LOAD     # 0x1011:01

    print("→ Restore TUNING category")
    node.sdo[0x1011][6].raw = LOAD     # 0x1011:06  (optional)

    print("→ Wait until flash done …")
    while node.sdo[0x1010][1].raw == 0:   # 0x1010:01
        time.sleep(0.1)

    print("→ Rebooting node", NODE_ID)
    node.nmt.state = 'RESET'

    print("✅ Factory defaults restored")

except canopen.SdoAbortedError as e:
    print("SDO abort:", e)
finally:
    net.disconnect()
