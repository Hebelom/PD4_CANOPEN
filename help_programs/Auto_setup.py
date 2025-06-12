import canopen, time

net = canopen.Network()
net.connect(interface='kvaser', channel=0, bitrate=1000000)
node = canopen.BaseNode402(9999, 'eds/m.eds')
net.add_node(node)

try:
    # 1) Pre‑select Auto‑Setup
    node.sdo[0x6060].raw = -2                     # 0xFE

    # 2) CiA‑402 -> Operation enabled
    for cw in (0x06, 0x07, 0x0F):
        node.sdo[0x6040].raw = cw
        time.sleep(0.05)

    # 3) Start Auto‑Setup (set bit4) -> 0x001F
    node.sdo[0x6040].raw = 0x001F
    print("Auto‑Setup running…")

    # 4) Wait for bit12 OMS
    while True:
        status = node.sdo[0x6041].raw
        if status & (1 << 12):
            break
        time.sleep(0.2)

    print("Auto‑Setup finished OK!")

    # 5) Stop the motor
    node.sdo[0x6040].raw = 0

    node.sdo[0x1010][6].raw = 1702257011

    time.sleep(5)


    # 6) Reboot so the new parameters are active
    node.nmt.state = 'RESET'
    print("Drive rebooted – new tuning loaded.")

finally:
    net.disconnect()
