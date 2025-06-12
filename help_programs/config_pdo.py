import canopen
import time

# 1) Connect
net = canopen.Network()
net.connect(interface='kvaser', channel=0, bitrate=1000000)
node = canopen.BaseNode402(1, 'eds/m.eds')
net.add_node(node)

# 2) Go PRE-OP so remapping is allowed
node.nmt.state = 'PRE-OPERATIONAL'
time.sleep(0.1)

try:
    orig_cob = node.sdo[0x1400][1].raw
    disabled_cob = orig_cob | (1 << 31)
    node.sdo[0x1400][1].raw = disabled_cob
    print(f"✅ RxPDO1 disabled! COB-ID was 0x{orig_cob:08X}, now 0x{disabled_cob:08X}")

    node.sdo[0x1605][0].raw = 0

    m1 = (0x6071 << 16) | (0x00 << 8) | 16
    node.sdo[0x1605][1].raw = m1
    m2 = (0x6072 << 16) | (0x00 << 8) | 16
    node.sdo[0x1605][2].raw = m2
    m3 = (0x6080 << 16) | (0x00 << 8) | 32
    node.sdo[0x1605][3].raw = m3

    ""


    """
    m1 = (0x6073 << 16) | (0x00 << 8) | 16
    node.sdo[0x1601][1].raw = m1
    m2 = (0x6074 << 16) | (0x00 << 8) | 16
    node.sdo[0x1601][2].raw = m2

        m3 = (0x6087 << 16) | (0x00 << 8) | 32
    node.sdo[0x1605][3].raw = m3
    m3 = (0x6087 << 16) | (0x00 << 8) | 32
    node.sdo[0x1600][3].raw = m3
        m4 = (0x6040 << 16) | (0x00 << 8) | 8
    node.sdo[0x1605][4].raw = m4

    
    m4 = (0x6073 << 16) | (0x00 << 8) | 16
    node.sdo[0x1600][4].raw =m4

    
    m5 = (0x6080 << 16) | (0x00 << 8) | 32
    node.sdo[0x1600][6].raw = m5
    
    m4 = (0x6074 << 16) | (0x00 << 8) | 16
    node.sdo[0x1600][4].raw = m4
    
    m3 = (0x6073 << 16) | (0x00 << 8) | 16
    node.sdo[0x1600][3].raw =m3

    m6 = (0x6080 << 16) | (0x00 << 8) | 16
    node.sdo[0x1600][6].raw = m6
    """

    node.sdo[0x1605][0].raw = 3
    node.sdo[0x1400][1].raw = orig_cob & 0x7FFFFFFF

    node.nmt.state = 'OPERATIONAL'
    time.sleep(0.1)

    node.pdo.read()

    pdo1 = node.pdo.rx[6]
    test_value = 8
    pdo1['Target torque'].raw = test_value
    pdo1['Max torque'].raw = test_value
    pdo1.transmit()
    time.sleep(0.01)

    time.sleep(0.1)
    torque = node.sdo[0x6071].raw
    max_torque = node.sdo[0x6072].raw
    target = node.sdo[0x6071].raw
    print(f"Torque target = {target} via SDO")
    print(f"Max Torque = {max_torque} via SDO")

    print("✅ Torque Slope mapped into RxPDO1!")
except Exception as e:
    print("❌ Remapping failed:", e)






