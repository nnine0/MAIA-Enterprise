import time
import subprocess
import os

def check_trigger():
    # Check for a trigger file or API call
    # For simplicity, poll for a file
    trigger_file = "/data_logs/trigger_update"
    if os.path.exists(trigger_file):
        os.remove(trigger_file)
        return True
    return False

def run_update():
    # Run the update process
    result = subprocess.run(["python", "train_update.py"], capture_output=True, text=True)
    print("Update result:", result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)

if __name__ == "__main__":
    print("Trainer waiting for trigger...")
    while True:
        if check_trigger():
            print("Trigger detected, running update...")
            run_update()
        time.sleep(60)  # Check every minute