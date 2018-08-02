"""
COSC 364 Assignment - RIP Routing
By: Kai & Eleasa 
Date: 4 April 2018
"""

import select, sys, time, random, threading
from random import randint
from socket import *

ABORT_MSG = "Critical Error Message - {}! Please check config file and try again. . ."
ERROR_TYPE = ['not INT', 'port out of range', 
              'duplicate ports', 'duplicate IDs', 'ID out of range']
LOCALHOST = "127.0.0.1"
INPUT_PORTS, NEIGHBOUR_ID = [], []
OUTPUT_PORTS, TABLE, SIDE_TABLE = {}, {}, {}
INF, ROUTER_ID = 16, -1


UpdateT = 0.1 #periodic time for sending updates(routing tables) to neighbours
TimeoutT = UpdateT * 6
GarbT = UpdateT * 4

"""
Helper functions - Start
"""

def parse_config(file):
    """Reads config file and stores data in a dict, 
       and type of data in a list.
    """
    
    keyIter, tempTable = [], {}
    data = open(file,'r').readlines()
    
    if len(data) != 3: #if config file does not have exactly 3 parameters
        print(ABORT_MSG.format('missing/additional parameters'))
        return False
    
    for stuff in data:
        info = stuff.strip().split(' ')
        numbers = info.pop(0)
        keyIter.append(numbers)
        tempTable[numbers] = info
        
    return (keyIter, tempTable)

def check_router_id(tempTable, keyIter):
    """Checks and returns router ID if valid and in range."""
    
    if len(tempTable[keyIter[0]]) > 1:
        print(ABORT_MSG.format(ERROR_TYPE[0]))
        return False     
    for num in tempTable[keyIter[0]]:
        if valid_num(num) == False:
            print(ABORT_MSG.format(ERROR_TYPE[0]))
            return False
        num = int(num)
        if id_in_range(num) == False:
            print(ABORT_MSG.format(ERROR_TYPE[4]))
            return False            
        routerID = num
    return routerID

def check_input_ports(tempTable, keyIter):
    """Checks and returns input ports if valid and in range."""
    
    inputPorts = []
    for stuff in tempTable[keyIter[1]]:
        if ',' in stuff:
            stuff = stuff[:-1]
        if valid_num(stuff) == False:
            print(ABORT_MSG.format(ERROR_TYPE[0]))
            return False
        else:
            stuff = int(stuff)
            if port_in_bound(stuff) == False:
                print(ABORT_MSG.format(ERROR_TYPE[1]))
                return False
            inputPorts.append(stuff)
    if len(inputPorts) != len(set(inputPorts)):
        print(ABORT_MSG.format(ERROR_TYPE[2]))
        return False
    return inputPorts
    
def check_outputs(tempTable, keyIter, routerID):
    """Checks and returns output ports if valid and in range."""    
    
    checkDupeId, checkDupePorts, outputs, table = [],[], {}, {}
    
    for stuff in tempTable[keyIter[2]]:
        temp = []
        if ',' in stuff:
            stuff = stuff[:-1]
        tempList = stuff.split('-')
        for num in tempList:
            if valid_num(num) == False:
                print(ABORT_MSG.format(ERROR_TYPE[0]))
                return  False
            if port_in_bound(int(tempList[0])) == False:
                print(ABORT_MSG.format(ERROR_TYPE[1]))
                return False
        outPort, cost, neighbor = int(tempList[0]), tempList[1], int(tempList[2])
        checkDupeId.append(neighbor)
        checkDupePorts.append(outPort)
        
        outputs[outPort] = neighbor
        
        flag = '-' #- for unconnected route
        timers = [0, 0] #drop timer and garbage collection timer
        table[neighbor] = [neighbor, cost, flag, timers]
        
    if len(checkDupeId) != len(set(checkDupeId)) or routerID in checkDupeId: #check for duplicate IDs
        print(ABORT_MSG.format(ERROR_TYPE[3]))
        return False
    if len(checkDupePorts) != len(set(checkDupePorts)): #check for duplicate ports
        print(ABORT_MSG.format(ERROR_TYPE[2]))
        return False    
    
    return (checkDupeId, checkDupePorts, outputs,table)

def check_dupe_ports(inPort, outPort):
    """Check for duplicates between input and output ports."""
    
    for port in inPort:
        if port in outPort:
            return False
    for port in outPort:
        if port in inPort:
            return False
    return True
    
def form_table(table, routerID):
    """Form initial routing table."""
    routerIds = sorted(table.keys())
    tableString = "+ ROUTER {} +\n| DEST || NEXT || COST || FLAG || Drop T/O || GRBG T/O |\n".format(routerID)
    
    for key, details in sorted(table.items()):
        
        tableString += """| {:>4} || {:>4} || {:>4} || {:>4} || {:>8.4f} || {:>8.4f} |\n""".format(key, details[0], details[1], details[2], details[3][0], details[3][1])
    return tableString
  
def valid_num(data):
    """Check if number is valid INT."""
    try:
        routerID = int(data)
    except ValueError:
        return False
    else:
        return True

def id_in_range(data):
    """Check if ID is within 1 and 64000."""
    if 1 <= data <= 64000:
        return True
    else:
        return False

def port_in_bound(data):
    """Check if port is within 1024 and 64000."""
    if 1024 <= data <= 64000:
        return True
    else:
        return False
    
"""
Helper functions - End
"""


"""
Main functions
"""

def process_config(file):
    """Reads configuation file and extract information
       to inform daemons about links. The internal routing 
       table is still empty at this stage.
    """
    keyIter, tempTable = parse_config(file)
    
    routerID = check_router_id(tempTable, keyIter)
    if routerID == False:
        return False
    inPorts = check_input_ports(tempTable, keyIter)
    if inPorts == False:
        return False
    temp = check_outputs(tempTable, keyIter, routerID)
    if temp == False:
        return False
    nextIds, outPorts, outports_id, table = temp
    checkPorts = check_dupe_ports(inPorts, outPorts)
    if checkPorts == False:
        print(ABORT_MSG.format(ERROR_TYPE[2]))
        return False
    
    """Deep copy of neighbours into an array"""
    neighbourID = []
    for key in table.keys():
        neighbourID.append(key)
        
    return (routerID, neighbourID, inPorts, outports_id, table)

def create_sockets(inPorts):
    """Creates UDP sockets according to number of input ports
       and binds one socket to each input port. Returns list of sockets
    """
    
    listenSocks = []
    for port in inPorts:
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sock.bind(('', port))
        listenSocks.append(sock)
    return listenSocks

"""
def print_message(msg):
    packet = msg.split(';')
    
    head = packet[0]
    body = packet[1:]
    
    print("SENDING PACKET CONTENTS")
    print("="*15)
    #Print Head 
    head_data = head.split(',')
    print("command = {0} , version = {1}, router id = {2}". format(head_data[0], head_data[1], head_data[2]))
    
    #Print Body
    for entry in body:
        entry_data = entry.split(',')
        print("next hop ID = {0}, metric = {1}".format(entry_data[0], entry_data[1]))  
"""

def create_message(routing_Tb, routerId, neighborId):
    """Create the message to send"""
    
    head = '2,2,' + str(routerId)  #version = 2, command = 2, routerid = id of router
    body = '' #Store the destination and metric 
    
    for key, value in routing_Tb.items():    
        
        metric = 0
        body += ';' + str(key) + ','
        
        if (TABLE[key][2] == '-'): #If neighbour is not up do not include metric of neighbour as infinity
            metric = 16
        elif (key == neighborId) : #If next-hop is neighbour send infinity metric (each neighbour knows direct-cost anyways)
            metric = 16 #Split horizon with Poisoned reverse (send inifinity metric to next-hop)
        else:
            metric = value[1]
            
        flag = value[2]
        body += str(metric) + ',' + flag
        
    message = head + body
    return message

def send_message(table=TABLE):
    """Send message to outports"""
    global TABLE
    table = TABLE
    sock = socket(AF_INET, SOCK_DGRAM)
    for port in OUTPUT_PORTS:
        
        neighborId = OUTPUT_PORTS[port] #Get the id of neighbour router
        msg = create_message(table, ROUTER_ID, neighborId)
        msg = msg.encode('utf-8')
        try:
            sock.sendto(msg, ('', port))
        except:
            pass

def unpack_msg(message):
    """ Extract id of destination router, 
    id of neighbour (sender) , and the cost between them"""
    
    raw_data = message.replace("b","").replace("'","")
    data = raw_data.split(';')
    head = data[0] #Get head of packet
    head_data = head.split(',')
    senderID = head_data[-1]
    
    dest = {} #Destination with cost
    
    if len(data) > 1: #Check if there is body after header
        body = data[1:]
        for entry in body:
            destID, metric, flag = entry.split(',')      
            if metric != '':
                dest[int(destID)] = [int(metric), flag] 
      
    return int(senderID), dest

def receive_message(socket_list):
    """ Receives RIP packet from neighbours. Gets the routing table of 
    neighbours to find new path or update to a better path to unidentified 
    destinations (destination which is not a neighbour)."""
    
    global TABLE, TIMEOUT_TIMER
    
    rlist, wlist, elist = select.select(socket_list, [], [], UpdateT) # Time out after x seconds (where x = update time) 
    

    for sock in rlist: #Loop through input sockets and print routing table
    
        data, addr = sock.recvfrom(1024)
        sender, dests = unpack_msg(str(data))
       
        """
        Add to routing table the dest w/ metric = cost this router's neighbour 
        knows to an unidentifed destination + cost this routers know to its neighbour 
    
        """
        
        if TABLE[sender][2] == '-': #If receiving a packet from a previously dead neighbour 
            ct = int(TABLE[sender][1])    
            TABLE[sender] = [sender, ct, 'UT', [0,0]]   #Set flag to 'U' to indicate route is up, set drop timeout since route is established. Use 30 as 30 / 5(periodic timer) = 6
            send_message()
            tablestr = form_table(TABLE, ROUTER_ID) 
            print(tablestr) #Print out the routing table
            continue
        else:
            TABLE[sender][3] = [0,0]
    
        for dest, val in dests.items():
            cost = val[0]
            flag_ = val[1]
         
            #print("dest = {0}, cost = {1} ,flag = {2}".format(dest,cost,flag_))
            if (dest == ROUTER_ID): #If path is for this router ignore as router's own metric is 0
                continue 
            
            if (dest in NEIGHBOUR_ID):
                continue
            
            
            
            """Perform Validation Tests HERE"""
            if not validate_(cost): #If metric not validated ignore
                continue
            
            """Update Metric HERE"""
            network_cost = TABLE[sender][1] #Cost from this router to its neighbour (sender)
            metric = min(cost + network_cost, 16)
            
           
            if (metric == 16):
                continue
              
            
            
            """Check for existing route to destination"""               
            #If dest is not in the routing table
            if dest not in TABLE.keys():
                # FORMAT: NEXT || COST || FLAG || DROP T/O || GRBG T/O
                TABLE[dest] = [sender, metric, 'UGT' , [0, 0]]
                send_message()
                tablestr = form_table(TABLE, ROUTER_ID) 
                print(tablestr) #Print out the routing table
                continue #Continue
            
            #If dest is in the routing table update metric whenever there is a shorter metric
            cur_cost = int(TABLE[dest][1]) #current cost from this router to another router
            flag = TABLE[dest][2]
            
            if metric < cur_cost: #Found shorter path
                flag = TABLE[dest][2] #Flag is not changed 
                TABLE[dest] = [sender, metric, flag, [0, 0]] #Reset timers
                send_message() #Send an update to neighbours to inform of latest metric. (Trigger update)
                tablestr = form_table(TABLE, ROUTER_ID) 
                print(tablestr) #Print out routing table route changes
            else:
                TABLE[dest][3] = [0,0] # Reset timers
            
def rand_updatetime():
    """Generate uniform random distribution of period ut""" 
    return random.uniform(UpdateT*0.8, UpdateT *1.2)

def validate_(metric):
    if (metric >= 1 and metric <= 16): #If metric between 1 and 16 inclusive
        return True
    return False

def update_timers(time):
    ''' Adds time onto all routing table entry timers.'''
    

    #print("UPDATING TIMERS")
    for key in sorted(TABLE.keys()):
        #print("incrementing timer")
        
        if TABLE[key][2] == '-':
            continue
        
        if (TABLE[key][2] == 'C'):
            TABLE[key][-1][1] += time
            tablestr = form_table(TABLE, ROUTER_ID) 
            print(tablestr) #Print out routing table route changes                       
            if TABLE[key][3][1] > GarbT:
                
                if key in NEIGHBOUR_ID:
                    TABLE[key][2] = '-'
                    TABLE[key][3][1] = 0
                    send_message()
                else:
                    del TABLE[key]
                # remove entry from dictionary
                tablestr = form_table(TABLE, ROUTER_ID) 
                print(tablestr) #Print out routing table route changes 
        else:
            TABLE[key][3][0] += time
            tablestr = form_table(TABLE, ROUTER_ID) 
            print(tablestr) #Print out routing table route changes                       
         
            if TABLE[key][3][0] > TimeoutT:
                print("set metric to 16")
                original_metric = TABLE[key][1]
                
                TABLE[key][1] = 16 # Set route to timed out router to infinity
                TABLE[key][2] = 'C'
                TABLE[key][3][0] = 0
                
                send_message()
                
                if key in NEIGHBOUR_ID:
                    TABLE[key][1] = original_metric #Set to original metric
                
                
                tablestr = form_table(TABLE, ROUTER_ID) 
                print(tablestr) #Print out routing table route changes             
       
                       
def respond_2events(socket_list):
    """Responding to events i.e. 1) send own routing table every x seconds and 
    2) receive routing table of a neighbour whenever there is an update"""
    
    global TABLE
    
    update_time = rand_updatetime() # random time
    startpt = time.time() # Start update timer

    while 1: #Start responding to eventss
        
        track = time.time()
        elp = time.time() - startpt #elapsed time for periodic update time
        if elp >= update_time: #if elapsed time is >= periodic update time 
            startpt = time.time() # Reset update timer
            update_time = rand_updatetime() # set new random time
            send_message() #Send message to outports around every x seconds
        else:
            receive_message(socket_list) #Receive message anytime    
            timer_incr = time.time() - track # Get timer increment
            update_timers(timer_incr)
            
def main():
    
    """3 main functionality: 
    1) Processing config file, 
    2) Creating/binding sockets to input ports, 
    3) and responding to events (sending and receiving messages)"""
    
    fname = sys.argv[1] #Get filename from console 
    routerID, neighbourID, inPorts, outPorts, table = process_config(fname)
    
    global TABLE, ROUTER_ID, NEIGHBOUR_ID, OUTPUT_PORTS
    TABLE, ROUTER_ID, NEIGHBOUR_ID, OUTPUT_PORTS = table, routerID, neighbourID, outPorts
    
    listenSocks = create_sockets(inPorts)
    tablestr = form_table(TABLE, ROUTER_ID) 
    print(tablestr)
    respond_2events(listenSocks) #Responding to events

main()
