import socket

import sys

import time

import select

import threading

from threading import Timer

from time import sleep

from threading import *

router_id = 0
INPUT_PORT = []
OUTPUT_PORT = []
COST = []
timer_status = ["timeout", "garbage"]
UDP_IP = "127.0.0.1"
BUFFSIZE = 1024
FORWARDING_TABLE = {}  # a dictionnary contain all tables for each router
INPUT_SOCKET_LIST = []
TIME_INTERVAL = [30, 60 ,90] #normal update, garbage collection, timeout
TIME_DIC = {}  #for each router it has two timer  {1: [timeout], 2 ...}



def parser(filename):
	'''function to extract router id,  input port number and output port number from configuration files'''
	global router_id
	start = 0
	end = 0
	new_config = []
	long_new = []
	new1 = []
	new2 = []
	new3 = []
	try:
		open(filename)
	except FileNotFoundError:
		print("can't find such file in your dirctory")
	finally:
		infile = open(filename)
		lines = infile.readlines()
		for line in lines:
			line = line.split(' ')
			for part in line:
				part = part.rstrip()
				long_new.append(part)

		for q in range(0, 2):
			new1.append(long_new[q])
			start = 2

		for w in range(start, len(long_new)):
			if(long_new[w] == "outputs"):
				end = long_new.index("outputs")

		for t in range(start, end):
			new2.append(long_new[t])
			start = end 

		for p in range(start, len(long_new)):
			new3.append(long_new[p])

		new_config.append(new1)
		new_config.append(new2)
		new_config.append(new3)
			
		if new_config[0][0] == "router_id":
			if 1 <= int(new_config[0][1]) <= 64000:
				router_id= int(new_config[0][1])
			else:
				print("invaild router id")
				sys.exit()
		if new_config[1][0] == "input-ports":
			for i in range(1, len(new_config[1])):
				if 1024 <= int(new_config[1][i]) <= 64000:
					INPUT_PORT.append(new_config[1][i])

				else:
					print("invaild port number")
					sys.exit()
		if new_config[2][0] == "outputs":
			for j in range(1, len(new_config[2])):
				OUTPUT_PORT.append(new_config[2][j])


def create_socket():
	'''create sockets as many as how many input ports, then bind them with '127.0.01' and input ports'''
	
	
	for i in range(len(INPUT_PORT)):
		
		try:
			sockets = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			sockets.bind((UDP_IP, int(INPUT_PORT[i])))
			INPUT_SOCKET_LIST.append(sockets)
			
		except:
			print("fail to create input socket")
			sys.exit()
		





def buildMessage(neigbour_id, times=1):
	'''build RIP packet in order to transport by using socket,
	main conponents are sender id, destinnation id and metric'''
	result = []
	

	bits = ''
	bits += "{:08b}".format(2)   #command field
	bits += "{:08b}".format(2)			#version field
	bits += "{:08b}".format(0)			# must be zero
	bits += "{:08b}".format(int(router_id)) # sender id
	for destination_id, metric, next_hop in FORWARDING_TABLE.values():
		bits += "{:08b}".format(0)		#address family identifier
		bits += "{:08b}".format(0)		#must be zero
		bits += "{:08b}".format(0)   #must be zero 
		bits += "{:08b}".format(0)
		bits += "{:08b}".format(destination_id) #destination_id
		bits += "{:08b}".format(0)		
		bits += "{:08b}".format(0)		
		bits += "{:08b}".format(0)   
		bits += "{:08b}".format(0)		
		bits += "{:08b}".format(0)	
		bits += "{:08b}".format(0)		
		bits += "{:08b}".format(0)	
		bits += "{:08b}".format(0)		
		bits += "{:08b}".format(0)	
		bits += "{:08b}".format(0)		
		bits += "{:08b}".format(0)
		bits += "{:08b}".format(0)		
		bits += "{:08b}".format(0)	
		bits += "{:08b}".format(0)
		if next_hop == neigbour_id and times != 0:
			bits += "{:08b}".format(16)
		else:
			bits += "{:08b}".format(metric)

		
	need = ""
	for i in bits:
		need += i
		if len(need) == 8:
			result.append(int(need, 2))
			need = ""
	# print(result)
	return bytearray(result)



def parser_FORWARDING_TABLE():
	'''parse varialbe from global in order to generate forwarding table

	table format is like {1:[2, 1 ,2] 2: [7, 8, 7]......}'''
	table = []
	for outport in OUTPUT_PORT:
		outport = outport.split('-')
		COST.append(outport)
		destination_id = int(outport[2])
		metric = int(outport[1])
		nextHop = int(outport[2])
		table.append(destination_id)
		table.append(metric)
		table.append(nextHop)
		FORWARDING_TABLE[destination_id] = table
		table = []
		set_timeout_timer(nextHop, "timeout")   
		
	
def print_FORWARDING_TABLE():
	'''Prints the forwarading table created by parser_FORWARDING_TABLE function'''
	print("================================================")
	print("Router id : {}".format(router_id))
	print("Destinations", "   Metrics", "      Next Hops\n")
	for i in FORWARDING_TABLE.copy().keys():
		print('     {}            {}             {}\n'.format(FORWARDING_TABLE[i][0], FORWARDING_TABLE[i][1], FORWARDING_TABLE[i][2]))
		
	print("================================================")



def sendUpdate(times=1):  
	'''build the message and then send to next hop(neighbour) via one of the input socket to matching output port number'''
	
	for temp_port in OUTPUT_PORT:
		temp_port = temp_port.split("-")
		outport = int(temp_port[0])
		next_hop = int(temp_port[2])
		
		
		message = buildMessage(next_hop, times)
		INPUT_SOCKET_LIST[0].sendto(message, (UDP_IP, outport))

def getCurrentMetric(sender_id):
	for cost in COST:
		if int(cost[2]) == sender_id:
			return int(cost[1])
		
	
def update_FORWARDING_TABLE(neigbour_id, result): #result = [destination , metric]
	'''update forwarding table by following steps
	1. check whether the destinnation id in the forwarding table, 
	2. if it is and new metric is less than the current metric, update it, reset the destination id timer.
	3. if it is and new metric is larger than the current metric, then check whether the sender is next hop(mean peer routers), if it is force update with new metric, if not just ignore the packet
	4. if not in the forwarding table, generate new key and values into dictionaty, create new timer for it'''
	change = 0
	for [destination_id, metric] in result:
		# print( [destination_id, metric])
		current_metric = getCurrentMetric(neigbour_id)
		# print("*****")
		# print(current_metric)
		# print("*****")
		new_metric = current_metric + metric
		# print("--------")
		# print(new_metric)
		# print("--------")
		if destination_id in FORWARDING_TABLE.keys():
			if new_metric < FORWARDING_TABLE[destination_id][1]:
				FORWARDING_TABLE[destination_id] = [destination_id, new_metric, neigbour_id]
				set_timeout_timer(destination_id, "timeout")
				change = 1
			else: 
				
				if neigbour_id == FORWARDING_TABLE[destination_id][2]:
					if new_metric <= 15:
						FORWARDING_TABLE[destination_id] = [destination_id, new_metric, neigbour_id]
						set_timeout_timer(destination_id, "timeout")
						change = 1
					else: 
						if new_metric >= 16:
							FORWARDING_TABLE[destination_id] = [destination_id, 16, neigbour_id]
							set_garbage_collection_timer(destination_id, "timeout")
							change = 1
				
				

		else:
			if new_metric <= 15:
				if router_id == destination_id:
					FORWARDING_TABLE[neigbour_id] = [neigbour_id, metric, neigbour_id]
					set_timeout_timer(neigbour_id, "timeout")
					change = 1
				elif router_id != destination_id:
					FORWARDING_TABLE[destination_id] = [destination_id, new_metric, neigbour_id]
					set_timeout_timer(destination_id, "timeout")
					change = 1
			elif new_metric == 16 :
				if router_id == destination_id:
					FORWARDING_TABLE[neigbour_id] = [neigbour_id, metric, neigbour_id]
					set_timeout_timer(neigbour_id, "timeout")
					change = 1


	if change == 1:
		print_FORWARDING_TABLE()
			


def parseRIPMessage(data):
	'''check the header of the packet then paser information from the message packet'''
	result = []
	sender = 0
	destination = 0
	metric = 0
	datalist = list(data)
	if datalist[0] != 2 or datalist[1] != 2 or datalist[2] != 0:
		print("invaild packet")
		sys.exit()
	else:
		sender = datalist[3]
		info_part = datalist[4:]
		for index in range(0, len(info_part), 20):
			destination = info_part[index + 4]
			metric = info_part[index + 19]
			result.append([destination, metric])
	# print(sender, result)
	set_timeout_timer(sender, "timeout")
	return sender, result





def set_timeout_timer(router_id, status):
	'''a timeout timer to count to 90s in order to check whether this route is break or not
	idea: if in time_dic refresh the current timer, if not create a timer for it '''



	if status == timer_status[0]:
		routers = []
		for r_id in TIME_DIC.keys():
			routers.append(r_id)
		
		
		if router_id not in routers:  
			time = threading.Timer(TIME_INTERVAL[2], trigger_update, (router_id,))
			TIME_DIC[router_id] = time
			time.start()
		else:
			time = TIME_DIC[router_id]
			time.cancel()
			del TIME_DIC[router_id]
			timeout = threading.Timer(TIME_INTERVAL[2], trigger_update, (router_id,))
			TIME_DIC[router_id] = timeout
			timeout.start()


def set_garbage_collection_timer(router_id, status):
	'''a timeout timer to count to 60s in order to check whether need to delete this break route'''
	if status == timer_status[1]:
		timeout = TIME_DIC[router_id]
		timeout.cancel()
		del TIME_DIC[router_id]
		garbage_time = threading.Timer(TIME_INTERVAL[1], delete_timeout_route, (router_id,))
		TIME_DIC[router_id] = garbage_time
		garbage_time.start()

	


def delete_timeout_route(router_id):
	'''delete the route if reach garbage collection timer maxium time'''
	if router_id in FORWARDING_TABLE.keys():
		del FORWARDING_TABLE[router_id]
		print("succesfully delete the router {}".format(router_id))
		
	else:
		print("there is no such router need to be delete")
	


def trigger_update(router_id):
	'''if timeout happen, set the corrspond router id metric to 16 and start the garbage collection timer, and immeditely send the update so neighbours can update their table as well
	'''
	
	print("router id : {} has timeout, garbage_collection timer has started".format(router_id))

	for r_id in FORWARDING_TABLE.keys():
		if r_id == router_id:
			FORWARDING_TABLE[r_id][1] = 16

	set_garbage_collection_timer(router_id, "garbage")
	sendUpdate()


def repeatly_sendUpdate():
	'''update forwarding table every 30 seconds'''
	sendUpdate()
	updateTimer = threading.Timer(TIME_INTERVAL[0], repeatly_sendUpdate)
	updateTimer.start()


def repeatly_print_table():
	'''print the forwarding table every 30 seconds'''
	print_FORWARDING_TABLE()
	updateTimer = threading.Timer(TIME_INTERVAL[0],repeatly_print_table)
	updateTimer.start()



def receiveLoop():
	''' a loop continue listening on input sockets, if receive any data , paser it and update the forwarding table'''
	while True:
		# print(FORWARDING_TABLE)

		readable, writeable, exceptional = select.select(INPUT_SOCKET_LIST, [], [])
		for sock in readable:
			try:
				data = sock.recv(BUFFSIZE)
				if data:
					sender, result = parseRIPMessage(data)
					update_FORWARDING_TABLE(sender, result)
					
				else:
					sys.exit()
			except ConnectionResetError:
				pass


if __name__ == '__main__':

	print('please input the configuration filename')
	filename = input()

	try:
		parser(filename)
	except:
		print("can not open this file")

	
	parser_FORWARDING_TABLE()
	create_socket()
	sendUpdate(0)
	repeatly_sendUpdate()
	repeatly_print_table()
	receiveLoop()
	
	





	
	
