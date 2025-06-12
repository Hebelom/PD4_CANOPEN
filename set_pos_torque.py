
import time
import motor_control
import datetime
_filename = None

def set_position_mode(node, target_position):
    """
    Set the motor to position mode and move to a target position.
    """
    motor_control.set_operation_mode(node, 1)  
    motor_control.set_control_word(node, 0x06) 
    motor_control.set_control_word(node, 0x07)  
    time.sleep(0.1)   
    motor_control.set_target_position(node, target_position)   
    motor_control.set_control_word(node, 0x1f)  

    try:
        while True:

            try:
                status_data = node.sdo[0x6041].raw
                current_torque  = node.sdo[0x6077].raw
            except Exception as e:
                pass

            if isinstance(status_data, bytes):
                status_word = int.from_bytes(status_data, byteorder='little')
            else:
                status_word = status_data

            if status_word & 0x0400:
                print("Target position reached. Stopping motion.")
                try:
                    motor_control.set_control_word(node, 0x00) 
                except Exception as e:
                    print("Failed to send stop command:", e)
                break
            time.sleep(0.1)
        en_value = motor_control.get_encoder_position(node)
   
        return 0
    except KeyboardInterrupt:
        print("Keyboard interrupt received. Exiting motion loop.")


def set_torque(node, target_torque, stop_event_load_cell=None):
    """
    Set the motor to torque mode and apply a target torque,
    with debug snapshots before config, after config, and each loop.
    """

    cw = node.sdo[0x6040].raw

    # 1) Set Fault-Reset bit (bit 7 = 0x0080)
    node.sdo[0x6040].raw = cw | 0x0080
    time.sleep(0.05)

    # 2) Clear the Fault-Reset bit again (so you stay in “Switch-On Disabled”)
    node.sdo[0x6040].raw = cw & ~0x0080
    time.sleep(0.05)
    
    # 1) Enter torque mode and enable operation
    motor_control.set_operation_mode(node, 0x04)
    motor_control.set_control_word(node, 0x06)
    motor_control.set_control_word(node, 0x07)
    motor_control.set_control_word(node, 0x0F)
    time.sleep(0.1)

    # 2) Load your torque parameters
    motor_control.set_torue_slope(node, 20)
    motor_control.set_torque(node, target_torque)
    motor_control.set_max_torque(node, abs(target_torque))
    motor_control.set_torque_window(node, 1)
    motor_control.set_torque_window_time_out(node, 10)
    motor_control.speed_in_torque(node)
    time.sleep(0.1)

    # 3) Re-enable operation (in case writing SDOs cleared it)
    motor_control.set_control_word(node, 0x0F)
    time.sleep(0.1)
    print_drive_errors(node)
    time.sleep(1)


    # 4) Monitor in a loop
    while True:
        status_data = motor_control.torque_status(node)
        current_torque = motor_control.current_torque_status(node)
        print(f"Status Data: {status_data}, Current Torque: {current_torque}, Target Torque: {target_torque}")
        if (status_data == 1 or current_torque == 0 ):
            print(">>> Target torque reached. Stopping motor.")
            try:
                motor_control.set_control_word(node, 0x0080)
                time.sleep(0.1)
                motor_control.set_control_word(node, 0x00)
                stop_event_load_cell.set()
            except Exception as e:
                print("Failed to send stop command:", e)
            break

    time.sleep(1)
    print(">>> END set_torque: final torque =", current_torque)
    cw = node.sdo[0x6040].raw
    # 1) Set Fault-Reset bit (bit 7 = 0x0080)
    node.sdo[0x6040].raw = cw | 0x0080
    time.sleep(0.05)
    # 2) Clear the Fault-Reset bit again (so you stay in “Switch-On Disabled”)
    node.sdo[0x6040].raw = cw & ~0x0080
    time.sleep(0.05)
    return current_torque





def simple_homing(node,
                  search_speed=100,
                  zero_speed=400,
                  accel=50):
    """Minimal homing sequence with Method 19 (left edge of home‑switch)."""
    en_value = motor_control.get_encoder_position(node)
   
    print(node ,"Encoder position before homing:", en_value)
   
    
    set_torque(node, 150)
    motor_control.map_input1_as_home_switch(node)
    motor_control.set_control_word(node, 0x0080)  
    motor_control.set_control_word(node, 0x0006)
    motor_control.set_control_word(node, 0x0007)
    motor_control.set_control_word(node, 0x000F)


    # ---- select Homing mode & parameters ---------------------------------
    node.sdo[0x6060].raw      = 6            
    node.sdo[0x6098].raw      = 19           
    node.sdo[0x6099][1].raw   = search_speed 
    node.sdo[0x6099][2].raw   = zero_speed   
    node.sdo[0x609A].raw      = accel        

    # ---- start homing (bit 4 = 1) ----------------------------------------
    motor_control.set_control_word(node, 0x001F)  # Start homing
    # ---- poll status until finished --------------------------------------
    while True:
        st = node.sdo[0x6041].raw
        if st == 0x9637:
            print("Homing finished.")
            motor_control.set_control_word(node, 0x00)  # Stop the motor
            en_value = motor_control.get_encoder_position(node)
            print(node, "Encoder position before homing:", en_value)
            time.sleep(0.1)
            break


def create_file(prefix="test_data"):
    """
    Create a new CSV file with a timestamped name and write the header.
    Returns the filename.
    """
    global _filename
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    _filename = f"{prefix}_{timestamp}.csv"
    # Write header
    with open(_filename, 'w', newline='') as f:
        f.write(
            "Timestamp, X Power, Y Power, X Direction, Y Direction, Encoder X, Encoder Y\n"
        )
    return _filename


def save_test_data(x_power, y_power, x_direction, y_direction, encoder_x, encoder_y):
    """
    Append a row of test data to the previously created file.
    Raises if create_file() has not been called.
    """
    global _filename
    if _filename is None:
        raise RuntimeError("No file created yet. Call create_file() first.")

    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

    with open(_filename, 'a', newline='') as f:
        f.write(
            f"{timestamp}, {x_power}, {y_power}, {x_direction}, {y_direction}, {encoder_x}, {encoder_y}\n"
        )


ERROR_NUMBER_DESC = {
    1:  "Input voltage (+Ub) too high",
    2:  "Output current too high",
    3:  "Input voltage (+Ub) too low",
    4:  "Error at fieldbus",
    6:  "CANopen only: Nodeguarding timeout",
    7:  "Sensor 1 hardware fault",
    8:  "Sensor 2 hardware fault",
    9:  "Sensor 3 hardware fault",
    10: "Warning: Positive limit switch exceeded",
    11: "Warning: Negative limit switch exceeded",
    12: "Overtemperature error",
    13: "Following-error window exceeded",
    14: "Warning: Nonvolatile memory full",
    15: "Motor blocked",
    # …etc. (add any others you need)
}
ERROR_CODE_DESC = {
    0x1000: "General error",
    0x2300: "Current at controller output too large",
    0x3100: "Over/undervoltage at controller input",
    0x4200: "Controller temperature error",
    0x5440: "Interlock error (60FDh bit 3=0)",
    0x6010: "Software reset (watchdog)",
    0x6100: "Internal software error",
    # …etc. (see table under “Error Code Description” ) :contentReference[oaicite:1]{index=1}
}

# 3) Read & print
def print_drive_errors(node):
    # Error Register (0x1001) :contentReference[oaicite:2]{index=2}
    err_reg = node.sdo[0x1001].raw
    print(f"Error Register (0x1001): 0x{err_reg:02X}")

    # Pre-defined Error Field (0x1003) :contentReference[oaicite:3]{index=3}
    count = node.sdo[0x1003][0x00].raw
    print(f"  {count} entr{'y' if count==1 else 'ies'} in error stack:")
    for i in range(1, count+1):
        entry = node.sdo[0x1003][i].raw
        num = entry & 0xFF             # lower byte = Error Number
        code = (entry >> 16) & 0xFFFF  # high word = Emergency/Error Code
        print(f"   [{i}] Raw=0x{entry:08X} → Number={num} “{ERROR_NUMBER_DESC.get(num,'?')}”, Code=0x{code:04X} “{ERROR_CODE_DESC.get(code,'?')}”")

    # Last Error Code (0x603F) :contentReference[oaicite:4]{index=4}
    last = node.sdo[0x603F].raw
    print(f"Last Error Code (0x603F): 0x{last:04X} → “{ERROR_CODE_DESC.get(last,'?')}”")


def debug_all(node):

    


    print(f"\n--- Motor Config Bits for Node {node} ---")
    try:
        val_3202 = node.sdo[0x3202].raw
        print(f"0x3202: {val_3202} (binary: {bin(val_3202)})")
    except Exception as e:
        print("Error reading 0x3202:", e)

    try:
        val_3203_01 = node.sdo[0x3203][1].raw
        print(f"0x3203:01: {val_3203_01} (binary: {bin(val_3203_01)})")
    except Exception as e:
        print("Error reading 0x3203:01:", e)

    try:
        val_3203_02 = node.sdo[0x3203][2].raw
        print(f"0x3203:02: {val_3203_02} (binary: {bin(val_3203_02)})")
    except Exception as e:
        print("Error reading 0x3203:02:", e)

    try:
        val_60E6_01 = node.sdo[0x60E6][1].raw
        print(f"0x60E6:01 (Polarity settings): {val_60E6_01} (binary: {bin(val_60E6_01)})")
    except Exception as e:
        print("Error reading 0x60E6:01:", e)

    try:
        val_60E6_02 = node.sdo[0x60E6][2].raw
        print(f"0x60E6:02 (Polarity settings): {val_60E6_02} (binary: {bin(val_60E6_02)})")
    except Exception as e:
        print("Error reading 0x60E6:02:", e)

    try:
        val_60E6_02 = node.sdo[0x60E6][3].raw
        print(f"0x60E6:03 (Polarity settings): {val_60E6_02} (binary: {bin(val_60E6_02)})")
    except Exception as e:
        print("Error reading 0x60E6:02:", e)
    print("--- End of config ---\n")



    
    try:
        val_3203_02 = node.sdo[0x33A0][2].raw
        print(f"0x33A0:02: {val_3203_02} (binary: {bin(val_3203_02)})")
    except Exception as e:
        print("Error reading 0x3203:02:", e)

    print("──────────────────────────────────────────────────\n")