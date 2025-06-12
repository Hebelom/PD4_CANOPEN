import canopen
import time

# 1) Connect
net = canopen.Network()
net.connect(interface='kvaser', channel=0, bitrate=1000000)
node = canopen.BaseNode402(1, 'eds/m.eds')
net.add_node(node)

# 2) Enter OPERATIONAL (so PDOs can be used) and read all PDO mappings
node.nmt.state = 'OPERATIONAL'
time.sleep(0.1)
node.pdo.read()

# 3) Print Rx-PDOs
print("=== Rx-PDOs ===")
for idx, pdo in sorted(node.pdo.rx.items()):
    print(f"RPDO {idx}: COB-ID = 0x{pdo.cob_id:03X}")
    for entry in pdo.map:
        # entry.name might exist; if not, skip or use a placeholder
        name = getattr(entry, 'name', '<unnamed>')
        print(f"   - {name}: index=0x{entry.index:04X}, sub=0x{entry.subindex:02X}, len={entry.length} bits")
    print()

# 4) Print Tx-PDOs
print("=== Tx-PDOs ===")
for idx, pdo in sorted(node.pdo.tx.items()):
    print(f"TPDO {idx}: COB-ID = 0x{pdo.cob_id:03X}")
    for entry in pdo.map:
        name = getattr(entry, 'name', '<unnamed>')
        print(f"   - {name}: index=0x{entry.index:04X}, sub=0x{entry.subindex:02X}, len={entry.length} bits")
    print()

net.disconnect()