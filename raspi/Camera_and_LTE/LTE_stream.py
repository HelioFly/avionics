# This script does the following:
#	1) Record H264 Video using PiCam at a maximum bitrate of 300 kbps
#	2) Stream video data to a local BytesIO object
#	3) Send raw data over LTE
#	4) Store raw data to an onboard file
#	5) Clears BytesIO object after network stream and file store
#	6) Interrupts and ends recording after 'record_time' seconds

# Author: Ronnie Ankner
# Last Edited: 10/2/19
# Libraries
#	-> picamera -> PiCamera: Enables pi cam interfacing and settings manipulation
#	-> picamera -> CircularIO: Allows for a circular buffer (if we want one)
#	-> threading: enables timer interrupt
#	-> io -> BytesIO : local file-like object that camera streams to
#	-> socket: allows for UDP socket and message sending
#	-> Hologram.HologramCloud -> HologramCloud: LTE API to send data over an LTE network

from picamera import PiCamera
from picamera import CircularIO
from io import BytesIO
from Hologram.HologramCloud import HologramCloud
import threading
import socket
import time
import os

#======================= Global Variables and Objects =================
#Global Variables
lte = True
wifi = not(lte)
record_file = 'buffer_recording.h264' #on-board file video is stored to
bitrate_max = 100000 # bits per second
record_time = 8 # Time in seconds that the recording runs for
record_chunk = 0.1 #chunk size in seconds video object is broken into and sent 
frame_rate = 15 #camera frame rate
interrupt_bool = False #global interrupt flag that ends recording/program
store_and_send_bool = False #global interrupt flag that initiates sending and storing of camera data

#ensures chunk size is not smaller than one frame
if record_chunk < 1/frame_rate:
	record_chunk = 1/frame_rate

#Camera Settings
camera = PiCamera()
camera.resolution = (320, 240)
camera.framerate = frame_rate

if lte:
	#LTE Network Streaming
	credentials = {'devicekey': '8K0Dyq*7'}
	hologram = HologramCloud(credentials, network='cellular')
if wifi:
	#Wifi UDP Network Streaming
	STREAM_IP = '127.0.0.1'
	STREAM_PORT = 4000
	send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#========================= Functions =================================
def interrupt_func():
	#Interrupt function that ends camera streaming and program
	global interrupt_bool
	interrupt_bool = True
	print("Program Timer up")

def store_interrupt_func():
	#interrupt function that initiates sending and storing camera data
	global store_and_send_bool
	store_and_send_bool = True
	#threading.Timer(record_chunk, store_interrupt_func).start()

def send_network(msg):
	if lte:
		#Sends data over LTE
		msg_err = hologram.sendMessage(msg, timeout = 1)
	if wifi:
		#Sends data over Wifi UDP
		send_sock.sendto(msg, (STREAM_IP, STREAM_PORT))

#======================== Video Streaming and Recording ============
loop_cnt = 0.0
cnt = 0
#camera.start_preview()

#=================== Stores to local BytesIO then sends========================
#		    MOST EFFICENT AND TEST-PROVEN METHOD
if lte:
	#Initialize LTE Network Connection
	connected = 0
	while not(connected == 1):
		os.system("sudo hologram network disconnect")
		if connected == 0:
			print("Not Connected (%d)\n -> Connecting"%(connected))
			hologram.network.connect(timeout = 10)
		else:
			print("Trying to Reconnect (%d)"%(connected))
			hologram.network.disconnect()
			hologram.network.connect(timeout = 10)
		connected  = hologram.network.getConnectionStatus()
	print("Connected!")

#Initialize local stream object
stream = BytesIO()
#stream = CircularIO(int((10*bitrate_max*record_chunk)/8))

#Open and/or create onboard file to store to
camera_file_handle = open(record_file, 'wb+')

#Begin Pi Cam recording
camera.start_recording(stream, format='h264', bitrate=bitrate_max)

print("Beginning Program")
#Start timer threads
threading.Timer(record_time, interrupt_func).start()
threading.Timer(record_chunk, store_interrupt_func).start()

loop_sum = 0
comms_sum = 0
store_sum = 0
random_cnt = 0
program_start = time.time()
#Main Program Loop
while not(interrupt_bool):
	#camera.wait_recording(record_chunk)
	if (store_and_send_bool):
		threading.Timer(record_chunk, store_interrupt_func).start()
		loop_start = time.time()
		#executes when record_chunk thread times out
		#controls how often data is ported ofver the network and to file
		#change 'record_chunk' to vary time and data size
		
		#Reset global interrupt flag
		store_and_send_bool = False

		#Send bytes-like date over the Network (UDP)
		comms_start = time.time()
		send_network(stream.getvalue())
		comms_sum += (time.time()-comms_start)		
		
		#Store bytes-like data to file 
		store_start = time.time()
		camera_file_handle.write(stream.getvalue())
		store_sum += (time.time()-store_start)

		#Clear local file-like object
		stream.truncate(0)
		stream.seek(0)

		#[Optional] Print Diagnostic printout
		cnt+=1
		print("Sent and Saved Chunk #%d | Loop Time: %f"%(cnt, (time.time()-loop_start)))
		loop_sum+=(time.time() - loop_start)
		
#======================================================================================

#End Recording and Tidy Up
total_time = time.time() - program_start 
print("Ending Recording")
camera.stop_recording()
print("Closing Video File")
camera_file_handle.close()
print("Program Time: %fs"%(total_time))
print("Process Time: %fs | Process Usage: %f%%"%(loop_sum, (loop_sum*100)/total_time))
print("\tComms: %fs | %f%%\n\tStore: %fs | %f%%"%(comms_sum, (comms_sum*100)/loop_sum, store_sum,(store_sum*100)/loop_sum))


#camera.stop_preview()
