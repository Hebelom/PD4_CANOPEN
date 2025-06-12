import datetime

# Module-level filename; set by create_file()
_filename = None


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


# Example usage when running this module directly
if __name__ == "__main__":
    fn = create_file()
    print(f"Logging to {fn}")
    # Append a couple of sample rows
    save_test_data(1.23, 4.56, "Left", "Down", 100, 200)
    save_test_data(2.34, 5.67, "Right", "Up", 150, 250)
    print("Done.")
