#!/usr/bin/env python3

import matplotlib
matplotlib.use('GTK3Cairo')
import sys
import time
import paho.mqtt.client as mqtt
import pandas as pd
import matplotlib.pyplot as plt
plt.close('all')
import matplotlib.animation as animation
import numpy as np

if len(sys.argv) < 2:
    print('Usage: ./mqttplot <MQTT server address>\n')
    exit()

fs = 450 # Sampling rate; according to TGAM1 datasheet, should be 500Hz
         # Going with 450 samples per second to allow for WiFi lag, etc.
n_fs = 0
update_interval = 1*1000 # milliseconds
data = [0] * fs * int(update_interval / 1000 * 2) # for holding 2 seconds of data
colors = [(74/255,151/255,255/255),
          (255/255,200/255,83/255),
          (29/255,188/255,0/255),
          (255/255,85/255,34/255),
          (164/255,97/255,177/255)]
df = pd.DataFrame(columns = ['band', 'val']) # Pandas data frame
max_adc = 32768
max_uV = 100 # max. estimated microvolts attainable with an on-scalp EEG
mqtt_address = sys.argv[1]
mqtt_port = 1883
# EEG band ranges in Hz
eeg_bands = {'Delta': ( 0,  4),
             'Theta': ( 4,  8),
             'Alpha': ( 8, 12),
             'Beta':  (12, 30),
             'Gamma': (30, 45)}


def on_connect(client, userdata, flags, rc):
    print('Connecting to MQTT message broker... ', end='')
    client.subscribe('MindFlex/data')
    print('success')


def on_message(client, userdata, msg):
    global fs, n_fs
    adc_val = int(msg.payload, 10) # signed short on ESP8266 (i.e. int16_t)
    uV = (adc_val / max_adc) * max_uV
    if n_fs < fs:
        data.pop(0)
        data.append(uV)
        print(uV)
        n_fs = n_fs + 1


def on_window_close(e):
    mqtt_client.loop_stop()
    print('window closed')


def get_data():
    c = mqtt.Client()
    c.on_connect = on_connect
    c.on_message = on_message
    c.connect(mqtt_address, mqtt_port, 60)
    c.loop_start()
    return c


# https://dsp.stackexchange.com/questions/45345/how-to-correctly-compute-the-eeg-frequency-bands-with-python/45662#45662
def perform_fft():
    # perform FFT
    fft_vals = np.absolute(np.fft.rfft(data))
    fft_freq = np.fft.rfftfreq(len(data), 1.0/fs)
    # take the mean of the fft amplitude for each EEG band
    eeg_band_fft = dict()
    for band in eeg_bands:
        i_freq = np.where((fft_freq >= eeg_bands[band][0]) &
                          (fft_freq <= eeg_bands[band][1]))[0]
        eeg_band_fft[band] = np.mean(fft_vals[i_freq])
    # prepare the data for plotting
    df.iloc[0:0] # empty out the dataframe
    df['band'] = eeg_bands.keys()
    df['val'] = [eeg_band_fft[band] for band in eeg_bands]
    print(df)
    # plot data using matplotlib
    plt.cla()
    df.plot.bar(x='band', y='val', legend=False, color=colors, ax=axes)
    axes.set_xlabel('EEG band')
    axes.set_ylabel('Mean band amplitude')


def animate(i):
    global fs, n_fs
    if n_fs == fs:
        perform_fft()
        # Start to accumulate new sample pair
        n_fs = 0


if __name__ == '__main__':
    mqtt_client = get_data()
    fig = plt.figure(figsize=(10,8), dpi=75)
    fig.canvas.mpl_connect('close_event', on_window_close)
    axes = fig.add_subplot(111) # 1 subplot in geometry 1x1
    ani = animation.FuncAnimation(fig, animate, interval=update_interval)
    print('Streaming data... ', end='', flush=True)
    plt.show()