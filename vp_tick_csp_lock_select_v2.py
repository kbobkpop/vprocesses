
import multiprocessing.connection
import time
import multiprocessing
import select
import graphviz
import random

#TODO - Clean up state lists and make naming more consistent
# - add image filename and dir as arguments
class VManager():
    def __init__(self, processes, connections, locks=[], selects=[]) -> None:
        self.processes = processes # List of VProcess passed as to the class constructor as argument
        self.connections = connections # List of VConnection classes passed to the class constructor as argument
        self.requests_from_worker_connections = [] # !!! List of connections populated by __init__ and used to receive requests from workers - Not used it seems 
        self.signal_to_worker_connections = [] # List of connections populated by __init__ - can be used to send messages to worker processes - Not used it seems
        self.recv_send_dict = {} # Dictionary of connections used by processes, where they key is the connection intended for the manager to receive messages from sync-objects and the value is connection used to send to sync-objects. Populated in __init__
        self.vconn_send_to_recv_dict = {} # Dictionary of VConnections used between worker processes, where they key is the VConnection one worker sends from and the value is the VConnection another worker receives from. Populated in __init__ - Not used it seems
        self.vconn_recv_to_send_dict = {} # Dictionary of VConnections used between worker processes, where they key is the VConnection one worker receives from and the value is the VConnection another worker sends to. Populated in __init__ - Not used it seems
        self.from_to_lock_connection_dict = {} # Dictionary of connections used by locks, where they key is the connection intended for the manager to receive messages from sync-objects and the value is connection used to send to sync-objects. Populated in __init__
        self.from_to_select_connection_dict = {} # Dictionary of connections used by selects, where they key is the connection intended for the manager to receive messages from sync-objects and the value is connection used to send to sync-objects. Populated in __init__
        self.tickCounter = 0 # Counter used for the number on the image file and showing which tick is run
        self.processNodes = [] # List of process nodes for the graph used for drawing the image
        self.lockNodes = [] # List of lock nodes for the graph used for drawing the image
        self.selectNodes = [] # List of select nodes for the graph used for drawing the image
        self.edges = [] # List of edges between processes for the graph used for drawing the image
        self.lockEdges = [] # List of edges between processes and locks for the graph used for drawing the image
        self.uncompletedSends = [] # List of send graph edges that are uncompleted updated by getRequests and used in handleRequests to update the graph and handle messaging
        self.uncompletedRecvs = [] # List of recv graph edges that are uncompleted updated by getRequests and used in handleRequests to update the graph and handle messaging
        self.waiting_to_send_connection = [] # List of processes waiting to send 
        self.waiting_to_receive_connection = [] # List of processes waiting to receive
        self.waitingToAcquire = [] # List of processes waiting to acquire a lock
        self.waitingToRelease = [] # List of processes waiting to release a lock
        self.waitingToSelect = [] # List of processes waiting to select
        self.lockedLocks = [] # List of locks that are currently locked
        self.vconnPairs = [] # List of VConn pairs of in and out - Not currently used
        self.prematureSelectSends = [] # List of sending processes that have been allowed to send because of an intervening select statment. However the processes are still not considered able, until the receiving side is ready. 
        self.locks = locks # List of VLock objects
        self.selects = selects # List of VSelect objects

        for process in self.processes:
            process.report_channels() #returns the process' connections
            self.processNodes.append([process.name, "black"])
            process.report_locks()

        for connection1 in connections:
            if connection1.name[-2:] == 'in': 
                name = connection1.name[:-2] + str('out')
                for connection2 in connections:
                    if name == connection2.name:
                        self.vconnPairs.append((connection1, connection2))
                        self.vconn_send_to_recv_dict[connection1.name] = connection2
                        self.vconn_recv_to_send_dict[connection2.name] = connection1
        
        locknamenum = 1
        for lock in locks:
            if type(lock.name) == int:
                tempname = lock.name
                for name in locks:
                    if name.name == tempname:
                        name.name = "lock" + str(locknamenum)
                locknamenum += 1
        
        for lock in locks:
            if not lock.name in self.lockNodes:
                self.lockNodes.append(lock.name)

        self.connection_process_lookup = {}

        for connection in self.connections: #4 x connections
            connected_process = None
            for process in self.processes: #2 x processes
                if connection in process.report_channels(): #"in" checks all elements for equality in list.
                    connected_process = process
            if connected_process != None: #if connected_process was assigned
                #Maps the given PatchConnection's name to a connected process
                self.connection_process_lookup[connection.name] = connected_process #adding key=connection.name, value=connected_process

        self.lock_process_lookup = {}

    def start(self):
        for connection in self.connections:
            recv, send = connection.setup_manager_connection()
            self.recv_send_dict[recv] = send # Dictionary mapping receive to send connections
            self.requests_from_worker_connections.append(recv)
            self.signal_to_worker_connections.append(send) #Do I need this?

        for lock in self.locks:
            lock.setup_manager_connection()

        for select in self.selects:
            select.setup_manager_connection()

        for process in self.processes:
            for connection in process.connections: #vconnections
                process.from_worker_connections.append(connection.recv_from_worker)
                process.to_worker_connections.append(connection.send_to_worker)
            for lock in process.locks:
                process.from_lock_connections.append(lock.recv_from_worker)
                process.to_lock_connections.append(lock.send_to_worker)
                self.from_to_lock_connection_dict[lock.recv_from_worker] = lock.send_to_worker
            for select in process.selects:
                process.from_select_connections.append(select.recv_from_worker)
                process.to_select_connections.append(select.send_to_worker)
                self.from_to_select_connection_dict[select.recv_from_worker] = select.send_to_worker

        for p in self.processes:
            p.start()
    
    def run_all_to_tick(self, processes):
        print(f"Tick {self.tickCounter} started")
        self.tickCounter += 1

        recvs, sends = self.getRequests(processes)

        self.uncompletedRecvs.extend(recvs)
        self.uncompletedSends.extend(sends)
        
        updateLockList = self.releaseLocks()

        updateLockList = self.acquireLocks(updateLockList)

        updateLockList, updateNodesList, updateEdgesList = self.handleRequests(updateLockList)

        self.updateGraph(updateLockList, updateNodesList, updateEdgesList)

        ableProcesses = self.getAbleProcesses()
    
        #print(f"self.waiting_to_send_connection: {self.waiting_to_send_connection}")
        #print(f"self.waiting_to_recv_connection: {self.waiting_to_receive_connection}")
        #print(f"self.uncompletedSends: {self.uncompletedSends}")
        #print(f"self.uncompletedRecvs: {self.uncompletedRecvs}")
        #print(f"self.prematureSelectSends: {self.prematureSelectSends}")
        #print(f"self.waitingToSelect: {self.waitingToSelect}")
        #print(f"self.waitingToAcquire {self.waitingToAcquire}")
        #print(f"self.waitingToRelease {self.waitingToRelease}")
        #print(f"self.lockedLocks {self.lockedLocks}")
        #print(f"ableProcesses: {ableProcesses}")
        
        return ableProcesses
    
    def getRequests(self, processes):
        sendEdges = []
        recvEdges = []

        woke = [False for _ in processes]

        while False in woke:
            for index, process in enumerate(processes):
                selectlist = process.from_worker_connections[:]
                selectlist.extend(process.from_lock_connections)
                selectlist.extend(process.from_select_connections)
                (inputs, _, _) = select.select(selectlist, [], [])
                for conn in selectlist:
                    if conn in inputs:
                        action, process1Name, data = conn.recv()
                        woke[index] = True
                        if action == "acquire":
                            lockName = data
                            self.waitingToAcquire.append([lockName, process1Name, self.from_to_lock_connection_dict[conn]])
                            #print(f"{process1Name} is trying to acquire")
                        elif action == "release":
                            lockName = data
                            self.waitingToRelease.append([lockName, process1Name, self.from_to_lock_connection_dict[conn]])
                            #print(f"{process1Name} is trying to release")
                        elif action == "select":
                            selectName, selectlist = data #Not sure if this is necessary
                            self.waitingToSelect.append([selectName, process1Name, self.from_to_select_connection_dict[conn], selectlist])
                            #print("SELECT REQEUST RECEIVED - self.waitingToSelect:", self.waitingToSelect)
                        else:
                            otherEndsVConnName, transfer = data
                            for connection in self.connections:
                                if otherEndsVConnName == connection.name:
                                    process2Name = self.connection_process_lookup[connection.name].name
                            if action == "recv":
                                self.waiting_to_receive_connection.append((process1Name, self.recv_send_dict[conn], otherEndsVConnName))
                                recvEdges.append([process2Name, process1Name, transfer])
                            elif action == "send":
                                self.waiting_to_send_connection.append((process1Name, self.recv_send_dict[conn], otherEndsVConnName))
                                sendEdges.append([process1Name, process2Name, transfer])
        return recvEdges, sendEdges

    #Handle updating graph after being in select state by checking next receive request from same process: Maybe only then remove from some list keeping it's state. 

    def handleRequests(self, updateLocksList):
        updateEdgesList = []
        updateNodesList = []
        for currentLockEdge in self.lockEdges:
            for newedge in self.waitingToAcquire:
                if currentLockEdge[0] == newedge[0] and currentLockEdge[1] == newedge[1]:
                    updateLocksList.append([newedge[0], currentLockEdge[1], ' ', 'purple', 'dashed'])
        
        for select in self.waitingToSelect:
            updateNodesList.append([select[1], 'red', 'dashed'])
        
        
        tmpSelectList = self.waitingToSelect[:]
        tmpSendList = self.waiting_to_send_connection[:]
        for pslct in tmpSelectList: 
            remove = False
            selectlist = pslct[3] 
            for conn in selectlist: 
                for wts in tmpSendList:
                    if conn.name == wts[2]:                     
                        wts[1].send(True)
                        remove = True
                        #print(f"macthed wts[0] = {wts[0]} => {pslct[1]} = pslct[1]")
                        self.prematureSelectSends.append(wts)

            if remove == True:
                pslct[2].send(True)
                self.waitingToSelect.remove(pslct)

        for conn in self.waiting_to_receive_connection:
            for node in self.selectNodes:
                if conn[0] == node[0]:
                    updateNodesList.append([node[0], 'black', 'solid'])

        #Check send:
        for currentedge in self.edges:
            for newedge in self.uncompletedSends:
                if currentedge[0] == newedge[0] and currentedge[1] == newedge[1]:
                    if currentedge[2] == ' ':
                        updateEdgesList.append(newedge)
        
        # Check recv:
        # for each edge in edges, compare if the same edge is in uncompletedRecvs:
        # If that is the case, check if that edge is currently transfering data add that uncompletedRecvs to the updatelist with empty " " and send messages to the two connections so that they can continue  
        for currentedge in self.edges:
            for newedge in self.uncompletedRecvs: #The premature send is in the uncompleted receive
                if currentedge[0] == newedge[0] and currentedge[1] == newedge[1]: #For each edge in the graph check if there is a corresponding uncompletedRecv
                    if currentedge[2] != ' ': #Since this is true, there must be a connection sending on that connection - I am not sure if I like this solution.
                        p1name = None
                        p2name = None
                        #We are now adding the edge to be updated below for the visual graph and completing the logical sending and receiving, by sending a message to the two connections
                        updateEdgesList.append(newedge)
                        removelist = []
                        for conn in self.waiting_to_send_connection:
                            p1name, c, _ = conn
                            if p1name == newedge[0]:
                                c.send(True)
                                removelist.append(conn)
                        self.waiting_to_send_connection[:] = [conn for conn in self.waiting_to_send_connection if conn not in removelist]
                        removelist = []
                        for conn in self.prematureSelectSends:
                            p1name, c, _ = conn
                            if p1name == newedge[0]:
                                removelist.append(conn)
                        self.prematureSelectSends = [conn for conn in self.prematureSelectSends if conn not in removelist]
                        removeConns = []
                        removeSends = []
                        removePrematureSends = []
                        removeRecvs = []
                        for conn in self.waiting_to_receive_connection: #Could there be a problem if a process was waiting on two connections? I don't think so, a process should never be waiting on two connections.
                            p2name, c, _ = conn
                            if p2name == newedge[1]: #Why does this hold? It holds because there is something on the current channel, seen in "if currentedge[2] != ' ':"
                                c.send(True)
                                removeConns.append(conn)
                                removeRecvs.append(newedge)
                                for edge in self.uncompletedSends:
                                    if edge[0] == newedge[0] and edge[1] == newedge[1]:
                                        removeSends.append(edge)

                        self.waiting_to_receive_connection[:] = [conn for conn in self.waiting_to_receive_connection if conn not in removeConns]
                        self.uncompletedSends[:] = [conn for conn in self.uncompletedSends if conn not in removeSends]
                        self.uncompletedRecvs[:] = [conn for conn in self.uncompletedRecvs if conn not in removeRecvs]
                        self.prematureSelectSends[:] = [conn for conn in self.prematureSelectSends if conn not in removePrematureSends]

        
        return updateLocksList, updateNodesList, updateEdgesList
    
    def acquireLocks(self, updateLockList):
        processesWaitingToAcquire = self.waitingToAcquire[:]
        
        templocks = self.lockNodes[:]

        for lock in templocks:
            templist = []
            for pwta2 in processesWaitingToAcquire:
                if lock == pwta2[0]:
                    templist.append(pwta2)
            if len(templist) > 0: 
                if templist[0][0] not in self.lockedLocks: # Only if lock is not already acquired
                    randIndex = random.randint(0, len(templist) - 1)
                    templist[randIndex][2].send(True)
                    updateLockList.append([templist[randIndex][0], templist[randIndex][1], ' ', 'blue', 'solid'])
                    self.lockedLocks.append(templist[randIndex][0])
                    self.waitingToAcquire.remove(templist[randIndex])

        return updateLockList

    def releaseLocks(self):
        updateLockList = []
        removelist = []
        for wtr in self.waitingToRelease:
            wtr[2].send(True)
            updateLockList.append([wtr[0], wtr[1], ' ', 'black', 'dashed']) # Updates the graph when waiting to release
            self.lockedLocks.remove(wtr[0])
            removelist.append(wtr)

        for r in removelist:
            self.waitingToRelease.remove(r)

        return updateLockList

    def getAbleProcesses(self):
        ableProcesses = self.processes[:]
        for process in self.processes:
            for p in self.uncompletedSends:
                if process.name == p[0]:
                    ableProcesses.remove(process)
            for p in self.uncompletedRecvs:
                if process.name == p[1]:
                    ableProcesses.remove(process)
            for p in self.waitingToAcquire:
                if process.name == p[1]:
                    ableProcesses.remove(process)
            for p in self.waitingToRelease:
                if process.name == p[1]:
                    ableProcesses.remove(process)
            for p in self.waitingToSelect:
                if process.name == p[1]:
                    ableProcesses.remove(process)
        return ableProcesses

    def updateGraph(self, updateLocksList, updateNodesList, updateEdgesList):
        for node in updateNodesList:
            self.updateSelectNodes(node[0], node[1], node[2])
        for edge in updateLocksList:                
            self.updateLockEdges(edge[0], edge[1], edge[2], edge[3], edge[4])
        for edge in updateEdgesList:                
            self.updateEdges(edge[0], edge[1], edge[2])
        self.drawGraph()


    def init_graph(self):
        for p1 in self.processes:
            for conn1 in p1.connections:
                for p2 in self.processes:
                    for conn2 in p2.connections:
                        if conn1.otherEnd == conn2 and conn1.sender == True:
                            self.edges.append([p1.name, p2.name, " "])
                            #print(f"added edge: ({p1.name}, {p2.name})")
        for lock in self.locks:
            for process in self.processes:
                if lock in process.locks:
                    self.lockEdges.append([lock.name, process.name, " ", "black", "dashed"])
        
        for select in self.selects:
            for process in self.processes:
                if select in process.selects:
                    self.selectNodes.append([process.name, select.name, "black"])

        self.drawGraph()
        print(f"Graph init ended, this is the current state: {self.edges}")

    #extend this with labels and titles, eg. tick number
    #consider range, and general design, could functionality for nodes and selects be merged
    def drawGraph(self):
        dgraph = graphviz.Digraph(format="pdf")
        dgraph.attr(label=f"Tick {self.tickCounter}", labelloc="t")
        for i in range(len(self.processNodes)):
            dgraph.node(self.processNodes[i][0], color=self.processNodes[i][1])
        for i in range(len(self.edges)):
            dgraph.edge(self.edges[i][0], self.edges[i][1], self.edges[i][2])
        for i in range(len(self.lockNodes)):
            dgraph.node(self.lockNodes[i], shape="square")
        for i in range(len(self.lockEdges)):
            #print(f"self.lockEdges[{i}]: {self.lockEdges[i]}")
            dgraph.edge(self.lockEdges[i][0], self.lockEdges[i][1], self.lockEdges[i][2], color=self.lockEdges[i][3], style=self.lockEdges[i][4], dir="none")
        for i in range(len(self.selectNodes)):
            dgraph.node(self.selectNodes[i][0], color=self.selectNodes[i][1], style=self.selectNodes[i][2])
        
        
        filename = 'output/Tick_' + str(self.tickCounter)
        dgraph.render(filename)
        print(filename, "rendered")
        #self.tickCounter += 1

    def updateEdges(self, name1, name2, input):
        for i in range(len(self.edges)):
            if name1 == self.edges[i][0] and name2 == self.edges[i][1]:
                self.edges[i][2] = str(input)

    def updateLockEdges(self, name1, name2, input, color, style):
        for i in range(len(self.lockEdges)):
            if name1 == self.lockEdges[i][0] and name2 == self.lockEdges[i][1]:
                self.lockEdges[i][3] = color
                self.lockEdges[i][4] = style

    def updateSelectNodes(self, node, color, style):
        for i in range(len(self.selectNodes)):
            if node == self.selectNodes[i][0]:
                self.selectNodes[i][1] = color
                self.selectNodes[i][2] = style

# Ths class seems bloated for what it actually uses
class VProcess(multiprocessing.Process):
    def __init__(self, group = None, target = None, name = None, args = [], kwargs = {}, *, daemon = None) -> None:
        super().__init__(group, target, name, args, kwargs, daemon=daemon)
        self.to_worker_connections = []
        self.from_worker_connections = [] 
        self.from_lock_connections = []
        self.to_lock_connections = []
        self.from_select_connections = []
        self.to_select_connections = [] 
        self.connections = [] # Connections received as parameters
        self.locks = []
        self.selects = []

        for arg in args:
            if type(arg) == VConnection:
                self.connections.append(arg)
            if type(arg) == VLock:
                self.locks.append(arg)
            if type(arg) == VSelect:
                self.selects.append(arg)
    
    def report_channels(self): #None of these are used as far as I can tell
        #print(self.connections)
        return self.connections
    
    def report_locks(self):
        #print(self.locks)
        return self.locks
    
    def report_selects(self):
        #print(self.locks)
        return self.selects

    # Maybe this one can be used to run the ticks by accessing the target method through BaseProcess, and control the ticks.
    def run_to_tick():
        pass

class VLock():
    def __init__(self, lock, name=None):
        self.lock = lock
        self.send_to_manager = None 
        self.recv_from_worker = None
        self.send_to_worker = None
        self.recv_from_manager = None
        if name: 
            self.name = name
        else:
            self.name = id(lock) 
        
    def setup_manager_connection(self):
        self.send_to_manager, self.recv_from_worker = multiprocessing.Pipe()
        self.send_to_worker, self.recv_from_manager = multiprocessing.Pipe()
        return self.recv_from_worker, self.send_to_worker
        
    
    def acquire(self):
        self.send_to_manager.send(("acquire", multiprocessing.current_process().name, self.name))
        self.recv_from_manager.recv()
        self.lock.acquire()

    def release(self):
        self.send_to_manager.send(("release", multiprocessing.current_process().name, self.name))
        self.recv_from_manager.recv()
        self.lock.release()


class VSelect():
    def __init__(self, name=None):
        self.send_to_manager = None 
        self.recv_from_worker = None
        self.send_to_worker = None
        self.recv_from_manager = None
        if name: 
            self.name = name
        else:
            self.name = id(self) 
        
    def setup_manager_connection(self):
        self.send_to_manager, self.recv_from_worker = multiprocessing.Pipe()
        self.send_to_worker, self.recv_from_manager = multiprocessing.Pipe()
        return self.recv_from_worker, self.send_to_worker
        
    #For now just sending selectlist1
    def select(self, selectlist1, selectlist2=[], selectlist3=[]):
        #print("REQUESTING TO SELECT")
        self.send_to_manager.send(("select", multiprocessing.current_process().name, (self.name, selectlist1)))
        self.recv_from_manager.recv()
        #print("RECEIVED PERMISSION TO SELECT")
        selectlist1 = [vconn.connection for vconn in selectlist1]
        (inputs1, inputs2, inputs3) = select.select(selectlist1, selectlist2, selectlist3)
        #print(f"SELECT.SELECT returned: {inputs1}")
        return inputs1, inputs2, inputs3

class VConnection():
    def __init__(self, connection, name, otherEndsName, sender=True) -> None:
        self.name = name
        self.otherEndsName = otherEndsName
        self.otherEnd = None
        self.connection = connection
        self.send_to_manager = None
        self.recv_from_worker = None
        self.send_to_worker = None 
        self.recv_from_manager = None 
        self.sender = sender

    def setup_manager_connection(self):
        self.send_to_manager, self.recv_from_worker = multiprocessing.Pipe()
        self.send_to_worker, self.recv_from_manager = multiprocessing.Pipe()
        return self.recv_from_worker, self.send_to_worker

    def send(self, data):
        self.send_to_manager.send(("send", multiprocessing.current_process().name, (self.otherEndsName, data)))
        good_to_go = self.recv_from_manager.recv()
        if good_to_go:
            self.connection.send(data)
    
    def recv(self):
        self.send_to_manager.send(("recv", multiprocessing.current_process().name, (self.otherEndsName, " ")))
        good_to_go = self.recv_from_manager.recv()
        if good_to_go:
            data = self.connection.recv()
            return data

        
def VPipe(name=""):
    end1, end2 = multiprocessing.Pipe()
    if name == "":
        name = id(end1)
    patchConnection1 = VConnection(end1, f"{name}_in", f"{name}_out", sender=True)
    patchConnection2 = VConnection(end2, f"{name}_out", f"{name}_in", sender=False)
    patchConnection1.otherEnd = patchConnection2
    patchConnection2.otherEnd = patchConnection1

    return patchConnection1, patchConnection2

def pingpong(i, input, output, initial_data=""):
    if initial_data:
        output.send(initial_data)
    while True:
        data = input.recv()
        print(f"{i}: {data}")
        output.send(data)

def lockedPingPong(i, lock, input, output, initial_data=""):
    if initial_data:
        lock.acquire()
        output.send(initial_data)
        lock.release()
    while True:
        data = input.recv()
        print(f"{i}: {data}")
        lock.acquire()
        output.send(data)
        lock.release()


def producer(queue):
    for i in range(5):
        queue.send(i)
        queue.send("hello")

def transmitter(conn1, conn2):
    for i in range(5):
        data = conn1.recv()
        conn2.send(data)

def consumer(queue):
    while True:
        data = queue.recv()
        print(f"{data}")


def doubleConsumer(queue1, queue2):
    while True:
        data1 = queue1.recv()
        data2 = queue2.recv()
        data3 = queue1.recv()
        data4 = queue2.recv()

        if data3 == "hello" and data4 == "hello":
            print(f"{data1}-{data2}")

def doubleInTransmitter(conn1, conn2, conn3):
    for i in range(5):
        data1 = conn1.recv()
        data2 = conn2.recv()

        dataout = str(data1) + " + " + str(data2) 

        conn3.send(dataout)

def doubleOutTransmitter(conn1, conn2, conn3):
    for i in range(5):
        data = conn1.recv()
        conn2.send(data)
        conn3.send(data)

def transmitterTest():
    pipe_1_in, pipe_1_out  = VPipe()
    pipe_2_in, pipe_2_out  = VPipe()

    processes = [
        VProcess(
            target=producer, 
            args=(pipe_1_in,),
            name="p1"
        ),
        VProcess(
            target=transmitter, 
            args=(pipe_1_out, pipe_2_in),
            name="t1"
        ),
        VProcess(
            target=consumer, 
            args=(pipe_2_out,),
            name="c1"
        )
    ]

    channels = [
        pipe_1_in,
        pipe_1_out,
        pipe_2_in,
        pipe_2_out,
    ]
    return processes, channels

def doubleInTransmitterTest():
    pipe_1_in, pipe_1_out  = VPipe()
    pipe_2_in, pipe_2_out  = VPipe()
    pipe_3_in, pipe_3_out  = VPipe()

    processes = [
        VProcess(
            target=producer, 
            args=(pipe_1_in,),
            name="p2"
        ),
        VProcess(
            target=producer, 
            args=(pipe_2_in,),
            name="p3"
        ),
        VProcess(
            target=doubleInTransmitter, 
            args=(pipe_1_out, pipe_2_out, pipe_3_in),
            name="t2"
        ),
        VProcess(
            target=consumer, 
            args=(pipe_3_out,),
            name="c2"
        )
    ]

    channels = [
        pipe_1_in,
        pipe_1_out,
        pipe_2_in,
        pipe_2_out,
        pipe_3_in, 
        pipe_3_out
    ]
    return processes, channels

def doubleOutTransmitterTest():
    pipe_1_in, pipe_1_out  = VPipe()
    pipe_2_in, pipe_2_out  = VPipe()
    pipe_3_in, pipe_3_out  = VPipe()

    processes = [
        VProcess(
            target=producer, 
            args=(pipe_1_in,),
            name="p4"
        ),
        VProcess(
            target=doubleOutTransmitter, 
            args=(pipe_1_out, pipe_2_in, pipe_3_in),
            name="t3"
        ),
        VProcess(
            target=consumer, 
            args=(pipe_2_out,),
            name="c3"
        ),
        VProcess(
            target=consumer, 
            args=(pipe_3_out,),
            name="c4"
        )
    ]

    channels = [
        pipe_1_in,
        pipe_1_out,
        pipe_2_in,
        pipe_2_out,
        pipe_3_in, 
        pipe_3_out
    ]
    return processes, channels

def pingPongTest():
    pipe_1_in, pipe_1_out  = VPipe()
    pipe_2_in, pipe_2_out  = VPipe()
    processes = [
        VProcess(
            target=pingpong, 
            args=(0, pipe_1_in, pipe_2_out, "hello"),
            name="Albert"
        ),
        VProcess(
            target=pingpong, 
            args=(1, pipe_2_in, pipe_1_out),
            name="Bertha"
        )
    ]
    channels = [
        pipe_1_in,
        pipe_1_out,
        pipe_2_in,
        pipe_2_out
    ]
    return processes, channels

def producerDoubleConsumerTest():
    q11, q12 = VPipe()
    q21, q22 = VPipe()

    processes = [
        VProcess(
            target=producer, 
            args=(q11, ),
            name="p5"
        ),
        VProcess(
            target=producer, 
            args=(q21,),
            name="p6"
        ),
        VProcess(
            target=doubleConsumer, 
            args=(q12, q22),
            name="c5"
        )
    ]
    channels = [q11, q12, q21, q22]
    return processes, channels

def producerConsumerTest():
    q11, q12 = VPipe()
    q21, q22 = VPipe()


    processes = [
        VProcess(
            target=producer, 
            args=(q11, ),
            name="p7"
        ),
        VProcess(
            target=producer, 
            args=(q21,),
            name="p8"
        ),
        VProcess(
            target=consumer, 
            args=(q12,),
            name="c7"
        ),
        VProcess(
            target=consumer, 
            args=(q22,),
            name="c8"
        )
    ]
    channels = [q11, q12, q21, q22]
    return processes, channels

def lockedProducer(conn, lock):
    for i in range(5):
        lock.acquire()
        #print(multiprocessing.current_process(), "acquired lock, and is trying to send", i)
        conn.send(i)
        lock.release()

def DavidsSquid(conn1, conn2, conn3, conn4, lock1, lock2, vs):
    while True:
        data1 = None
        data2 = None
        #print("DAVIDS SQUID, START OF WHILE")
        (inputs, _, _) = vs.select([conn1, conn2], [], [])
        #print("inputs: ", inputs)
        if conn1.connection in inputs and conn2.connection in inputs:
            num = random.randint(0, 1)
            #print("num:", num)
            if num == 0:
                #print(f"num 0, conn1 before recv")
                data1 = conn1.recv()
                #print(f"Davids Squid, conn1: {data1}")
            else:
                #print(f"not num 0, conn2 before recv")
                data2 = conn2.recv()
                #print(f"Davids Squid, conn2: {data2}")
        elif conn1.connection in inputs:
            #print(f"Davids Squid, conn1 before recv")
            data1 = conn1.recv()
            #print(f"Davids Squid, conn1: {data1}")
        elif conn2.connection in inputs:
            #print(f"Davids Squid, conn2 before recv")
            data2 = conn2.recv()
            #print(f"Davids Squid, conn2: {data2}")
        
        #num = random.randint(0, 1)
        
        if data1 != None:
            lock1.acquire()
            conn3.send(data1)
            lock1.release()
        elif data2 != None:
            lock2.acquire()
            conn4.send(data2)
            lock2.release()

def oneLockLockedProducerConsumerTest():

    lock = multiprocessing.Lock()

    vlock1 = VLock(lock)
    vlock2 = VLock(lock)
    vlock3 = VLock(lock)
    vlock4 = VLock(lock)

    p1, c1 = VPipe()
    p2, c2 = VPipe()
    p3, c3 = VPipe()
    p4, c4 = VPipe()

    processes = [
            VProcess(
                target=lockedProducer, 
                args=(p1, vlock1),
                name="p1"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p2, vlock2),
                name="p2"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p3, vlock3),
                name="p3"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p4, vlock4),
                name="p4"
            ),
            VProcess(
                target=consumer, 
                args=(c1,),
                name="c1"
            ),
            VProcess(
                target=consumer, 
                args=(c2,),
                name="c2"
            ),
            VProcess(
                target=consumer, 
                args=(c3,),
                name="c3"
            ),
            VProcess(
                target=consumer, 
                args=(c4,),
                name="c4"
            )
    ]

    channels = [p1, c1, p2, c2, p3, c3, p4, c4]
    locks = [vlock1, vlock2, vlock3, vlock4]

    return processes, channels, locks

def twoLockLockedProducerConsumerTest():

    lock1 = multiprocessing.Lock()
    lock2 = multiprocessing.Lock()
    #lock3 = multiprocessing.Lock()

    vlock1 = VLock(lock1)
    vlock2 = VLock(lock1)
    vlock3 = VLock(lock1)
    vlock4 = VLock(lock2)
    vlock5 = VLock(lock2)
    vlock6 = VLock(lock2)

    p1, c1 = VPipe()
    p2, c2 = VPipe()
    p3, c3 = VPipe()
    p4, c4 = VPipe()
    p5, c5 = VPipe()
    p6, c6 = VPipe()

    processes = [
            VProcess(
                target=lockedProducer, 
                args=(p1, vlock1),
                name="p1"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p2, vlock2),
                name="p2"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p3, vlock3),
                name="p3"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p4, vlock4),
                name="p4"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p5, vlock5),
                name="p5"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p6, vlock6),
                name="p6"
            ),
            VProcess(
                target=consumer, 
                args=(c1,),
                name="c1"
            ),
            VProcess(
                target=consumer, 
                args=(c2,),
                name="c2"
            ),
            VProcess(
                target=consumer, 
                args=(c3,),
                name="c3"
            ),
            VProcess(
                target=consumer, 
                args=(c4,),
                name="c4"
            ),
            VProcess(
                target=consumer, 
                args=(c5,),
                name="c5"
            ),
            VProcess(
                target=consumer, 
                args=(c6,),
                name="c6"
            )
    ]

    channels = [p1, c1, p2, c2, p3, c3, p4, c4, p5, c5, p6, c6]
    locks = [vlock1, vlock2, vlock3, vlock4, vlock5, vlock6]

    return processes, channels, locks

def lockedPingPongTest():
    lock = multiprocessing.Lock()
    
    vlock1 = VLock(lock)
    vlock2 = VLock(lock)
    
    pipe_1_in, pipe_1_out  = VPipe()
    pipe_2_in, pipe_2_out  = VPipe()
    
    
    processes = [
        VProcess(
            target=lockedPingPong, 
            args=(0, vlock1, pipe_1_in, pipe_2_out, "hello"),
            name="Albert"
        ),
        VProcess(
            target=lockedPingPong, 
            args=(1, vlock2, pipe_2_in, pipe_1_out),
            name="Bertha"
        )
    ]

    locks = [vlock1, vlock2]

    channels = [
        pipe_1_in,
        pipe_1_out,
        pipe_2_in,
        pipe_2_out
    ]
    return processes, channels, locks

def lockedMultiplePingPongTest():
    lock = multiprocessing.Lock()
    
    vlock1 = VLock(lock)
    vlock2 = VLock(lock)
    vlock3 = VLock(lock)
    vlock4 = VLock(lock)
    

    pipe_1_in, pipe_1_out  = VPipe()
    pipe_2_in, pipe_2_out  = VPipe()
    pipe_3_in, pipe_3_out  = VPipe()
    pipe_4_in, pipe_4_out  = VPipe()
    
    processes = [
        VProcess(
            target=lockedPingPong, 
            args=(0, vlock1, pipe_1_in, pipe_2_out, "hello"),
            name="Albert"
        ),
        VProcess(
            target=lockedPingPong, 
            args=(1, vlock2, pipe_2_in, pipe_1_out),
            name="Bertha"
        ),
        VProcess(
            target=lockedPingPong, 
            args=(0, vlock3, pipe_3_in, pipe_4_out, "hello"),
            name="Cindy"
        ),
        VProcess(
            target=lockedPingPong, 
            args=(1, vlock4, pipe_4_in, pipe_3_out),
            name="Dennis"
        ),
    ]

    locks = [vlock1, vlock2, vlock3, vlock4]

    channels = [
        pipe_1_in,
        pipe_1_out,
        pipe_2_in,
        pipe_2_out,
        pipe_3_in,
        pipe_3_out,
        pipe_4_in,
        pipe_4_out
    ]
    return processes, channels, locks

def DavidsSquidTest():
    
    vs = VSelect(name="vselector")

    lock1 = multiprocessing.Lock()
    lock2 = multiprocessing.Lock()

    vlock1 = VLock(lock1)
    vlock2 = VLock(lock2)
    vlock3 = VLock(lock1)
    vlock4 = VLock(lock2)


    p1, c1 = VPipe()
    p2, c2 = VPipe()
    p3, c3 = VPipe()
    p4, c4 = VPipe()

    processes = [
            VProcess(
                target=lockedProducer, 
                args=(p1,vlock1),
                name="p1"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p2,vlock2),
                name="p2"
            ),
            VProcess(
                target=DavidsSquid, 
                args=(c1, c2, p3, p4, vlock3, vlock4, vs),
                name="DS"
            ),
            VProcess(
                target=consumer, 
                args=(c3, ),
                name="c1"
            ),
            VProcess(
                target=consumer, 
                args=(c4,),
                name="c2"
            )]

    locks = [vlock1, vlock2, vlock3, vlock4]
    connections = [p1, c1, p2, c2, p3, c3, p4, c4]
    selects = [vs]

    return processes, connections, locks, selects



# Test 1 - Uncomment this and out comment other tests to run
#p = []
#c = []
#
#processes, channels = pingPongTest()
#p.extend(processes)
#c.extend(channels)
#processes, channels = producerDoubleConsumerTest()
#p.extend(processes)
#c.extend(channels)
#processes, channels = producerConsumerTest()
#p.extend(processes)
#c.extend(channels)
#processes, channels = transmitterTest()
#p.extend(processes)
#c.extend(channels)
#processes, channels = doubleInTransmitterTest()
#p.extend(processes)
#c.extend(channels)
#processes, channels = doubleOutTransmitterTest()
#p.extend(processes)
#c.extend(channels)
#processes, channels = p, c
#vmanager = VManager(processes, channels)

# Test 2
#processes, channels, locks = twoLockLockedProducerConsumerTest()
#vmanager = VManager(processes, channels, locks)

# Test 3
processes, channels, locks, selects = DavidsSquidTest()
vmanager = VManager(processes, channels, locks, selects)

vmanager.init_graph()
vmanager.start()

ableProcesses = vmanager.run_all_to_tick(processes)

running = True
while running:
    response = input("Press enter to run next tick:")
    if response == "q" or response == "quit":
        running = False
    if running:
        ableProcesses = vmanager.run_all_to_tick(ableProcesses)