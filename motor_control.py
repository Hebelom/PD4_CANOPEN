import canopen
import time

 

def init_canopen(node_id, channel_id):
    
    network = canopen.Network()
    network.connect(interface='kvaser', channel=channel_id, bitrate=1000000)
    network.check()

    node = canopen.BaseNode402(node_id, 'eds/m.eds')
    network.add_node(node)
    # go PRE-OP if needed…
    #node.nmt.state = 'PRE-OPERATIONAL'
    #time.sleep(0.1)

    try:
       # network.nmt.state = 'RESET'  # Återställ noden
       # time.sleep(1)  # Vänta en stund för att säkerställa att noden är återställd
        network.nmt.state = 'OPERATIONAL'  # Sätt noden till OPERATIONAL
        time.sleep(1)  # Vänta en stund för att säkerställa att noden är i OPERATIONAL-tillstånd
         # Sätt nodens tillstånd till OPERATIONAL
        print("Node state set to OPERATIONAL.")
    except Exception as e:
        print("Failed to change node state:", e)
        time.sleep(0.1)
    return node, network


def set_operation_mode(node, mode_value): 
    try:
        node.sdo[0x6060].raw = mode_value
        print(f"Operating mode set to {mode_value}.")
    except Exception as e:
        print(f"Error setting operating mode: {e}")


def set_control_word(node, control_word_value):

    try:
        node.sdo[0x6040].raw = control_word_value
        print(f"Control word set to {control_word_value}.")
    except Exception as e:
        print(f"Error setting control word: {e}")

def set_target_position(node, target_position_value):

    try:
        node.sdo[0x607A].raw = target_position_value
        print(f"Target position set to {target_position_value}.")
    except Exception as e:
        print(f"Error setting target position: {e}")


def set_torque(node, torque_value):
    try:
        node.sdo[0x6071].raw = torque_value
        print(f"Torque set to {torque_value}.")
    except Exception as e:
        print(f"Error setting torque: {e}")

def set_max_torque(node, max_torque_value):
    try:
        node.sdo[0x6072].raw = max_torque_value
        print(f"Maximum torque set to {max_torque_value}.")
    except Exception as e:
        print(f"Error setting maximum torque: {e}")

def set_torque_window(node, torque_window_value):

    try:
        node.sdo[0x203D].raw = torque_window_value
        print(f"Torque window set to {torque_window_value}.")
    except Exception as e:
        print(f"Error setting torque window: {e}")


def set_torque_window_time_out(node, torque_window_timeout_value):

    try:
        node.sdo[0x203E].raw = torque_window_timeout_value
        print(f"Torque window timeout set to {torque_window_timeout_value}.")
    except Exception as e:
        print(f"Error setting torque window timeout: {e}")


def torque_status(node): 
    try:
        torque_status_value = node.sdo[0x6041].raw
    except Exception as e:
        print(f"Error getting torque status: {e}")
        return None
    # Extract the bits of interest from the torque status value
    cw_bit8 = (torque_status_value >> 8)  & 1   # 6040h – bit 8
    sw_bit10 = (torque_status_value >> 10) & 1  # 6041h – bit 10

    if   cw_bit8 == 0 and sw_bit10 == 0:
        return 0  # Specified torque not reached
    elif cw_bit8 == 0 and sw_bit10 == 1:
        return 1
    elif cw_bit8 == 1 and sw_bit10 == 0:
        return 0
        #print("Axis brakes")
    else:  # cw_bit8 == 1 and sw_bit10 == 1
        return 0
        #print("Axis speed is 0")
   

def get_encoder_position(node):

    try:
        encoder_position = node.sdo[0x6064].raw
        return encoder_position
    except Exception as e:
        print(f"Error getting encoder position: {e}")
        return None
def get_raw_encoder(node):

    try:
        raw_encoder_value = node.sdo[0x6063].raw
       
        return raw_encoder_value
    except Exception as e:
        print(f"Error getting raw encoder value: {e}")
        return None

def speed_in_torque(node):
    try:
        mask = ~(1 << 5)
        value =  node.sdo[0x3202].raw 
        value = value & mask
        node.sdo[0x3202].raw = value
    except Exception as e:
        print(f"Error setting maximum current: {e}")

def set_speed_in_torque(node, speed_in_torque_value):
    try:
        node.sdo[0x6080].raw = speed_in_torque_value
        print(f"Speed in torque set to {speed_in_torque_value}.")
    except Exception as e:
        print(f"Error setting speed in torque: {e}")

def set_torue_slope(node, torque_slop_value):

    try:
        node.sdo[0x6087].raw = torque_slop_value
        print(f"Torque slope set to {torque_slop_value}.")
    except Exception as e:
        print(f"Error setting torque slope: {e}")
def set_max_current(node, max_current_value):
    """
    Set the maximum current. This is typically done by writing to object 0x6073.
    """
    try:
        node.sdo[0x6073].raw = max_current_value
        print(f"Maximum current set to {max_current_value}.")
    except Exception as e:
        print(f"Error setting maximum current: {e}")

def current_torque_status(node):
    current_torque = 0
    try:
        current_torque  = node.sdo[0x6077].raw
    except Exception as e:
        print("Error reading torque value:", e)
    return current_torque

def set_direction(node, direction_value):
    """
    Set the direction. This is typically done by writing to object 0x607C.
    """
    try:
        node.sdo[0x607E].raw = direction_value
    except Exception as e:
  
        print(f"Error setting direction: {e}")

def save_configuration(node):
    """
    Save the current configuration parameters.
    This typically writes a specific key (e.g., 0x65766173h as per manual)
    to object 0x1010 (Store Parameters) or similar.
    """
    try:
        node.sdo[0x1010].raw = 0x65766173  # The magic value in hexadecimal.
        print("Configuration saved.")
    except Exception as e:
        print(f"Error saving configuration: {e}")

def map_input1_as_home_switch(node):
    """Route physical Input 1 to the home‑switch special function."""
    node.sdo[0x3240][8].raw = 1              
    node.sdo[0x3242][3].raw = 0x01           
    node.sdo[0x3240][1].raw |= 0x00000004   
    

