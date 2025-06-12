import sys
import queue
import threading
import time
import qe_command
import dac
import set_pos_torque
import motor_control
from PySide6 import QtWidgets, QtCore, QtGui
from worker_pool import submit, shutdown, _result_queue
import numpy as np
import matplotlib.pyplot as plt

# Global event to signal thread shutdown.
stop_event = threading.Event()
stop_event_load_cell = threading.Event()

#gloabl queues
loadcell_x = queue.Queue()
loadcell_y = queue.Queue()
data_x = queue.Queue()
data_y = queue.Queue()

# Global variables for motor control and joystick data.
save_mode = 0           # 1=collect, 2=report
pos_set = 2
encoder_x_start = 0
encoder_y_start = 0
equation_push = None
equation_pull = None
task_done = False


def save_load_cell_data(loadcell_x: queue.Queue, loadcell_y: queue.Queue, save_to_file = 0):
    
    global save_mode, encoder_x_start, encoder_y_start
    loadcell_x_values = [0]
    loadcell_y_values = [0]
    try:
        while True:
            loadcell_x.get_nowait()   # pop one item
    except queue.Empty:
        pass  # now the queue is empty

    try:
        while True:
            loadcell_y.get_nowait()   # pop one item
    except queue.Empty:
        pass  # now the queue is empty
   # 0) Idle: no work
    if save_mode == 0:
        print("Idle...")
        return

    while save_mode == 1:
        x = loadcell_x.get()
        y = loadcell_y.get()

        loadcell_x.task_done()
        loadcell_y.task_done()
        x = x.get("x", None)
        y = y.get("y", None)
        loadcell_x_values.append(abs(x))
        loadcell_y_values.append(abs(y))  

    try:
        while True:
            data_y.get_nowait()   # pop one item
    except queue.Empty:
        pass  # now the queue is empty

    try:
        while True:
            data_x.get_nowait()   # pop one item
    except queue.Empty:
        pass  # now the queue is empty

    try:
        data_x_item = data_x.get(timeout=2)
        joystick_x_raw = data_x_item["x"]  
        joystick_x_pos = data_x_item["x_d"]  
        if(joystick_x_pos == 1): #left = 1, right = 2
            joystick_x_raw *= -1
        joystick_x = joystick_x_raw
    except queue.Empty:
        pass

    # Update for Y:
    try:
        data_y_item = data_y.get(timeout=2)        
        joystick_y_raw = data_y_item["y"]  
        joystick_y_pos = data_y_item["y_d"]  
        if(joystick_y_pos == 1): #down = 1, up = 2
            joystick_y_raw *= -1    
        joystick_y = joystick_y_raw
        
    except queue.Empty:
        pass


    if save_mode == 2:
            print("Saving data...")
            max_x  = max(loadcell_x_values)
            max_y  = max(loadcell_y_values)
            encode_x = motor_control.get_encoder_position(node_x) 
            #encode_y = motor_control.get_encoder_position(node_y)
            save_mode = 0

            if(save_to_file == 0):
                set_pos_torque.save_test_data(
                *(f"{v:.2f}" for v in (max_x, max_y, joystick_x, joystick_y)),
                encode_x, 0)
                print("Data saved.")
                return
            else:
                return max_x
        
    
def init_motor():
    """
    Initialize the motor and set it to a known state.
    """
    node_id = 2  
    channel_id = '0'  
    global node_x, network_x, node_y, network_y
    node_x, network_x = motor_control.init_canopen(node_id, channel_id)
    """""
    node_id = 2  
    channel_id = '0'  
    node_y, network_y = motor_control.init_canopen(node_id, channel_id)
    node_y.sdo[0x1017].raw = 500
    """
    node_x.sdo[0x1017].raw = 500
    set_pos_torque.simple_homing(node_x) 
    time.sleep(1)
        # 1) Fault reaction: quick-stop ramp on interlock fault
    node_x.sdo[0x605E].raw = 1      # 0→coast, 1→slow ramp, 2→quick-stop ramp

    # 2) Enable interlock function (3240:01 bit 3)
    current = node_x.sdo[0x3240][1].raw
    node_x.sdo[0x3240][1].raw = current | 0x08

    # 3) Invert input logic so HIGH→fault (3240:02 bit 3)
    current = node_x.sdo[0x3240][2].raw
    node_x.sdo[0x3240][2].raw = current | 0x08

    # 4) (Skip 24 V threshold if you’re on 5 V)
    #    Otherwise:
    current = node_x.sdo[0x3240][6].raw
    node_x.sdo[0x3240][6].raw = current | 0x08

    # 5) Enable routing (3240:08 = 1)
    node_x.sdo[0x3240][8].raw = 1

    # 6) Map physical Input 4 → interlock bit 3 (3242:04 = 4)
    node_x.sdo[0x3242][4].raw = 132
    
def set_upp_motor():
    global equation_push, equation_pull, save_mode, node_x
    print("starting set upp")
    value_out = []
    load_cell_value_push = []
    load_cell_value_pull = []
    start_value = 70
    for x in range(start_value, 200, 5):
       submit( set_pos_torque.set_torque, node_x, x)
       save_mode = 1
       max_x = save_load_cell_data(loadcell_x, loadcell_y, 1)
       value_out.append(x)
       load_cell_value_push.append(max_x)
       print("Push value:", x, "Load cell value:", max_x)
       set_pos_torque.set_position_mode(node_x, 0)
       time.sleep(0.5)
       v = -x
       print("Pull value:", v)
       submit( set_pos_torque.set_torque, node_x, v)
       save_mode = 1
       max_x = save_load_cell_data(loadcell_x, loadcell_y, 1)
       load_cell_value_pull.append(max_x)
       set_pos_torque.set_position_mode(node_x, 0)
       time.sleep(0.1)
    x_value = np.array(value_out)
    y_push = np.array(load_cell_value_push)
    y_pull = np.array(load_cell_value_pull)
    coeffs_push = np.polyfit(y_push, x_value, deg=2)
    coeffs_pull = np.polyfit(y_pull, x_value, deg=2)
    equation_push = np.poly1d(coeffs_push)
    equation_pull = np.poly1d(coeffs_pull)
    print("Push equation:", equation_push)
    print("Pull equation:", equation_pull)
    
def predict(value, direction):
    """
    Predict the load cell value based on the input value and direction.
    """
    global equation_push, equation_pull
    if direction == "push":
        if equation_push is not None:
            return equation_push(value)
        else:
           
            return None
    elif direction == "pull":
        if equation_pull is not None:
            return equation_pull(value)
        else:
    
            return None
    else:
        print("Invalid direction. Use 'push' or 'pull'.")
        return None
       
def start_handling( Test_Type, moment, power_x, power_y, cycles):
    """
    Start the handling of the motor.
    """
    global save_mode, pos_set
    cycle_count = 0
    set_pos_torque.create_file()

    # Set the test type and moment type.
    if Test_Type == "Power_Test":
      
        while cycle_count < cycles*2:

            if(cycle_count % 2 == 0 or cycle_count == 0):
                power_x_ = predict(power_x, "pull")
                if power_x_ is None:
                    power_x_ = power_x

            elif(cycle_count % 2 == 1):
                power_x_ = predict(power_x, "push")
                if power_x_ is None:
                    power_x_ = power_x

            if(pos_set == 2):
                stop_event_load_cell.clear()
                pos_set = 0
                if moment == "X":
                    submit( set_pos_torque.set_torque, node_x, power_x_, stop_event_load_cell)
                elif moment == "Y":
                    pass
                    #submit( set_pos_torque.set_torque, node_y, power_y)
                elif moment == "Combined":
                    submit( set_pos_torque.set_torque, node_x, power_x_)
                save_mode = 1
                save_load_cell_data( loadcell_x, loadcell_y) 
                cycle_count += 1
                print("-----------------------------------")
                submit( set_pos_torque.set_position_mode, node_x, 0)
                
    elif Test_Type == "Position_Test":
        print("Power X:", power_x)
        print("Power Y:", power_y)
        motor_control.set_direction(node_x, 0xFF if power_x < 0 else 0x00)
        #motor_control.set_direction(node_y, 0xFF if power_y < 0 else 0x00)
        if moment == "X":
            submit( set_pos_torque.set_position_mode, node_x, power_x)
        elif moment == "Y":
            pass
            #submit( set_pos_torque.set_position_mode, node_y, power_y)
        elif moment == "Combined":
            submit( set_pos_torque.set_position_mode, node_x, power_x)
            #submit( set_pos_torque.set_position_mode, node_y, power_y)

class MyWidget(QtWidgets.QWidget):
    def __init__(self, data_x, data_y, loadcell_x, loadcell_y):
        super().__init__()      # ← do this first

        # Set your font
        font = QtGui.QFont("Calibri", 13, QtGui.QFont.Bold)
        self.setFont(font)

        # and the fixed size for all QLineEdits
        self.setStyleSheet("""
            QWidget {
                background-color: #232222;
                color: #02D5FA;
            }
            QLineEdit {
                min-width: 150px;
                max-width: 150px;
                min-height: 25px;
                max-height: 25px;
            }
        """)
        # Save the queues; note: joystick data will come from data_x and data_y.
        self.data_x = data_x
        self.data_y = data_y
        self.loadcell_x = loadcell_x
        self.loadcell_y = loadcell_y
        
        # Saved parameters.
        self.saved_power_x = None
        self.saved_power_y = None
        self.saved_cycles = None
         # Poll the result‐queue every 50 ms
        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.timeout.connect(self.poll_results)
        self._poll_timer.start(50)    # 50 ms → 20 Hz

        # Hard-coded destination for saving data.
        self.destination = "/data/output.txt"
        self.saving_data = False
        
        # ----- Build the GUI layout -----
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # Section 1: Test Type.
        test_type_group = QtWidgets.QGroupBox("Test Type")
        test_type_layout = QtWidgets.QHBoxLayout(test_type_group)
        self.rb_power_test = QtWidgets.QRadioButton("Power Test")
        self.rb_position_test = QtWidgets.QRadioButton("Position Test")
        self.rb_power_test.setChecked(True)
        test_type_layout.addWidget(self.rb_power_test)
        test_type_layout.addWidget(self.rb_position_test)
        main_layout.addWidget(test_type_group)
        
        # Section 2: Moment Type.
        moment_type_group = QtWidgets.QGroupBox("Moment Type")
        moment_type_layout = QtWidgets.QHBoxLayout(moment_type_group)
        self.rb_moment_x = QtWidgets.QRadioButton("X")
        self.rb_moment_y = QtWidgets.QRadioButton("Y")
        self.rb_moment_combined = QtWidgets.QRadioButton("Combined")
        self.rb_moment_x.setChecked(True)
        moment_type_layout.addWidget(self.rb_moment_x)
        moment_type_layout.addWidget(self.rb_moment_y)
        moment_type_layout.addWidget(self.rb_moment_combined)
        main_layout.addWidget(moment_type_group)
        
        # Section 3: Test Parameters.
        test_params_group = QtWidgets.QGroupBox("Test Parameters")
        test_params_layout = QtWidgets.QFormLayout(test_params_group)
        self.input_power_x = QtWidgets.QLineEdit()
        self.input_power_y = QtWidgets.QLineEdit()
        self.input_cycles = QtWidgets.QLineEdit()
        test_params_layout.addRow("Power X:", self.input_power_x)
        test_params_layout.addRow("Power Y:", self.input_power_y)
        test_params_layout.addRow("Antal cykler:", self.input_cycles)
        
        main_layout.addWidget(test_params_group)
        
        # Section 4: Active Power Display.
        active_power_group = QtWidgets.QGroupBox("Active Power")
        active_power_layout = QtWidgets.QGridLayout(active_power_group)

        # Create your labels...
        lbl_motor_x    = QtWidgets.QLabel("Motor torque X:")
        lbl_motor_y    = QtWidgets.QLabel("Motor torque Y:")
        lbl_loadcell_x = QtWidgets.QLabel("Loadcell X:")
        lbl_loadcell_y = QtWidgets.QLabel("Loadcell Y:")

        # Right‑justify each label’s text
        for lbl in (lbl_motor_x, lbl_motor_y, lbl_loadcell_x, lbl_loadcell_y):
            lbl.setAlignment(QtCore.Qt.AlignRight )

        # Create the line‑edits...
        self.active_power_x          = QtWidgets.QLineEdit(); self.active_power_x.setReadOnly(True)
        self.active_power_y          = QtWidgets.QLineEdit(); self.active_power_y.setReadOnly(True)
        self.active_power_x_loadcell = QtWidgets.QLineEdit(); self.active_power_x_loadcell.setReadOnly(True)
        self.active_power_y_loadcell = QtWidgets.QLineEdit(); self.active_power_y_loadcell.setReadOnly(True)

        # Now add them to the grid as before:
        active_power_layout.addWidget(lbl_motor_x,             0, 0)
        active_power_layout.addWidget(self.active_power_x,     0, 1)
        active_power_layout.addWidget(lbl_motor_y,             0, 2)
        active_power_layout.addWidget(self.active_power_y,     0, 3)
        active_power_layout.addWidget(lbl_loadcell_x,          1, 0)
        active_power_layout.addWidget(self.active_power_x_loadcell, 1, 1)
        active_power_layout.addWidget(lbl_loadcell_y,          1, 2)
        active_power_layout.addWidget(self.active_power_y_loadcell, 1, 3)
        main_layout.addWidget(active_power_group)

        
        # Section 5: Joystick Position.
        joystick_pos_group = QtWidgets.QGroupBox("Joystick Position")
        joystick_pos_layout = QtWidgets.QFormLayout(joystick_pos_group)
        self.joystick_pos_x = QtWidgets.QLineEdit()
        self.joystick_pos_x.setReadOnly(True)
        self.joystick_pos_y = QtWidgets.QLineEdit()
        self.joystick_pos_y.setReadOnly(True)
        joystick_pos_layout.addRow("Joystick X:", self.joystick_pos_x)
        joystick_pos_layout.addRow("Joystick Y:", self.joystick_pos_y)
        main_layout.addWidget(joystick_pos_group)
        
        # Section 6: Data Saving.
        data_saving_group = QtWidgets.QGroupBox("Data Saving")
        data_saving_layout = QtWidgets.QHBoxLayout(data_saving_group)
        self.destination_label = QtWidgets.QLabel(f"Saving data to: {self.destination}")
        self.saving_led = QtWidgets.QLabel()
        self.saving_led.setFixedSize(20, 20)
        self.set_saving_led("red")  # Initially not saving.
        data_saving_layout.addWidget(self.destination_label)
        data_saving_layout.addWidget(QtWidgets.QLabel("Status:"))
        data_saving_layout.addWidget(self.saving_led)
        main_layout.addWidget(data_saving_group)
        
        # Section 7: Sequence Controls.
        sequence_group = QtWidgets.QGroupBox("sequence Controls")
        sequence_layout = QtWidgets.QHBoxLayout(sequence_group)
        self.start_button = QtWidgets.QPushButton("Start")
        self.pause_button = QtWidgets.QPushButton("Paus")
        self.stop_button = QtWidgets.QPushButton("Stop")
        # Set colors.
        self.start_button.setStyleSheet(
            "background-color: #34A911; color: white; font-family: Arial; font-size: 20px; border-radius: 10px; padding: 6px;"
        )
        self.pause_button.setStyleSheet(
            "background-color: #9A8510; color: white; font-family: Arial; font-size: 20px; border-radius: 10px; padding: 6px;"
        )
        self.stop_button.setStyleSheet(
            "background-color: #901B1B; color: white; font-family: Arial; font-size: 20px; border-radius: 10px; padding: 6px;"
        )


        sequence_layout.addWidget(self.start_button)
        sequence_layout.addWidget(self.pause_button)
        sequence_layout.addWidget(self.stop_button)
        main_layout.addWidget(sequence_group)
        
        # ----- Connect Signals -----
        self.start_button.clicked.connect(self.start_sequence)
        self.pause_button.clicked.connect(self.pause_sequence)
        self.stop_button.clicked.connect(self.stop_sequence)
        
        # QTimer updates the GUI every 10 ms.
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_values)
        self.timer.start(10)
    
    def set_saving_led(self, color):
        """Set the LED indicator: green if saving; red if not."""
        if color.lower() == "green":
            self.saving_led.setStyleSheet("background-color: lightgreen; border-radius: 10px;")
        else:
            self.saving_led.setStyleSheet("background-color: red; border-radius: 10px;")

    def poll_results(self):
        global save_mode, pos_set
        """
        Called in the Qt event loop to drain ready results
        from your worker threads.
        """
        global encoder_x_start, encoder_y_start, task_done
        try:
            while True:
                func, args, res = _result_queue.get_nowait()
                if isinstance(res, Exception):
                    print(f"Task {func.__name__}{args} failed:", res)
                    pass
                else:
                    #print(f"Task {func.__name__}{args} succeeded:", res)
                    #print(func.__name__)
                    if func.__name__ == "set_torque" or func.__name__ == "set_torque_mode_two_motor":
                        print("Torque set to:", res)
                        save_mode = 2
                        #pos_set += 1
                        print("pos_set:", pos_set)
                    elif func.__name__ == "set_position_mode":
                        pos_set += 2
                    elif func.__name__ == "start_handling":
                        print("Handling complited.")
                        task_done = True
                        
                    elif func.__name__ == "simple_homing": 
                        encoder_x_start = motor_control.get_encoder_position(node_x)
                        #encoder_y_start = motor_control.get_encoder_position(node_y) 
                        print("Encoder X start:", encoder_x_start)
                        #print("Encoder Y start:", encoder_y_start)
                    

        except queue.Empty:
            pass
    def parse_int_input(self, s: str, default: int = 0) -> int:
        """
        Strip whitespace, allow negatives & floats, then cast to int.
        Empty → default; invalid → ValueError.
        """
        s = s.strip()
        if not s:
            return default
        try:
            return int(float(s))
        except ValueError:
            raise ValueError(f"Invalid numeric input: {s!r}")
    
    @QtCore.Slot()
    def start_sequence(self):
        """Save inputs and simulate starting the test sequence (data saving begins)."""
        try:
            self.saved_power_x = self.parse_int_input(self.input_power_x.text())
            self.saved_power_y = self.parse_int_input(self.input_power_y.text())
            self.saved_cycles  = self.parse_int_input(self.input_cycles.text())
        except ValueError as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return

        
        print("Starting sequence with:")
        test_type = ("Power_Test" if self.rb_power_test.isChecked() else "Position_Test")
        moment = ("X" if self.rb_moment_x.isChecked() else 
                  "Y" if self.rb_moment_y.isChecked() else "Combined")
        print("Moment Type:", moment)
        print("Power X:", self.saved_power_x)
        print("Power Y:", self.saved_power_y)
        print("Antal cykler:", self.saved_cycles)
        submit(start_handling, test_type, moment, self.saved_power_x, self.saved_power_y, self.saved_cycles)      

    
    @QtCore.Slot()
    def pause_sequence(self):
        if self.pause_button.text() == "Pause":
            self.pause_button.setText("Play")
            self.pause_button.setStyleSheet(
            "background-color: green; color: white; font-family: Arial; font-size: 20px; border-radius: 10px; padding: 6px;"
        )
        else:
            self.pause_button.setText("Pause")
            self.pause_button.setStyleSheet(
            "background-color: #9A8510; color: white; font-family: Arial; font-size: 20px; border-radius: 10px; padding: 6px;"
        )
        #submit(set_upp_motor)
    @QtCore.Slot()
    def stop_sequence(self):
        """Stop the test sequence."""
        print("Stop clicked.")
        try:
            sys.exit(self.app.exec())
        except KeyboardInterrupt:
            print("\nKeyboardInterrupt received. Exiting.")
            stop_event.set()


    
    def update_values(self):

        # Update for X:
        try:
            data_x_item = self.data_x.get_nowait()
            lodacell_x_item = self.loadcell_x.get_nowait()
            #print(lodacell_x_item)
            active_power_x = lodacell_x_item["x"] 
            joystick_x_raw = data_x_item["x"]  
            joystick_x_pos = data_x_item["x_d"]  

            if(joystick_x_pos == 1): #left = 1, right = 2
                joystick_x_raw *= -1

            joystick_x = joystick_x_raw
            self.active_power_x_loadcell.setText(f"{active_power_x:.2f}")
            self.joystick_pos_x.setText(f"{joystick_x_raw:.2f} ")

        except queue.Empty:
            active_power_x = joystick_x_raw = joystick_x_pos = 0

        # Update for Y:
        try:
            data_y_item = self.data_y.get_nowait()
            loadcell_y_item = self.loadcell_y.get_nowait()
            active_power_y = loadcell_y_item["y"] 
            joystick_y_raw = data_y_item["y"]  
            joystick_y_pos = data_y_item["y_d"]  
            if(joystick_y_pos == 1): #down = 1, up = 2
                joystick_y_raw *= -1    
            joystick_y = joystick_y_raw
            self.active_power_y_loadcell.setText(f"{active_power_y:.2f}")
            self.joystick_pos_y.setText(f"{joystick_y_raw:.2f}")
        except queue.Empty:
            active_power_y = joystick_y_raw = joystick_y_pos = 0
       
def main():
    init_motor()

    # Create and start hardware-reading threads.
    t1 = threading.Thread(target=qe_command.qe_read, args=(data_x, data_y), daemon=True)
    t2 = threading.Thread(target=dac.load_cell_read, args=(loadcell_x,loadcell_y, stop_event_load_cell), daemon=True)
    
    t1.start()
    t2.start()
   
    # Create the Qt application and instantiate the GUI, passing in the queues.
    app = QtWidgets.QApplication(sys.argv)
    widget = MyWidget(data_x, data_y, loadcell_x, loadcell_y)
    widget.app = app  # Store the app reference in the widget
    
    widget.resize(800, 600)
    widget.show()
    

    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Exiting.")
        stop_event.set()

if __name__ == '__main__':
    main()
    print("Program terminated.")

