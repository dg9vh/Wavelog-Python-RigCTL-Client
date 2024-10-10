#!/bin/python3
import tkinter as tk
from tkinter import ttk
import threading
import socket
import time
import requests
import configparser
from tkinter import font as tkFont

# Flag for Blinking-State
is_blinking = False

# reading configuration from ini-file
config = configparser.ConfigParser()
config.read('config.ini')

# configuring connection to rigctld
RIGCTLD_HOST = config.get('rigctld', 'host')
RIGCTLD_PORT = config.getint('rigctld', 'port')

# configuring Wavelog-API
CLOUDLOG_URL = config.get('cloudlog', 'url')
API_KEY = config.get('cloudlog', 'api_key')

# reading poll-interval
POLL_INTERVAL = config.getint('settings', 'poll_interval')

# creating socket to rigctld
def connect_to_rigctld(host, port):
    try:
        rig_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        rig_sock.connect((host, port))
        return rig_sock
    except socket.error as e:
        log_message(f"Error connecting to rigctld: {e} - Retrying in 10 Seconds")
        time.sleep(10)
        return connect_to_rigctld(host, port)

# sending command to rigctld and receiving answer
def send_command(sock, command):
    try:
        sock.sendall((command + '\n').encode('utf-8'))
        response = sock.recv(1024).decode('utf-8').strip()
        return response
    except socket.error as e:
        log_message(f"Error sending the command: {e}")
        return None

# updating Wavelog API-data
def update_cloudlog(frequency, mode, power):
    headers = {
        'Content-Type': 'application/json'
    }
    payload = {
        'key': API_KEY,
        'radio': 'Wavelog Python Client',
        'frequency': frequency,
        'mode': mode,
        'power': power
    }
    log_message(f"New data: {payload}")
    try:
        response = requests.post(CLOUDLOG_URL, headers=headers, json=payload)
        if response.status_code == 200:
            log_message("Radio-information actualized successfully.")
        else:
            log_message(f"Error actualizing Wavelog: {response.status_code} {response.text}")
    except requests.RequestException as e:
        log_message(f"Error connecting to Wavelog: {e}")

# Log message in the text area
def log_message(message):
    log_text.insert(tk.END, f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
    log_text.see(tk.END)

# funktion for formatting with "MHz"
def format_frequency(frequency):
    if int(frequency) < 10000000:
        return f"{frequency[0]}.{frequency[1:]}"
    else:
        return f"{frequency[0:2]}.{frequency[2:]}"


# function to reconnect
def reconnect():
    global rig_sock
    rig_sock = connect_to_rigctld(RIGCTLD_HOST, RIGCTLD_PORT)
    if rig_sock:
        log_message("Reconnected to rigctld. Restarting data fetching...")
        # Starte die Hauptschleife in einem neuen Thread, um die GUI nicht zu blockieren
        threading.Thread(target=main_loop, daemon=True).start()
    else:
        log_message("Failed to reconnect to rigctld.")
        
def toggle_led():
    led_label.config(bg="red")
    root.update()  # Force the GUI to update immediately
    time.sleep(0.2)  # Adjust the delay as needed
    led_label.config(bg="black")

# function to check if within bandplan
def is_within_iaru_region1(frequency):
    # Region 1 bandplan
    bands = [
        (1810000, 2000000),  # 160m Band
        (3500000, 3800000),  # 80m Band
        (5351500, 5366500),  # 60m Band
        (7000000, 7200000),  # 40m Band
        (10100000, 10150000), # 30m Band
        (14000000, 14350000), # 20m Band
        (18068000, 18168000), # 17m Band
        (21000000, 21450000), # 15m Band
        (24890000, 24990000), # 12m Band
        (28000000, 29700000), # 10m Band
        (50000000, 52000000), # 6m Band
        (70150000, 70250000)  # 4m Band
    ]
    
    # Check if QRG in bandplan
    for (lower, upper) in bands:
        if lower <= int(frequency) <= upper:
            return True
    return False

# blinking of the frequency
def blink_frequency():
    global is_blinking
    if is_blinking:
        current_color = frequency_label.cget("fg")
        new_color = "red" if current_color == "black" else "black"
        frequency_label.config(fg=new_color)
        root.after(500, blink_frequency)  # Blinks every 500 ms

# Update the GUI with the current data
def update_display(frequency, mode, power):
    global is_blinking
    formatted_frequency = format_frequency(frequency)  # formatting QRG for output
    frequency_label.config(text=formatted_frequency)
    mhz_label.config(text="MHz")
    mode_label.config(text=mode)
    power_bar['value'] = power

    # check, if QRG is within Region 1 bandplan
    if is_within_iaru_region1(frequency):
        # if in - stop blinking
        is_blinking = False
        frequency_label.config(fg="red")
    else:
        # if out - start blinking
        if not is_blinking:
            is_blinking = True
            blink_frequency()

# Main-function for fetching the data
def main_loop():
    rig_sock = connect_to_rigctld(RIGCTLD_HOST, RIGCTLD_PORT)
    if not rig_sock:
        return

    # initial values
    last_frequency = None
    last_mode = None
    last_power_level = None

    try:
        while True:
            # actual frequency
            frequency = send_command(rig_sock, 'f')

            # power level
            power_level = send_command(rig_sock, 'l RFPOWER')
            try:
                power_level = float(power_level) * 100
            except ValueError:
                power_level = 0.0  # Fallback on converting error

            # mode
            mode_response = send_command(rig_sock, 'm')
            mode = mode_response.split('\n')[0] if mode_response else 'Unknown'
            
            # Toggle the LED after each poll
            toggle_led()
            
            # do we have any new value?
            if (frequency != last_frequency or mode != last_mode or power_level != last_power_level):
                # only updating if any value changed
                update_cloudlog(frequency, mode, power_level)
                root.after(0, update_display, frequency, mode, power_level)

                # actualizing last values
                last_frequency = frequency
                last_mode = mode
                last_power_level = power_level

            # wait for next poll
            time.sleep(POLL_INTERVAL)
    finally:
        rig_sock.close()



# Setup GUI
root = tk.Tk()
root.title("Wavelog Client")
root.geometry("500x380")

# Lade und verwende die 7-Segment Schriftart für die Frequenz
seven_seg_font = tkFont.Font(family="DSEG7 Classic", size=40)  # Passe hier den Namen der installierten Schriftart an

# Frequenz-Label
frequency_frame = tk.Frame(root)
frequency_label = tk.Label(frequency_frame, text="0000000", font=seven_seg_font, fg="red")
frequency_label.pack(side=tk.LEFT)

# MHz-Label mit gleicher Schriftgröße und Schriftart wie der Mode
mhz_label = tk.Label(frequency_frame, text="MHz", font=("Courier", 20), fg="red")
mhz_label.pack(side=tk.LEFT)

frequency_frame.pack()

# Mode Label
mode_label = tk.Label(root, text="USB", font=("Courier", 20), fg="red")
mode_label.pack()

# Power Progressbar
power_bar = ttk.Progressbar(root, length=300, mode='determinate')
power_bar.pack(pady=10)

# Log Text Area
log_text = tk.Text(root, height=10, wrap=tk.WORD)
log_text.pack(fill=tk.BOTH, expand=True)

# creating a reconnect button
reconnect_button = ttk.Button(root, text="Reconnect", command=reconnect)
reconnect_button.pack(pady=0)

# Create a label for the LED
led_label = tk.Label(root, bg="black", width=2, height=1)
led_label.pack(side=tk.RIGHT)

# Starte die Hauptschleife in einem separaten Thread
threading.Thread(target=main_loop, daemon=True).start()

root.mainloop()
