#!/bin/python3
import tkinter as tk
from tkinter import ttk
import threading
import socket
import time
import requests
import configparser
from tkinter import font as tkFont

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

# Funktion zur Formatierung der Frequenzanzeige mit "MHz"
def format_frequency(frequency):
    if len(frequency) > 1:
        return f"{frequency[0]}.{frequency[1:]}"
    else:
        return frequency  # Fallback falls die Frequenz zu kurz ist

# Update the GUI with the current data
def update_display(frequency, mode, power):
    formatted_frequency = format_frequency(frequency)  # Formatiere die Frequenz für die Anzeige
    frequency_label.config(text=formatted_frequency)
    mode_label.config(text=mode)
    power_bar['value'] = power

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
