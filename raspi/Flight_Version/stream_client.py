# This script does the following:
#	1) Record H264 Video using PiCam at a maximum bitrate of {bitrate_max} kbps
#	2) Record video data to a local BytesIO object
#	3) Send raw data over a TCP socket to a ground server
#	4) Store raw data to an onboard file
#	5) Clears BytesIO object after network stream and file store
#	6) Interrupts and ends recording after 'record_time' seconds

#	Client: RASPI
#	Server: COMPUTER

# Author: Ronnie Ankner
# Last Edited: 11/1/19
# Libraries
#	-> picamera -> PiCamera: Enables pi cam interfacing and settings manipulation
#	-> picamera -> PiCameraCircularIO: Allows for a circular buffer (if we want one)
#	-> threading: enables timer interrupt
#	-> io -> BytesIO : local file-like object that camera streams to
#	-> socket: allows for UDP socket and message sending
#	-> time: used to measure timing aspects of the system
#	-> os: runs terminal commands from python
#	-> sys: used exclusively for exiting the program


from picamera import PiCamera
from picamera import CircularIO
from io import BytesIO
import threading
import socket
import time
import os
import sys

#======================= Global Variables and Objects =================
#Global Variables
record_file = 'buffer_recording.h264' #on-board file video is stored to
bitrate_max = 200000 # bits per second
record_time = 10 # Time in seconds that the recording runs for
record_chunk = 0.1 #chunk size in seconds video object is broken into and sent 
frame_rate = 15 #camera frame rate
interrupt_bool = False #global interrupt flag that ends recording/program
store_and_send_bool = False #global interrupt flag that initiates sending and storing of camera data

#ensures chunk size is not smaller than one frame
if record_chunk < 1/frame_rate:
	record_chunk = 1/frame_rate

#Camera Settings
camera = PiCamera()
camera.resolution = (640, 480)
camera.framerate = frame_rate

#Network Setup
SERVER_IP = '73.136.139.198'
SERVER_PORT = 5000

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print("RASPI CLIENT Socket Created")

sock.connect((SERVER_IP, SERVER_PORT))
print("RASPI CLIENT Connected to COMPUTER SERVER!\nWAITING FOR VIDEO")
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

def send_network(client_sock, msg):
	client_sock.sendall(msg)

#======================== Video Streaming and Recording ============
loop_cnt = 0.0
cnt = 0
#camera.start_preview()

#=================== Stores to local BytesIO then sends========================
#		    MOST EFFICENT AND TEST-PROVEN METHOD

#Initialize local stream object
stream = BytesIO()
#stream = CircularIO(int((10*bitrate_max*record_chunk)/8))

#Open and/or create onboard file to store to
camera_file_handle = open(record_file, 'wb+')

print("Beginning Stream!")

#Begin Pi Cam recording
camera.start_recording(stream, format='h264', bitrate=bitrate_max)

#Start timer threads
threading.Timer(record_time, interrupt_func).start()
threading.Timer(record_chunk, store_interrupt_func).start()

loop_sum = 0
comms_sum = 0
store_sum = 0
random_cnt = 0
program_start = time.time()
max_packet = 0
max_comms = 0
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
		
		#Get Buffer Size:
		buff_size = stream.getbuffer().nbytes

		#Send bytes-like date over the Network (UDP)
		comms_start = time.time()
		send_network(sock, stream.getvalue())
		comms_time = (time.time()-comms_start)
		comms_sum += comms_time		
		
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
		print("\tComms Time: %fs"%(comms_time))
		print("\tData Size: %d Bytes | %d bits"%(buff_size, buff_size*8))
		print("\tApparent Data Rate: %d kbps"%(float(buff_size*8)/(comms_time*1000)))
		if buff_size > max_packet:
			max_packet = buff_size
		if comms_time > max_comms:
			max_comms = comms_time
		loop_sum+=(time.time() - loop_start)
		
#======================================================================================

#End Recording and Tidy Up
total_time = time.time() - program_start 
print("Closing Connection")
sock.close()
print("Ending Recording")
camera.stop_recording()
print("Closing Video File")
camera_file_handle.close()
print("Program Time:  %fs"%(total_time))
print("Process Time:  %fs | Process Usage: %f%%"%(loop_sum, (loop_sum*100)/total_time))
print("\tComms: %fs | %f%%\n\tStore: %fs | %f%%"%(comms_sum, (comms_sum*100)/loop_sum, store_sum,(store_sum*100)/loop_sum))
print("Stream Metrics:\n\tMax Packet Size: %d Bytes\n\tMax Send Time  : %f ms"%(max_packet, max_comms*1000))


#camera.stop_preview()
