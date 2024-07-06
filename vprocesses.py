import multiprocessing
import select
import graphviz
import random

# VConnections no longer have separate connections but have the connections of their VProcess which are assigned upon initialization of the manager 
# No need for select objects
# No need to instantiate multiple VLocks. The same object can be share across multiple processes
# Nested release and acquire calls on different locks are resolved in the same tick
# Same for nested select calls if something is being sent on one of the channels that are being listened on

class VManager():
    def __init__(self, vprocesses, vconnections, vlocks=[], logging=False, output='output/Tick', outputFormat='pdf', interactiveLocks=False, logFileName="log.txt", draw=True, tickTock=True, incrTicks=True) -> None:
        self.processes = vprocesses # List of VProcess passed as to the class constructor as argument
        self.connections = vconnections # List of VConnection classes passed to the class constructor as argument
        if type(vlocks) == VLock:
            vlocks = [vlocks] 
        self.locks = vlocks # List of VLock objects
        self.fromToConnectionDict = {} # Dictionary of normal connections, where they key is the connection intended for the manager to receive messages from sync-objects and the value is connection used to send to sync-objects. Populated in __init__
        self.syncObjectProcessLookup = {} # Dictionary mapping VConnections to process names
        self.processToManagerSendConn = {} # Dictionary mapping process name to that process' send connection to the manager 
        self.processToManagerRecvConn = {} # Dictionary mapping process name to that process' receive connection from the manager
        self.processToWorkerSendConn = {} # Dictionary mapping process name to that process' send connection to the worker
        self.processToWorkerRecvConn = {} # Dictionary mapping process name to that process' receive connection from the worker
        self.tickCounter = 0 # Counter used for the number on the image file and showing which tick is run
        self.edges = [] # List of edges between processes for the graph used for drawing the image
        self.processNodes = [] # List of process nodes for the graph used for drawing the image
        self.lockNodes = [] # List of lock nodes for the graph used for drawing the image - Could possibly be merged with processNodes
        self.lockEdges = [] # List of edges between processes and locks for the graph used for drawing the image
        self.lockedLocks = [] # List of locks that are currently locked 
        self.waitingToSend = [] # List of processes waiting to send 
        self.waitingToReceive = [] # List of processes waiting to receive
        self.waitingToAcquire = [] # List of processes waiting to acquire a lock
        self.waitingToRelease = [] # List of processes waiting to release a lock
        self.waitingToSelect = [] # List of processes waiting to select
        self.prematureSelectSends = [] # List of sending processes that have been allowed to send because of an intervening select statment. However the processes are still not considered able, until the receiving sides have received on the channels.
        self.previousTickProcessCount = 0
        self.logging = logging
        self.outputFileName = output
        self.outputFormat = outputFormat
        self.interactive = interactiveLocks
        self.draw = draw
        self.tickTock = tickTock
        self.incrementTicks = incrTicks
        
        if logging:
            self.log = open(logFileName, "w")
        
        locknamenum = 1
        for lock in self.locks:
            if type(lock.name) == int:
                lock.name = "lock" + str(locknamenum)
                locknamenum += 1
                self.lockNodes.append(lock.name)

        # Setting up connections
        for process in self.processes:
            self.processNodes.append([process.name, "green", "solid", process.name])
            recv, send = process.setup_manager_connection()
            self.fromToConnectionDict[recv] = send
            self.processToManagerSendConn[process.name] = process.send_to_manager
            self.processToManagerRecvConn[process.name] = process.recv_from_manager
            self.processToWorkerRecvConn[process.name] = process.recv_from_worker
            for connection in process.connections:
                connection.send_to_manager = process.send_to_manager
                connection.recv_from_manager = process.recv_from_manager
                self.syncObjectProcessLookup[connection.name] = process

        VSelect.setDictionaries(self.processToManagerSendConn, self.processToManagerRecvConn)
        for lock in self.locks:
            lock.setDictionaries(self.processToManagerSendConn, self.processToManagerRecvConn)

    def start(self):
        self.init_graph()
        for p in self.processes:
            p.start()
    
    def stepwiseTicks(self, processes):
        running = True
        while running:
            response = input("Press enter to run next tick, type 'd' to draw graph or 'q' to end execution:")
            if response == "q" or response == "quit":
                running = False
                if self.logging:
                    self.log.close()
            elif response == "d":
                self.drawGraph()
            else:
                processes = self.runAllToTick(processes)
                if not self.processes:
                    running = False

    def runTicksToEnd(self, processes):
        while self.processes:
            processes = self.runAllToTick(processes)
            if processes == False:
                break

    def runAllToTick(self, processes):
        self.tickCounter += 1
        print(f"Tick {self.tickCounter} started")
        
        if self.previousTickProcessCount == 0 and len(processes) == 0:
            print("Exiting - System is not progressing! - Either because of a deadlock, a process is blocking or a bug.")
            return False
        
        self.previousTickProcessCount = len(processes)

        releases, acquires, selects = self.getRequests(processes)

        acquires.extend(self.waitingToAcquire)
        selects.extend(self.waitingToSelect)

        acquires, selects = self.handleNonChannels(releases, acquires, selects)

        self.waitingToAcquire = acquires
        self.waitingToSelect = selects

        updateNodesList = []

        updateEdgesList, updateNodesList = self.handleSend(updateNodesList)

        updateNodesList, updateEdgesList = self.handleReceive(updateEdgesList, updateNodesList)

        self.updateGraph(updateNodesList, updateEdgesList)

        ableProcesses = self.getAbleProcesses()
    
        #self.printState()
        #print("ableProcesses: ", ableProcesses)
        
        return ableProcesses
    
    def getRequests(self, ableProcesses):
        requestsSentFromAbleProcesses = [0 for _ in ableProcesses]
        loglist = []
        releases = []
        acquires = []
        selects = []
        for index, process in enumerate(ableProcesses):
            conn = self.processToWorkerRecvConn[process.name]
            request = conn.recv()
            requestsSentFromAbleProcesses[index] += 1
            action, rest = request 
            if action == "acquire":
                lockName = rest
                acquires.append([lockName, process.name, self.fromToConnectionDict[conn]]) 
                loglist.append(f"{process.name} requests to acquire {lockName}")
            elif action == "release":
                lockName = rest
                releases.append([lockName, process.name, self.fromToConnectionDict[conn]]) 
                loglist.append(f"{process.name} requests to release {lockName}")
            elif action == "select":
                selectlist = rest
                selects.append([process.name, self.fromToConnectionDict[conn], selectlist])
                loglist.append(f"{process.name} requests to selecting")
            elif action == "terminate": 
                self.fromToConnectionDict[conn].send(True)
                self.processes.remove(process)
                self.updateNode(process.name, "black", "bold", process.name + "☠️")
                process.join()
                loglist.append(f"{process.name} requests to terminate")
            else:
                vconnName, otherEndsVConnName, transfer = rest
                if action == "recv":
                    self.waitingToReceive.append((otherEndsVConnName, vconnName, " ", self.fromToConnectionDict[conn]))
                    loglist.append(f"{process.name} requests to receive from {self.syncObjectProcessLookup[otherEndsVConnName].name}")
                elif action == "send":
                    self.waitingToSend.append((vconnName, otherEndsVConnName, transfer, self.fromToConnectionDict[conn]))
                    loglist.append(f"{process.name} requests to send to {self.syncObjectProcessLookup[otherEndsVConnName].name}")
        
        if self.logging:
            self.log.write(f"Tick {self.tickCounter}" + '\n')
            for entry in loglist:
                self.log.write(entry + '\n')
                self.log.flush()

        for request in requestsSentFromAbleProcesses:
            if request != 1:
                print(f"ERROR: A PROCESS HAS EITHER SENT MORE THAN ONE MESSAGES OR NOT SENT A MESSAGE - {requestsSentFromAbleProcesses}")

        return releases, acquires, selects
    
    def handleSend(self, updateNodesList):
        updateEdgesList = []

        for request in self.waitingToSend:
            for edge in self.edges:
                if edge[0] == request[0] and edge[1] == request[1]:
                    if self.tickTock:
                        condition = edge[2] == ' '
                    else:
                        condition = True
                    if condition:
                        updateEdgesList.append([request[0], request[1], request[2]])
                        process = self.syncObjectProcessLookup[request[0]].name
                        updateNodesList.append([process, 'red', 'solid', process])
        
        return updateEdgesList, updateNodesList

    def handleSelect(self, releaseList, acquireList, selectList):

        newrl = []
        newal = []
        newsl = []

        selected = False

        tmpSelectList = selectList[:]
        tmpSendList = self.waitingToSend[:]
        tmpPrematureSendList = self.prematureSelectSends[:] 
        for pslct in tmpSelectList:  # self.waitingToSelect 
            remove = False
            selectlist = pslct[2] 
            for conn in selectlist:
                edge = self.getRecvEdge(conn.name)
                if self.tickTock:
                    condition = edge[2] != ' '
                else:
                    condition = True
                if condition:
                    for wts in tmpSendList: #self.waitingToSend
                        if conn.name == wts[1]:
                            wts[3].send(True)
                            remove = True
                            self.prematureSelectSends.append(wts) # These being appended before receive should not matter for handleReceive, as there should not be requests waiting to receive on the channel, as the selecting process will be the one receiving eventually.
                            self.waitingToSend.remove(wts) 
                    for pss in tmpPrematureSendList:
                        if conn.name == pss[1]:
                            remove = True

            if remove == True:
                selected = True
                pslct[1].send(True)
                process = self.getProcess(pslct[0])
                rl, al, sl =self.getRequests([process])
                newrl.extend(rl)
                newal.extend(al)
                newsl.extend(sl)
                selectList.remove(pslct)

        releaseList.extend(newrl)
        acquireList.extend(newal)
        selectList.extend(newsl)
        
        return releaseList, acquireList, selectList, selected
    
    def handleReceive(self, updateEdgesList, updateNodesList):
        
        removeRecv = []
        for request in self.waitingToReceive:
            for currentedge in self.edges:
                if currentedge[0] == request[0] and currentedge[1] == request[1]:
                    if self.tickTock:
                        condition = currentedge[2] != ' '
                    else:
                        condition = True
                    if condition:
                        p1name = None
                        match = False
                        updateEdgesList.append([request[0], request[1], request[2]])
                        removelist = []
                        for wts in self.waitingToSend: 
                            p1name, _, _, conn = wts
                            if p1name == request[0]:
                                match = True
                                conn.send(True)
                                removelist.append(wts)
                        self.waitingToSend[:] = [wts for wts in self.waitingToSend if wts not in removelist]
                        removelist = []
                        for pss in self.prematureSelectSends:
                            if pss[0] == request[0]:
                                match = True
                                removelist.append(pss)
                        self.prematureSelectSends = [pss for pss in self.prematureSelectSends if pss not in removelist]
                        if match:
                            removeRecv.append(request)
                            process = self.syncObjectProcessLookup[request[0]].name
                            updateNodesList.append([process, 'green', 'solid', process])
                            process = self.syncObjectProcessLookup[request[1]].name
                            updateNodesList.append([process, 'green', 'solid', process])
                            request[3].send(True)

        self.waitingToReceive[:] = [conn for conn in self.waitingToReceive if conn not in removeRecv]

        for request in self.waitingToReceive:
            for node in self.processNodes:
                process = self.syncObjectProcessLookup[request[1]].name
                if process == node[0]:
                    updateNodesList.append([process, 'red', node[2], process])

        return updateNodesList, updateEdgesList
    
    def getProcess(self, name):
        for process in self.processes:
            if process.name == name:
                return process

    def acquireLocks(self, releaseList, acquireList, selectList):
        processesWaitingToAcquire = acquireList[:]
        newrl = []
        newal = []
        newsl = []

        acquired = False

        templocks = self.lockNodes[:]
        for lock in templocks:
            if not self.checkLocked(lock):
                templist = []
                for pwta in processesWaitingToAcquire:
                    if lock == pwta[0]:
                        templist.append(pwta)
                if len(templist) > 0:
                    if self.interactive and len(templist) > 1:
                        for i, process in enumerate(templist):
                            print(f"Enter {i} to let {process[1]} acquire {lock}")
                        while True:
                            response = input("Make your choice: ")
                            try:
                                 int(response)
                            except ValueError:
                                print(f"{response} is not an integer")
                            else:
                                choice = int(response)
                                if choice < 0 or choice >= len(templist): 
                                    print(f"{choice} is not a valid valid choice")
                                else:
                                    templist[choice][2].send(True)                                    
                                    process = self.getProcess(templist[randIndex][1])
                                    rl, al, sl = self.getRequests([process])
                                    newrl.extend(rl)
                                    newal.extend(al)
                                    newsl.extend(sl)
                                    self.lockedLocks.append([templist[choice][0], templist[choice][1]])
                                    acquireList.remove(templist[choice])
                                    break
                    else:
                        acquired = True
                        randIndex = random.randint(0, len(templist) - 1)
                        templist[randIndex][2].send(True)
                        process = self.getProcess(templist[randIndex][1])
                        rl, al, sl = self.getRequests([process])
                        newrl.extend(rl)
                        newal.extend(al)
                        newsl.extend(sl)
                        self.lockedLocks.append([templist[randIndex][0], templist[randIndex][1]])
                        acquireList.remove(templist[randIndex])

        releaseList.extend(newrl)
        acquireList.extend(newal)
        selectList.extend(newsl)

        return releaseList, acquireList, selectList, acquired
    
    def handleNonChannels(self, releaseList, acquireList, selectList):

        acquired = True
        while (releaseList or acquireList or selectList) and acquired:
            acquired = False
            selected = True
            while (releaseList or selectList) and selected:
                selected = False
                
                while releaseList:
                    releaseList, acquireList, selectList = self.releaseLocks(releaseList, acquireList, selectList)
    
                if selectList:
                    releaseList, acquireList, selectList, selected = self.handleSelect(releaseList, acquireList, selectList)

            if acquireList:
                releaseList, acquireList, selectList, acquired = self.acquireLocks(releaseList, acquireList, selectList)
            else: 
                break

        return acquireList, selectList

    def releaseLocks(self, releaseList, acquireList, selectList):
        newrl = []
        newal = []
        newsl = []
        removelist = []

        tempReleaseList = releaseList[:]
        for wtr in tempReleaseList:
            wtr[2].send(True)
            process = self.getProcess(wtr[1])
            rl, al, sl = self.getRequests([process])
            newrl.extend(rl)
            newal.extend(al)
            newsl.extend(sl)
            self.lockedLocks.remove([wtr[0], wtr[1]])
            removelist.append(wtr)

        for r in removelist:
            releaseList.remove(r)

        releaseList.extend(newrl)
        acquireList.extend(newal)
        selectList.extend(newsl)

        return releaseList, acquireList, selectList

    def getAbleProcesses(self):
        
        ableProcesses = self.processes[:]
        
        for process in self.processes:
            for p in self.waitingToSend: 
                if process.name == self.syncObjectProcessLookup[p[0]].name:
                    ableProcesses.remove(process)
            for p in self.prematureSelectSends: 
                if process.name == self.syncObjectProcessLookup[p[0]].name:
                    ableProcesses.remove(process)
            for p in self.waitingToReceive:
                if process.name == self.syncObjectProcessLookup[p[1]].name:
                    ableProcesses.remove(process)
            for p in self.waitingToAcquire: 
                if process.name == p[1]:
                    ableProcesses.remove(process)
            for p in self.waitingToSelect:
                if process.name == p[0]:
                    ableProcesses.remove(process)

        return ableProcesses

    def init_graph(self):
        
        for process in self.processes:
            for conn in process.connections:
                if type(conn) == VConnection:
                    for p2 in self.processes:
                        for conn2 in p2.connections:
                            if type(conn2) == VConnection:
                                if conn.otherEndsName == conn2.name and conn.sender == True:
                                    self.edges.append([conn.name, conn2.name, " "])

            for lock in process.locks:
                if type(lock) == VLock:
                    self.lockEdges.append([lock.name, process.name, "black", "dashed"])     

        if self.draw:
            self.drawGraph()

    def updateGraph(self, updateNodesList, updateEdgesList):
        
        for node in updateNodesList:
            self.updateNode(node[0], node[1], node[2], node[3])
        
        for edge in updateEdgesList:
            self.updateEdge(edge[0], edge[1], edge[2])
        
        for node in self.waitingToSelect:
            self.updateNode(node[0], 'red', 'dashed', node[0])

        for request in self.waitingToAcquire:
            self.updateNode(request[1], 'red', 'solid', request[1])
        
        for edge in self.lockEdges:
            self.updateLockEdge(edge[0], edge[1], 'black', 'dashed')

        for req in self.waitingToAcquire:
            self.updateLockEdge(req[0], req[1], 'purple', 'dashed')

        for lock in self.lockedLocks:
            self.updateLockEdge(lock[0], lock[1], 'blue', 'solid')
        
        if self.draw:
            self.drawGraph()

    def drawGraph(self):

        dgraph = graphviz.Digraph(format=self.outputFormat)
        dgraph.attr(label=f"Tick {self.tickCounter}", labelloc="t")

        for node in self.processNodes: # Format: [process name, color, style, label]
            dgraph.node(node[0], color=node[1], style=node[2], label=node[3])

        for edge in self.edges: # Format: [vconn1 name, vconn2 name, transfer data]
            p1 = self.syncObjectProcessLookup[edge[0]].name
            p2 = self.syncObjectProcessLookup[edge[1]].name
            dgraph.edge(p1, p2, edge[2]) 

        for node in self.lockNodes: # Format: [lock name]
            dgraph.node(node, shape="square")

        for edge in self.lockEdges: # Format: [lock name, process name, color, style]
            dgraph.edge(edge[0], edge[1], color=edge[2], style=edge[3], dir="none")
        
        if self.incrementTicks:
            filename = self.outputFileName + '_' + str(self.tickCounter)
        else:
            filename = self.outputFileName
        
        dgraph.render(filename)

    def updateEdge(self, name1, name2, input):
        for edge in self.edges:
            if name1 == edge[0] and name2 == edge[1]:
                edge[2] = str(input)

    def updateLockEdge(self, name1, name2, color, style):
        for edge in self.lockEdges:
            if name1 == edge[0] and name2 == edge[1]:
                edge[2] = color
                edge[3] = style

    def updateNode(self, node, color, style, label):
        for processNode in self.processNodes:
            if node == processNode[0]:
                processNode[1] = color
                processNode[2] = style
                processNode[3] = label 

    def printState(self):
        print(f"self.waitingToSend: {self.waitingToSend}")
        print(f"self.waitingToReceive: {self.waitingToReceive}")
        print(f"self.prematureSelectSends: {self.prematureSelectSends}")
        print(f"self.waitingToSelect: {self.waitingToSelect}")
        print(f"self.waitingToAcquire {self.waitingToAcquire}")
        print(f"self.waitingToRelease {self.waitingToRelease}")
        print(f"self.lockedLocks {self.lockedLocks}")
    
    def checkLocked(self, lock):
        for pair in self.lockedLocks:
            if pair[0] == lock:
                return True
    
    def getSendEdge(self, id):
        for edge in self.edges:
            if edge[0] == id:
                return edge

    def getRecvEdge(self, id):
        for edge in self.edges:
            if edge[1] == id:
                return edge


class VProcess(multiprocessing.Process):
    num = 0
    def __init__(self, group = None, target = None, name = None, args = [], kwargs = {}, *, daemon = None) -> None:
        if not name:
            name = 'p' + str(VProcess.num)
            VProcess.num += 1
        super().__init__(group, target, name, args, kwargs, daemon=daemon)
        self.connections = [] # All synchronization objects given as parameters to target
        self.locks = []

        for arg in args:
            if type(arg) == VConnection:
                self.connections.append(arg)
            if type(arg) == VLock:
                self.locks.append(arg)
            if type(arg) == list:
                for elm in arg:
                    if type(elm) == VConnection:
                        self.connections.append(elm)
                    if type(elm) == VLock:
                        self.locks.append(elm)

    def setup_manager_connection(self):
        self.send_to_manager, self.recv_from_worker = multiprocessing.Pipe()
        self.send_to_worker, self.recv_from_manager = multiprocessing.Pipe()
        return self.recv_from_worker, self.send_to_worker

    def run(self):
        super().run()
        self.send_to_manager.send(("terminate", self.name))
        self.recv_from_manager.recv()


class VLock():
    def __init__(self, name=None):
        self.lock = multiprocessing.Lock()
        if name: 
            self.name = name
        else:
            self.name = id(self)
    
    def setDictionaries(self, sendDict, recvDict):
        self.processToManagerSendConn = sendDict
        self.processToManagerRecvConn = recvDict
        
    def acquire(self):
        processName = multiprocessing.current_process().name
        sendconn = self.processToManagerSendConn[processName]
        recvconn = self.processToManagerRecvConn[processName]
        sendconn.send(("acquire", self.name))
        recvconn.recv()
        self.lock.acquire()

    def release(self):
        processName = multiprocessing.current_process().name
        sendconn = self.processToManagerSendConn[processName]
        recvconn = self.processToManagerRecvConn[processName]
        sendconn.send(("release", self.name))
        recvconn.recv()
        self.lock.release()


class VSelect():

    @classmethod
    def setDictionaries(cls, sendDict, recvDict):
        cls.processToManagerSendConn = sendDict
        cls.processToManagerRecvConn = recvDict

    @classmethod
    def select(cls, vselectlist1, selectlist2=[], selectlist3=[]):
        processName = multiprocessing.current_process().name
        sendconn = cls.processToManagerSendConn[processName]
        recvconn = cls.processToManagerRecvConn[processName]
        sendconn.send(("select", vselectlist1)) # For now just sending selectlist1
        recvconn.recv()
        selectlist1 = [vconn.connection for vconn in vselectlist1]
        (inputs1, inputs2, inputs3) = select.select(selectlist1, selectlist2, selectlist3)
        vinputs1 = []
        for connection in inputs1:
            for vconnection in vselectlist1:
                if connection == vconnection.connection:
                    vinputs1.append(vconnection)
        return vinputs1, inputs2, inputs3


class VConnection():
    def __init__(self, connection, name, otherEndsName, sender=True) -> None:
        self.name = name
        self.otherEndsName = otherEndsName
        self.connection = connection
        self.send_to_manager = None
        self.recv_from_manager = None
        self.sender = sender

    def send(self, data):
        self.send_to_manager.send(("send", [self.name, self.otherEndsName, data]))
        good_to_go = self.recv_from_manager.recv()
        if good_to_go:
            self.connection.send(data)
    
    def recv(self):
        self.send_to_manager.send(("recv", [self.name, self.otherEndsName, " "]))
        good_to_go = self.recv_from_manager.recv()
        if good_to_go:
            data = self.connection.recv()
            return data


def VPipe(name=""):
    end1, end2 = multiprocessing.Pipe()
    if name == "":
        name = id(end1)
    vconn1 = VConnection(end1, f"{name}_w", f"{name}_r", sender=True)
    vconn2 = VConnection(end2, f"{name}_r", f"{name}_w", sender=False)

    return vconn1, vconn2

# Aliases

Pipe = VPipe
Process = VProcess
Lock = VLock
current_process = multiprocessing.current_process
