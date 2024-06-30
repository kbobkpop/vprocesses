import multiprocessing
import select
import graphviz
import random
import os
import shutil
import time

#VConnections no longer have separate connections but have the connections of their VProcess which are assigned upon initialization of the manager 
#No need for select objects
#No need to instantiate multiple VLocks. The same object can be share across multiple processes

# Problem! - Not updating graph in current tick when acquiring a lock - Look at moving send or acquire lock
# Problem! - cannot handle nested locks and select calls - Make the logic of acquiring, releasing locks and calling select a loop

class VManager():
    def __init__(self, vprocesses, vconnections, vlocks=[], vselects=[], logging=False, output='output/Tick', outputFormat='pdf', interactiveLocks=False, logFileName="log.txt", terminateProcesses=True, draw=True) -> None:
        self.processes = vprocesses # List of VProcess passed as to the class constructor as argument
        self.connections = vconnections # List of VConnection classes passed to the class constructor as argument
        self.locks = vlocks # List of VLock objects
        self.selects = vselects # List of VSelect objects
        self.fromToConnectionDict = {} # Dictionary of normal connections, where they key is the connection intended for the manager to receive messages from sync-objects and the value is connection used to send to sync-objects. Populated in __init__
        self.syncObjectProcessLookup = {} # Dictionary mapping VConnections to process names
        self.processToManagerSendConn = {}
        self.processToManagerRecvConn = {}
        self.tickCounter = 0 # Counter used for the number on the image file and showing which tick is run
        self.edges = [] # List of edges between processes for the graph used for drawing the image
        self.processNodes = [] # List of process nodes for the graph used for drawing the image
        self.lockNodes = [] # List of lock nodes for the graph used for drawing the image - Could possibly be merged with processNodes
        self.lockEdges = [] # List of edges between processes and locks for the graph used for drawing the image
        self.selectNodes = [] # List of select nodes for the graph used for drawing the image
        self.waitingToSend = [] # List of processes waiting to send 
        self.waitingToReceive = [] # List of processes waiting to receive
        self.waitingToAcquire = [] # List of processes waiting to acquire a lock
        self.waitingToRelease = [] # List of processes waiting to release a lock
        self.waitingToSelect = [] # List of processes waiting to select
        self.lockedLocks = [] # List of locks that are currently locked 
        self.prematureSelectSends = [] # List of sending processes that have been allowed to send because of an intervening select statment. However the processes are still not considered able, until the receiving sides have received on the channels.
        if logging:
            self.log = open(logFileName, "w")
        self.previousTickProcessCount = 0
        self.logging = logging
        self.outputFileName = output
        self.outputFormat = outputFormat
        self.interactive = interactiveLocks
        self.terminateProcesses = terminateProcesses
        self.draw = draw
        
        locknamenum = 1
        for lock in self.locks:
            if type(lock.name) == int:
                tempname = lock.name
                for name in self.locks:
                    if name.name == tempname:
                        name.name = "lock" + str(locknamenum)
                locknamenum += 1
        
        for lock in self.locks:
            if not lock.name in self.lockNodes: # There are multiple VLocks sharing the same name
                self.lockNodes.append(lock.name)

        # Setting up connections
        for process in self.processes:
            self.processNodes.append([process.name, "green", "solid", process.name])
            recv, send = process.setup_manager_connection()
            process.from_worker_connections.append(recv)
            process.to_worker_connections.append(send)
            self.fromToConnectionDict[recv] = send
            self.processToManagerSendConn[process.name] = process.send_to_manager
            self.processToManagerRecvConn[process.name] = process.recv_from_manager
            for connection in process.connections:
                connection.send_to_manager = process.send_to_manager
                connection.recv_from_worker = process.recv_from_worker
                connection.send_to_worker = process.send_to_worker
                connection.recv_from_manager = process.recv_from_manager
                self.syncObjectProcessLookup[connection.name] = process

        VSelect.setDictionaries(self.processToManagerSendConn, self.processToManagerRecvConn)
        for lock in self.locks:
            lock.setDictionaries(self.processToManagerSendConn, self.processToManagerRecvConn)

    def start(self):
        for p in self.processes:
            p.start()
    
    def stepwiseTicks(self, processes):
        running = True
        while running:
            response = input("Press enter to run next tick, type 'd' to draw graph or 'q' to end execution:")
            if response == "q" or response == "quit":
                running = False
                if self.logging:
                    vmanager.log.close()
            elif response == "d":
                self.drawGraph()
            else:
                processes = vmanager.runAllToTick(processes)
                if not self.processes:
                    running = False

    def runTicksToEnd(self, processes):
        while self.processes:
                processes = vmanager.runAllToTick(processes)
                if processes == False:
                    break

    def runAllToTick(self, processes):
        self.tickCounter += 1
        print(f"Tick {self.tickCounter} started")
        
        if self.previousTickProcessCount == 0 and len(processes) == 0:
            print("Exiting - System is not progressing! - Either because of a deadlock, a process is blocking or a bug.")
            return False
        
        self.previousTickProcessCount = len(processes)
        
        releases = []
        acquires = []

        #releases, acquires = self.getRequests(processes)
        releases, acquires = self.getRequests(processes)

        acquires.extend(self.waitingToAcquire)

        print(f"Pre handleLocks: releases: {releases} acquires: {acquires}")
        acquires = self.handleLocks(releases, acquires)

        print(f"Post handleLocks: releases: {releases} acquires: {acquires}")
        self.waitingToAcquire = acquires
        #updateLocksList, updateNodesList, progressList = self.releaseLocks()
#
        #updateLocksList, updateNodesList = self.acquireLocks(updateLocksList, updateNodesList, progressList)

        updateNodesList = []

        updateEdgesList, updateNodesList = self.handleSend(updateNodesList)

        updateNodesList = self.handleSelect(updateNodesList)

        updateNodesList, updateEdgesList = self.handleReceive(updateEdgesList, updateNodesList)

        self.updateGraph(updateNodesList, updateEdgesList)

        ableProcesses = self.getAbleProcesses()
    
        self.printState()
        print("ableProcesses: ", ableProcesses)

        return ableProcesses

    def getRequests(self, ableProcesses):
        requestsSentFromAbleProcesses = [0 for _ in ableProcesses]
        if self.logging:
            loglist = []
        #removeList = []
        releases = []
        acquires = []
        for index, process in enumerate(ableProcesses):
            print(f"{index}: process: {process.name}")
            conn = process.recv_from_worker
            request = conn.recv()
            #self.parseRequest(process.recv_from_worker, request, process)
            requestsSentFromAbleProcesses[index] += 1
            action, data = request 
            if action == "acquire":
                process1Name, lockName = data
                acquires.append([lockName, process1Name, self.fromToConnectionDict[conn]])
                #if self.logging:
                #    loglist.append(f"{process1Name} requests to acquire {lockName}")
            elif action == "release":
                process1Name, lockName = data
                releases.append([lockName, process1Name, self.fromToConnectionDict[conn]])
                #if self.logging:
                #    loglist.append(f"{process1Name} requests to release {lockName}")
            elif action == "select":
                process1Name, selectlist = data
                self.waitingToSelect.append([process1Name, self.fromToConnectionDict[conn], selectlist])
                #if self.logging:
                #    loglist.append(f"{process1Name} requests to selecting")
            elif action == "terminate":
                process1Name = data 
                self.fromToConnectionDict[conn].send(True)
                self.processes.remove(process)
                #removeList.append(process)
                self.updateNode(process.name, "black", "bold", process.name + "☠️")
                process.join()
                #if self.logging:
                #    loglist.append(f"{self.syncObjectProcessLookup[process1Name].name} requests to terminate")
            else:
                vconnName, otherEndsVConnName, transfer = data
                if action == "recv":
                    self.waitingToReceive.append((otherEndsVConnName, vconnName, " ", self.fromToConnectionDict[conn], otherEndsVConnName))
                    #if self.logging:
                    #    loglist.append(f"{self.syncObjectProcessLookup[vconnName].name} requests to receive from {self.syncObjectProcessLookup[otherEndsVConnName].name}")
                elif action == "send":
                    self.waitingToSend.append((vconnName, otherEndsVConnName, transfer, self.fromToConnectionDict[conn], otherEndsVConnName))
                    #if self.logging:
                    #    loglist.append(f"{self.syncObjectProcessLookup[vconnName].name} requests to send to {self.syncObjectProcessLookup[otherEndsVConnName].name}")
        
        if self.logging:
            self.log.write(f"Tick {self.tickCounter}" + '\n')
            for entry in loglist:
                self.log.write(entry + '\n')
                self.log.flush()

        for request in requestsSentFromAbleProcesses:
            if request != 1:
                print(f"ERROR: A PROCESS HAS SENT MORE THAN ONE MESSAGE - {requestsSentFromAbleProcesses}")

        return releases, acquires
    
    # Parse all pending requests, append updates to the graph lists
    # Uses the state of: 
    #   - self.lockEdges, self.waitingToAcquire, self.waitingToSelect, self.waiting_to_send_connection, self.waiting_to_receive_connection, self.selectNodes, self.edges, self.prematureSelectSends
    # May change the state of: self.prematureSelectSends, self.waitingToSelect, self.waiting_to_send_connection, self.prematureSelectSends, self.waiting_to_receive_connection
    def handleSend(self, updateNodesList):
        updateEdgesList = []

        for request in self.waitingToSend:
            for edge in self.edges:
                if edge[0] == request[0] and edge[1] == request[1]:
                    if edge[2] == ' ':
                        updateEdgesList.append([request[0], request[1], request[2]])
                        process = self.syncObjectProcessLookup[request[0]].name
                        updateNodesList.append([process, 'red', 'solid', process])
        
        return updateEdgesList, updateNodesList


    def getSendEdge(self, id):
        for edge in self.edges:
            if edge[0] == id:
                return edge

    def getRecvEdge(self, id):
        for edge in self.edges:
            if edge[1] == id:
                return edge

    def handleSelect(self, updateNodesList):
        #updateNodesList = []
        for select in self.waitingToSelect:
            updateNodesList.append([select[0], 'red', 'dashed', select[0]])
        
        tmpSelectList = self.waitingToSelect[:]
        tmpSendList = self.waitingToSend[:]
        tmpPrematureSendList = self.prematureSelectSends[:] 
        for pslct in tmpSelectList:  # self.waitingToSelect #Select objec
            remove = False
            selectlist = pslct[2] 
            for conn in selectlist:
                #print("conn:", conn.name)
                edge = self.getRecvEdge(conn.name)
                if edge[2] != ' ':
                    for wts in tmpSendList: #self.waitingToSend
                        if conn.name == wts[4]:                     
                            wts[3].send(True)
                            remove = True
                            self.prematureSelectSends.append(wts) # These being appended before should not matter for the receive loop, as there should not be requests waiting to receive on the channel, as the selecting process will be the one receiving ecentually.
                            self.waitingToSend.remove(wts) 
                    for pss in tmpPrematureSendList: #self.prematureSelectSends - If there is a connection matching on the prematureSelectSends to one of those being selected upon the selecting process is allowed to proceed
                        if conn.name == pss[4]:
                            remove = True

            if remove == True:
                pslct[1].send(True)
                #process = self.getProcess(pslct[0])
                #self.getRequests([process])
                self.waitingToSelect.remove(pslct)

        for request in self.waitingToReceive:
            for node in self.processNodes:
                if self.syncObjectProcessLookup[request[1]].name == node[0]:
                    updateNodesList.append([node[0], 'red', 'solid', node[0]])
        
        return updateNodesList

    
    def handleReceive(self, updateEdgesList, updateNodesList):
        
        removeRecv = []
        for request in self.waitingToReceive: # should be able to be replaced with waiting to receive.  The premature send is in the uncompleted receive
            for currentedge in self.edges:
                if currentedge[0] == request[0] and currentedge[1] == request[1]: #For each edge in the graph check if there is a corresponding uncompletedRecv
                    if currentedge[2] != ' ': #Since this is true, there must be a connection sending on that connection either in self.waitingToSend or self.prematureSelectSends
                        p1name = None
                        match = False
                        # An edge is being added to be updated below for the visual graph and the send and receive is being completed, by sending a message to the two connections.
                        # - Unless a permission has already been sent in case of a premature select send, in which case a permission is only being sent to the receiving process.
                        updateEdgesList.append([request[0], request[1], request[2]])
                        removelist = []
                        for wts in self.waitingToSend: 
                            p1name, _, _, conn, _ = wts
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

    #def acquireLocks(self, updateLocksList, updateNodesList, progressList):
    def acquireLocks(self, releaseList, acquireList):
        processesWaitingToAcquire = acquireList[:]
        newrl = []
        newal = []

        acquired = False

        templocks = self.lockNodes[:]
        for lock in templocks:
            if not self.checkLocked(lock):
            #if lock not in self.lockedLocks:
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
                                    #updateLocksList.append([templist[choice][0], templist[choice][1], ' ', 'blue', 'solid'])
                                    self.lockedLocks.append([templist[choice][0], templist[choice][1]])
                                    acquireList.remove(templist[choice])
                                    break
                    else:
                        acquired = True
                        randIndex = random.randint(0, len(templist) - 1)
                        templist[randIndex][2].send(True)
                        process = self.getProcess(templist[randIndex][1])
                        rl, al = self.getRequests([process])
                        print("received requests:", rl, al)
                        newrl.extend(rl)
                        newal.extend(al)

                        self.lockedLocks.append([templist[randIndex][0], templist[randIndex][1]])
                        acquireList.remove(templist[randIndex])

        releaseList.extend(newrl)
        acquireList.extend(newal)

        #self.getRequests(progressList)

        #for currentLockEdge in self.lockEdges:
        #    for newedge in self.waitingToAcquire:
        #        if currentLockEdge[0] == newedge[0] and currentLockEdge[1] == newedge[1]:
        #            updateLocksList.append([newedge[0], currentLockEdge[1], ' ', 'purple', 'dashed'])
        #            updateNodesList.append([newedge[1], 'red', 'solid', newedge[1]])

        return releaseList, acquireList, acquired

    # For each process request waiting to release a lock: 
    #   - If that process is neither in self.prematureSelectSends nor in self.waiting_to_send_connection
    #   - Send a permission to that process to release, remove that lock from self.lockedlocks and that request from self.waitingToRelease
    
    def checkLocked(self, lock):
        for pair in self.lockedLocks:
            if pair[0] == lock:
                return True

    def handleLocks(self, releaseList, acquireList):

        #handle all releases
        #handle all acquires
        acquired = True
        while (releaseList or acquireList) and acquired:
            while releaseList:
                print("calling releaseLocks")
                releaseList, acquireList = self.releaseLocks(releaseList, acquireList)
    
            if acquireList:
                print("calling acquireLocks, acquireList:", acquireList)
                releaseList, acquireList, acquired = self.acquireLocks(releaseList, acquireList)
                print("post acquireLocks, acquireList:", acquireList)
            #    if not acquired:
            #        break
            #else:
            #    break
        
        return acquireList

    def releaseLocks(self, releaseList, acquireList):
        newrl = []
        newal = []
        removelist = []
        #progressList = []

        #for wtr in self.waitingToRelease:
        #    wtr[2].send(True)
        #    process = self.getProcess(wtr[1])
        #    progressList.append(process)
        #    #self.getRequests([process])
        #    updateLockList.append([wtr[0], wtr[1], ' ', 'black', 'dashed']) # Updates the graph when waiting to release, such that it can be acquired in same tick
        #    updateNodesList.append([wtr[1], 'green', 'solid', wtr[1]])
        #    self.lockedLocks.remove(wtr[0])
        #    removelist.append(wtr)
        tempReleaseList = releaseList[:]
        for wtr in tempReleaseList:
            wtr[2].send(True)
            process = self.getProcess(wtr[1])
            #progressList.append(process)
            rl, al = self.getRequests([process])
            newrl.extend(rl)
            newal.extend(al)
            #updateLockList.append([wtr[0], wtr[1], ' ', 'black', 'dashed']) # Updates the graph when waiting to release, such that it can be acquired in same tick
            #updateNodesList.append([wtr[1], 'green', 'solid', wtr[1]])
            self.lockedLocks.remove([wtr[0], wtr[1]])
            removelist.append(wtr)

        for r in removelist:
            releaseList.remove(r)

        releaseList.extend(newrl)
        acquireList.extend(newal)

        return releaseList, acquireList

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
            for p in self.waitingToRelease:
                if process.name == p[1]:
                    ableProcesses.remove(process)
            for p in self.waitingToSelect:
                if process.name == p[0]:
                    ableProcesses.remove(process)

        return ableProcesses

    #def updateGraph(self, updateLocksList, updateNodesList, updateEdgesList, updateSelectsList):
    def updateGraph(self, updateNodesList, updateEdgesList):
        
        for node in updateNodesList:
            self.updateNode(node[0], node[1], node[2], node[3])
        
        #for node in self.waitingToSelect:
        #    self.updateNode(node[1], 'red', 'dashed', node[1])

        for edge in self.lockEdges:
            self.updateLockEdges(edge[0], edge[1], 'black', 'dashed')

        for req in self.waitingToAcquire: #[lockName, process1Name, self.fromToConnectionDict[conn]]          
            self.updateLockEdges(req[0], req[1], 'purple', 'dashed')

        for lock in self.lockedLocks:
            self.updateLockEdges(lock[0], lock[1], 'blue', 'solid')
        
        for edge in updateEdgesList:
            self.updateEdges(edge[0], edge[1], edge[2])
        
        if self.draw:
            self.drawGraph()

    def init_graph(self):
        
        for process in self.processes:
            for conn in process.connections:
                if type(conn) == VConnection:
                    for p2 in self.processes:
                        for conn2 in p2.connections:
                            if type(conn2) == VConnection:
                                if conn.otherEnd == conn2 and conn.sender == True:
                                    self.edges.append([conn.name, conn2.name, " "])

            for lock in process.locks:
                if type(lock) == VLock:
                    self.lockEdges.append([lock.name, process.name, " ", "black", "dashed"])

                #if type(conn) == VSelect:
                    #self.selectNodes.append([process.name, "green", "solid"])           

        if self.draw:
            self.drawGraph()

    def drawGraph(self):

        dgraph = graphviz.Digraph(format=self.outputFormat)
        dgraph.attr(label=f"Tick {self.tickCounter}", labelloc="t")
        for node in self.processNodes: # Format: [name, color, style]
            dgraph.node(node[0], color=node[1], style=node[2], label=node[3])
        for edge in self.edges: # Format: [vconn1.name, vconn2.name, data]
            p1 = self.syncObjectProcessLookup[edge[0]].name
            p2 = self.syncObjectProcessLookup[edge[1]].name
            dgraph.edge(p1, p2, edge[2]) 
        for node in self.lockNodes: # Format: [lock name]
            dgraph.node(node, shape="square")
        for edge in self.lockEdges: # Format: [lock name, process name, color, style]
            dgraph.edge(edge[0], edge[1], color=edge[2], style=edge[3], dir="none")
        for node in self.selectNodes: # Format: [process name, color, style]
            dgraph.node(node[0], color=node[1], style=node[2])
        filename = self.outputFileName + '_' + str(self.tickCounter)
        dgraph.render(filename)

    def updateEdges(self, name1, name2, input):
        for edge in self.edges:
            if name1 == edge[0] and name2 == edge[1]:
                edge[2] = str(input)

    def updateLockEdges(self, name1, name2, color, style):
        for edge in self.lockEdges:
            if name1 == edge[0] and name2 == edge[1]:
                edge[2] = color
                edge[3] = style

    def updateSelectNodes(self, node, color, style):
        for selectNode in self.selectNodes:
            if node == selectNode[0]:
                selectNode[1] = color
                selectNode[2] = style

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

class VProcess(multiprocessing.Process):
    def __init__(self, group = None, target = None, name = None, args = [], kwargs = {}, *, daemon = None) -> None:
        super().__init__(group, target, name, args, kwargs, daemon=daemon)
        self.to_worker_connections = []
        self.from_worker_connections = []
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
        self.send_to_manager.send(("terminate", [self.name]))
        self.recv_from_manager.recv()


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
    
    def setDictionaries(self, sendDict, recvDict):
        self.processToManagerSendConn = sendDict
        self.processToManagerRecvConn = recvDict
        
    def acquire(self):
        processName = multiprocessing.current_process().name
        sendconn = self.processToManagerSendConn[processName]
        recvconn = self.processToManagerRecvConn[processName]
        sendconn.send(("acquire", [processName, self.name]))
        print(processName, "tries to acquire", self.name)
        recvconn.recv()
        self.lock.acquire()

    def release(self):
        processName = multiprocessing.current_process().name
        sendconn = self.processToManagerSendConn[processName]
        recvconn = self.processToManagerRecvConn[processName]
        sendconn.send(("release", [processName, self.name]))
        recvconn.recv()
        self.lock.release()


class VSelect():
    processToManagerSendConn = None
    processToManagerRecvConn = None
    def __init__(self, name=None):
        self.send_to_manager = None 
        self.recv_from_worker = None
        self.send_to_worker = None
        self.recv_from_manager = None
        self.processToManagerSendConn = {}
        self.processToManagerRecvConn = {}
        if name:
            self.name = name
        else:
            self.name = id(self) 

    @classmethod
    def setDictionaries(cls, sendDict, recvDict):
        cls.processToManagerSendConn = sendDict
        cls.processToManagerRecvConn = recvDict

    @classmethod
    def select(cls, vselectlist1, selectlist2=[], selectlist3=[]):
        processName = multiprocessing.current_process().name
        sendconn = cls.processToManagerSendConn[processName]
        recvconn = cls.processToManagerRecvConn[processName]
        sendconn.send(("select", [processName, vselectlist1])) # For now just sending selectlist1
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
        self.otherEnd = None
        self.connection = connection
        self.send_to_manager = None
        self.recv_from_worker = None
        self.send_to_worker = None 
        self.recv_from_manager = None 
        self.sender = sender

    def send(self, data):
        self.send_to_manager.send(("send", [self.name, self.otherEndsName, data]))
        good_to_go = self.recv_from_manager.recv()
        if good_to_go:
            self.connection.send(data)
            print(multiprocessing.current_process().name, "just sent ", data)
    
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
    VConnection1 = VConnection(end1, f"{name}_w", f"{name}_r", sender=True)
    VConnection2 = VConnection(end2, f"{name}_r", f"{name}_w", sender=False)
    VConnection1.otherEnd = VConnection2
    VConnection2.otherEnd = VConnection1

    return VConnection1, VConnection2


# Implementation done. Below is just testing. Go to the end of the file, to try out a few tests!

# target functions for processes:
def pingpong(i, wConn, rConn, iterations, outputdir="vtest/", initial_data=""):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    if initial_data:
        wConn.send(initial_data)
        output.write(str(initial_data))
        output.flush()
    for i in range(iterations):
        data = rConn.recv()
        print(f"{i}: {data}")
        output.write(f"{i}: {data}")
        output.flush()
        wConn.send(data)
        output.write(str(data))
        output.flush()
    if not initial_data:
        data = rConn.recv()
        print(f"{i}: {data}")

def lockedPingPong(i, lock, inConn, outConn, iterations, outputdir="vtest/", initial_data=""):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    if initial_data:
        lock.acquire()
        outConn.send(initial_data)
        output.write(str(initial_data))
        output.flush()
        lock.release()
    for i in range(iterations):
        data = inConn.recv()
        print(f"{i}: {data}")
        output.write(f"{i}: {data}")
        output.flush()
        lock.acquire()
        outConn.send(data)
        output.write(str(data))
        output.flush()
        lock.release()
    if not initial_data:
        data = inConn.recv()
        print(f"{i}: {data}")
        output.write(str(data))
        output.flush()

def producer(conn, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        conn.send(i)
        print(f"{process.name} sent {i}")
        output.write(str(i))
        output.flush()

def doubleProducer(conn1, conn2, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        conn1.send(i)
        print(f"{process.name} sent {i}")
        output.write(str(i))
        conn2.send(i)
        output.write(str(i))
        output.flush()

def doubleSendProducer(conn, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        conn.send(i)
        output.write(str(i))
        output.flush()
        conn.send("hello")
        output.write("hello")
        output.flush()

def consumer(conn, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, 'w')
    for i in range(iterations):
        data = conn.recv()
        print(f"{data}")
        output.write(str(data))
        output.flush()

def doubleRecvDoubleConsumer(conn1, conn2, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        data1 = conn1.recv()
        data2 = conn2.recv()
        data3 = conn1.recv()
        data4 = conn2.recv()

        if data3 == "hello" and data4 == "hello":
            print(f"{data1}-{data2}")
        output.write(f"{data1}-{data2}-{data3}-{data4}")
        output.flush()


def doubleSendDoubleProducer(conn1, conn2, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        conn1.send(i)
        conn2.send("hello")
        conn1.send(i)
        conn2.send("hello")

        output.write(f"{i}-hello-{i}-hello")
        output.flush()

def doubleConsumer(conn1, conn2, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        data1 = conn1.recv()
        data2 = conn2.recv()
        print(f"{data1}-{data2}")
        output.write(f"{data1}-{data2}")
        output.flush()

def transmitter(conn1, conn2, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        data = conn1.recv()
        conn2.send(data)
        output.write(f"{data}")
        output.flush()

def doubleInTransmitter(conn1, conn2, conn3, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        data1 = conn1.recv()
        data2 = conn2.recv()
        dataout = str(data1) + " + " + str(data2) 
        conn3.send(dataout)
        output.write(str(dataout))
        output.flush()

def doubleOutTransmitter(conn1, conn2, conn3, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        data = conn1.recv()
        conn2.send(data)
        conn3.send(data)
        output.write(str(data))
        output.flush()

def lockedProducer(conn, lock, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        lock.acquire()
        conn.send(i)
        output.write(str(i))
        output.flush()
        lock.release()

def selectSharedLockTwoLockedProducersTwoConsumers(conn1, conn2, conn3, conn4, lock1, lock2, vs, iterations, outputdir="vtest/"):
    for i in range(iterations*2):
        data1 = None
        data2 = None
        (inputs, _, _) = vs.select([conn1, conn2], [], [])
        if conn1 in inputs and conn2 in inputs:
            num = random.randint(0, 1)
            if num == 0:
                data1 = conn1.recv()
            else:
                data2 = conn2.recv()
        elif conn1 in inputs:
            data1 = conn1.recv()
        elif conn2 in inputs:
            data2 = conn2.recv()
        
        if data1 != None:
            lock1.acquire()
            conn3.send(data1)
            lock1.release()
        elif data2 != None:
            lock2.acquire()
            conn4.send(data2)
            lock2.release()

def selectSharedLockTwoLockedProducersTwoConsumers2(conn1, conn2, conn3, conn4, lock1, lock2, iterations, outputdir="vtest/"):
    for i in range(iterations*2):
        data1 = None
        data2 = None
        (inputs, _, _) = VSelect.select([conn1, conn2], [], [])
        if conn1 in inputs and conn2 in inputs:
            num = random.randint(0, 1)
            if num == 0:
                data1 = conn1.recv()
            else:
                data2 = conn2.recv()
        elif conn1 in inputs:
            data1 = conn1.recv()
        elif conn2 in inputs:
            data2 = conn2.recv()
        
        if data1 != None:
            lock1.acquire()
            conn3.send(data1)
            lock1.release()
        elif data2 != None:
            lock2.acquire()
            conn4.send(data2)
            lock2.release()

def veryLockedProducer(locks, conn, iterations):
    for i in range(iterations):
        for lock in locks:
            lock.acquire()
        conn.send(i)
        for lock in locks:
             lock.release()

def veryLockedProducer2(lock1, lock2, lock3, conn, iterations):
    for i in range(iterations):
        lock1.acquire()
        lock2.acquire()
        lock1.release()
        lock3.acquire()
        conn.send(i)
        lock2.release()
        lock3.release()

def nestedLockedSelect(lock1, lock2, lock3, conn1, conn2, conn3, iterations):
    for i in range(iterations):
        lock1.acquire()
        lock2.acquire()
        inputs,_,_ = VSelect.select([conn1, conn2, conn3], [], [])
        print("inputs:", inputs)
        lock3.acquire()
        lock1.release()
        lock2.release()        
        for input in inputs:
            input.recv()
        lock3.release()  
    
def nestedLocksSelectTest(iterations):

    lock1 = VLock(multiprocessing.Lock())
    lock2 = VLock(multiprocessing.Lock())
    lock3 = VLock(multiprocessing.Lock())

    locks = [lock1, lock2, lock3] 

    p1, c1 = VPipe()
    p2, c2 = VPipe()
    p3, c3 = VPipe()

    channels = [p1, c1, p2, c2, p3, c3]

    processes = [
            VProcess(
                    target=nestedLockedSelect, 
                    args=(lock1, lock2, lock3, c1, c2, c3, iterations + 1),
                    name="nls1"
                    ),
            #VProcess(
            #        target=nestedLockedSelect, 
            #        args=(lock1, lock2, lock3, c1, c2, c3, iterations),
            #        name="nls2"
            #        ),
            VProcess(
                    target=producer, 
                    args=(p1, iterations), 
                    name="p1"
                    ),
            VProcess(
                    target=producer, 
                    args=(p2, iterations), 
                    name="p2"
                    ),
            VProcess(
                    target=producer, 
                    args=(p3, iterations), 
                    name="p3"
                    )
                 ]
    
    return processes, channels, locks



def nestedLocksTest(iterations):
    lock1 = VLock(multiprocessing.Lock())
    lock2 = VLock(multiprocessing.Lock())
    lock3 = VLock(multiprocessing.Lock())
    lock4 = VLock(multiprocessing.Lock())
    

    locks = [lock1, lock2, lock3, lock4] 

    p1, c1 = VPipe()
    p2, c2 = VPipe()
    p3, c3 = VPipe()
    p4, c4 = VPipe()

    channels = [p1, c1, p2, c2, p3, c3, p4, c4]

    processes = [
            VProcess(
                    target=veryLockedProducer, 
                    args=(locks, p1, iterations), 
                    name="lp1"
                    ),
            VProcess(
                    target=veryLockedProducer, 
                    args=(locks, p2, iterations), 
                    name="lp2"
                    ),
            VProcess(
                    target=veryLockedProducer, 
                    args=(locks, p3, iterations), 
                    name="lp3"
                    ),
            VProcess(
                    target=veryLockedProducer, 
                    args=(locks, p4, iterations), 
                    name="lp4"
                    ),
            VProcess(
                    target=consumer, 
                    args=(c1, iterations), 
                    name="c1"
                    ),
            VProcess(
                    target=consumer, 
                    args=(c2, iterations), 
                    name="c2"
                    ),
            VProcess(
                    target=consumer, 
                    args=(c3, iterations), 
                    name="c3"
                    ),
            VProcess(
                    target=consumer, 
                    args=(c4, iterations), 
                    name="c4"
                    )
                 ]
    
    return processes, channels, locks

def nestedLocksTest2(iterations):

    lock1 = VLock(multiprocessing.Lock())
    lock2 = VLock(multiprocessing.Lock())
    lock3 = VLock(multiprocessing.Lock())
    #lock4 = VLock(multiprocessing.Lock())
    

    locks = [lock1, lock2, lock3] 

    p1, c1 = VPipe()
    p2, c2 = VPipe()
    p3, c3 = VPipe()
    p4, c4 = VPipe()

    channels = [p1, c1, p2, c2, p3, c3, p4, c4]

    processes = [
            VProcess(
                    target=veryLockedProducer2, 
                    args=(lock1, lock2, lock3, p1, iterations), 
                    name="lp1"
                    ),
            VProcess(
                    target=veryLockedProducer2, 
                    args=(lock1, lock2, lock3, p2, iterations), 
                    name="lp2"
                    ),
            VProcess(
                    target=veryLockedProducer2, 
                    args=(lock1, lock2, lock3, p3, iterations), 
                    name="lp3"
                    ),
            VProcess(
                    target=veryLockedProducer2, 
                    args=(lock1, lock2, lock3, p4, iterations), 
                    name="lp4"
                    ),
            VProcess(
                    target=consumer, 
                    args=(c1, iterations), 
                    name="c1"
                    ),
            VProcess(
                    target=consumer, 
                    args=(c2, iterations), 
                    name="c2"
                    ),
            VProcess(
                    target=consumer, 
                    args=(c3, iterations), 
                    name="c3"
                    ),
            VProcess(
                    target=consumer, 
                    args=(c4, iterations), 
                    name="c4"
                    )
                 ]
    
    return processes, channels, locks



def selectVariableProducersConsumers1(in_connections, out_connections, vselect, num, iterations):
    for i in range(num * iterations):
        (inputs, _, _) = vselect.select(in_connections, [], [])
        for i, connection in enumerate(in_connections):
          if connection in inputs:
              data = connection.recv()
              out_connections[i].send(data)

def selectVariableProducersConsumers2(in_connections, out_connections, vselect):
    sendIndex = 0
    maxIndex = len(out_connections)
    for i in range(30):
        (inputs, _, _) = vselect.select(in_connections, [], [])
        index = random.randint(0, len(inputs) - 1)
        data = inputs[index].recv()
        out_connections[sendIndex].send(data)
        sendIndex = (sendIndex + 1) % maxIndex
        print(f"Sending to: {sendIndex}")

# Tests

def transmitterTest(iterations, outputdir="vtest/"):
    pipe_1_in, pipe_1_out  = VPipe()
    pipe_2_in, pipe_2_out  = VPipe()

    processes = [
        VProcess(
            target=producer, 
            args=(pipe_1_in, iterations, outputdir),
            name="p1"
        ),
        VProcess(
            target=transmitter, 
            args=(pipe_1_out, pipe_2_in, iterations, outputdir),
            name="t1"
        ),
        VProcess(
            target=consumer, 
            args=(pipe_2_out, iterations, outputdir),
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

def doubleInTransmitterTest(iterations, outputdir="vtest/"):
    pipe_1_in, pipe_1_out  = VPipe()
    pipe_2_in, pipe_2_out  = VPipe()
    pipe_3_in, pipe_3_out  = VPipe()

    processes = [
        VProcess(
            target=producer, 
            args=(pipe_1_in, iterations, outputdir),
            name="p2"
        ),
        VProcess(
            target=producer, 
            args=(pipe_2_in, iterations, outputdir),
            name="p3"
        ),
        VProcess(
            target=doubleInTransmitter, 
            args=(pipe_1_out, pipe_2_out, pipe_3_in, iterations, outputdir),
            name="t2"
        ),
        VProcess(
            target=consumer, 
            args=(pipe_3_out, iterations, outputdir),
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

def doubleOutTransmitterTest(iterations, outputdir="vtest/"):
    pipe_1_in, pipe_1_out  = VPipe()
    pipe_2_in, pipe_2_out  = VPipe()
    pipe_3_in, pipe_3_out  = VPipe()

    processes = [
        VProcess(
            target=producer, 
            args=(pipe_1_in, iterations, outputdir),
            name="p4"
        ),
        VProcess(
            target=doubleOutTransmitter, 
            args=(pipe_1_out, pipe_2_in, pipe_3_in, iterations, outputdir),
            name="t3"
        ),
        VProcess(
            target=consumer, 
            args=(pipe_2_out, iterations, outputdir),
            name="c3"
        ),
        VProcess(
            target=consumer, 
            args=(pipe_3_out, iterations, outputdir),
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

def doubleOutTransmitterTransmitterTest(iterations, outputdir="vtest/"):
    pipe_1_in, pipe_1_out  = VPipe()
    pipe_2_in, pipe_2_out  = VPipe()
    pipe_3_in, pipe_3_out  = VPipe()
    pipe_4_in, pipe_4_out  = VPipe()

    processes = [
        VProcess(
            target=producer, 
            args=(pipe_1_in, iterations, outputdir),
            name="p4"
        ),
        VProcess(
            target=doubleOutTransmitter, 
            args=(pipe_1_out, pipe_2_in, pipe_3_in, iterations, outputdir),
            name="t3"
        ),
        VProcess(
            target=transmitter,
            args=(pipe_2_out, pipe_4_in, iterations, outputdir),
            name="t4"
        ),
        VProcess(
            target=consumer, 
            args=(pipe_4_out, iterations, outputdir),
            name="c3"
        ),
        VProcess(
            target=consumer, 
            args=(pipe_3_out, iterations, outputdir),
            name="c4"
        )
    ]

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

    return processes, channels

def pingPongTest(iterations, outputdir="vtest/"):
    pipe_1_w, pipe_1_r  = VPipe()
    pipe_2_w, pipe_2_r  = VPipe()
    processes = [
        VProcess(
            target=pingpong, 
            args=(0, pipe_1_w, pipe_2_r, iterations, outputdir, "hello"),
            name="Albert"
        ),
        VProcess(
            target=pingpong, 
            args=(1, pipe_2_w, pipe_1_r, iterations, outputdir),
            name="Bertha"
        )
    ]
    channels = [
        pipe_1_w,
        pipe_1_r,
        pipe_2_w,
        pipe_2_r
    ]
    return processes, channels

def twoDoubleProducerDoubleSendDoubleConsumerDoubleRecvTest(iterations, outputdir="vtest/"):

    p1, c1 = VPipe()
    p2, c2 = VPipe()
    p3, c3 = VPipe()
    p4, c4 = VPipe()

    processes = [
        VProcess(
            target=doubleSendDoubleProducer,
            args=(p1, p2, iterations, outputdir),
            name="p1"
        ),
        VProcess(
            target=doubleSendDoubleProducer,
            args=(p3, p4, iterations, outputdir),
            name="p2"
        ),
        VProcess(
            target=doubleRecvDoubleConsumer,
            args=(c1, c4, iterations, outputdir),
            name="c1"
        ),
        VProcess(
            target=doubleRecvDoubleConsumer,
            args=(c3, c2, iterations, outputdir),
            name="c2"
        )
    ]

    channels = [c1, p1, c2, p2, c3, p3, c4, p4]
    return processes, channels



def producerDoubleConsumerTest(iterations, outputdir="vtest/"):
    q11, q12 = VPipe()
    q21, q22 = VPipe()

    processes = [
        VProcess(
            target=producer, 
            args=(q11, iterations, outputdir),
            name="p5"
        ),
        VProcess(
            target=producer, 
            args=(q21, iterations, outputdir),
            name="p6"
        ),
        VProcess(
            target=doubleConsumer, 
            args=(q12, q22, iterations, outputdir),
            name="c5"
        )
    ]
    channels = [q11, q12, q21, q22]
    return processes, channels

def producerConsumerTest(iterations, outputdir="vtest/"):
    q11, q12 = VPipe()

    processes = [
        VProcess(
            target=producer, 
            args=(q11, iterations, outputdir),
            name="p1"
        ),
        VProcess(
            target=consumer, 
            args=(q12, iterations, outputdir),
            name="c1"
        )
    ]
    channels = [q11, q12]
    return processes, channels

def twoXProducerConsumerTest(iterations, outputdir="vtest/"):
    p1, c1 = VPipe()
    p2, c2 = VPipe()

    processes = [
        VProcess(
            target=doubleProducer, 
            args=(p1, p2, iterations, outputdir),
            name="p1"
        ),
        VProcess(
            target=doubleConsumer, 
            args=(c1, c2, iterations, outputdir),
            name="c1"
        )
    ]
    channels = [p1, p2, c1, c2]
    return processes, channels

def doubleProducerConsumerTest(iterations, outputdir="vtest/"):
    q11, q12 = VPipe()
    q21, q22 = VPipe()

    processes = [
        VProcess(
            target=producer, 
            args=(q11, iterations, outputdir),
            name="p7"
        ),
        VProcess(
            target=producer, 
            args=(q21, iterations, outputdir),
            name="p8"
        ),
        VProcess(
            target=consumer, 
            args=(q12, iterations, outputdir),
            name="c7"
        ),
        VProcess(
            target=consumer, 
            args=(q22, iterations, outputdir),
            name="c8"
        )
    ]
    channels = [q11, q12, q21, q22]
    return processes, channels


def oneLockLockedProducerConsumerTest(iterations, outputdir="vtest/"):

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
                args=(p1, vlock1, iterations, outputdir),
                name="p1"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p2, vlock2, iterations, outputdir),
                name="p2"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p3, vlock3, iterations, outputdir),
                name="p3"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p4, vlock4, iterations, outputdir),
                name="p4"
            ),
            VProcess(
                target=consumer, 
                args=(c1, iterations, outputdir),
                name="c1"
            ),
            VProcess(
                target=consumer, 
                args=(c2, iterations, outputdir),
                name="c2"
            ),
            VProcess(
                target=consumer, 
                args=(c3, iterations, outputdir),
                name="c3"
            ),
            VProcess(
                target=consumer, 
                args=(c4, iterations, outputdir),
                name="c4"
            )
    ]

    channels = [p1, c1, p2, c2, p3, c3, p4, c4]
    locks = [vlock1, vlock2, vlock3, vlock4]

    return processes, channels, locks

def twoLockLockedProducerConsumerTest(iterations, outputdir="vtest/"):

    lock1 = multiprocessing.Lock()
    lock2 = multiprocessing.Lock()

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
                args=(p1, vlock1, iterations, outputdir),
                name="p1"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p2, vlock2, iterations, outputdir),
                name="p2"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p3, vlock3, iterations, outputdir),
                name="p3"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p4, vlock4, iterations, outputdir),
                name="p4"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p5, vlock5, iterations, outputdir),
                name="p5"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p6, vlock6, iterations, outputdir),
                name="p6"
            ),
            VProcess(
                target=consumer, 
                args=(c1, iterations, outputdir),
                name="c1"
            ),
            VProcess(
                target=consumer, 
                args=(c2, iterations, outputdir),
                name="c2"
            ),
            VProcess(
                target=consumer, 
                args=(c3, iterations, outputdir),
                name="c3"
            ),
            VProcess(
                target=consumer, 
                args=(c4, iterations, outputdir),
                name="c4"
            ),
            VProcess(
                target=consumer, 
                args=(c5, iterations, outputdir),
                name="c5"
            ),
            VProcess(
                target=consumer, 
                args=(c6, iterations, outputdir),
                name="c6"
            )
    ]

    channels = [p1, c1, p2, c2, p3, c3, p4, c4, p5, c5, p6, c6]
    locks = [vlock1, vlock2, vlock3, vlock4, vlock5, vlock6]

    return processes, channels, locks

def lockedPingPongTest(iterations, outputdir="vtest/"):
    lock = multiprocessing.Lock()
    
    vlock1 = VLock(lock)
    vlock2 = VLock(lock)
    
    pipe_1_in, pipe_1_out  = VPipe()
    pipe_2_in, pipe_2_out  = VPipe()
    
    
    processes = [
        VProcess(
            target=lockedPingPong, 
            args=(0, vlock1, pipe_1_in, pipe_2_out, iterations, outputdir, "hello"),
            name="Albert"
        ),
        VProcess(
            target=lockedPingPong, 
            args=(1, vlock2, pipe_2_in, pipe_1_out, iterations, outputdir),
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

def lockedMultiplePingPongTest(iterations, outputdir="vtest/"):
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
            args=(0, vlock1, pipe_1_in, pipe_2_out, iterations, outputdir,"hello"),
            name="Albert"
        ),
        VProcess(
            target=lockedPingPong, 
            args=(1, vlock2, pipe_2_in, pipe_1_out, iterations, outputdir),
            name="Bertha"
        ),
        VProcess(
            target=lockedPingPong, 
            args=(0, vlock3, pipe_3_in, pipe_4_out, iterations, outputdir,"hello"),
            name="Cindy"
        ),
        VProcess(
            target=lockedPingPong, 
            args=(1, vlock4, pipe_4_in, pipe_3_out, iterations, outputdir),
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

def selectSharedLockTwoLockedProducersTwoConsumersTest(iterations, outputdir="vtest/"):
    
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
                args=(p1,vlock1, iterations, outputdir),
                name="p1"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p2,vlock2, iterations, outputdir),
                name="p2"
            ),
            VProcess(
                target=selectSharedLockTwoLockedProducersTwoConsumers, 
                args=(c1, c2, p3, p4, vlock3, vlock4, vs, iterations, outputdir),
                name="DS"
            ),
            VProcess(
                target=consumer, 
                args=(c3, iterations, outputdir),
                name="c1"
            ),
            VProcess(
                target=consumer, 
                args=(c4, iterations, outputdir),
                name="c2"
            )]

    locks = [vlock1, vlock2, vlock3, vlock4]
    connections = [p1, c1, p2, c2, p3, c3, p4, c4]
    selects = [vs]

    return processes, connections, locks, selects

def selectSharedLockTwoLockedProducersTwoConsumersTest2(iterations, outputdir="vtest/"):
    
    #vs = VSelect(name="vselector")

    lock1 = multiprocessing.Lock()
    lock2 = multiprocessing.Lock()

    vlock1 = VLock(lock1)
    vlock2 = VLock(lock2)
    #vlock3 = VLock(lock1)
    #vlock4 = VLock(lock2)


    p1, c1 = VPipe()
    p2, c2 = VPipe()
    p3, c3 = VPipe()
    p4, c4 = VPipe()

    processes = [
            VProcess(
                target=lockedProducer, 
                args=(p1,vlock1, iterations, outputdir),
                name="p1"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p2,vlock2, iterations, outputdir),
                name="p2"
            ),
            VProcess(
                target=selectSharedLockTwoLockedProducersTwoConsumers2, 
                args=(c1, c2, p3, p4, vlock1, vlock2, iterations, outputdir),
                name="DS"
            ),
            VProcess(
                target=consumer, 
                args=(c3, iterations, outputdir),
                name="c1"
            ),
            VProcess(
                target=consumer, 
                args=(c4, iterations, outputdir),
                name="c2"
            )]

    locks = [vlock1, vlock2]
    #locks = [vlock1, vlock2, vlock3, vlock4]
    connections = [p1, c1, p2, c2, p3, c3, p4, c4]
    #selects = [vs]

    return processes, connections, locks


def complexTest(iterations, outputdir="vtest/"):
    
    vs1 = VSelect(name="s1")
    vs2 = VSelect(name="s2")
    vs3 = VSelect(name="s3")

    lock1 = multiprocessing.Lock()
    lock2 = multiprocessing.Lock()
    lock3 = multiprocessing.Lock()
    lock4 = multiprocessing.Lock()
    lock5 = multiprocessing.Lock()

    vlock11 = VLock(lock1)
    vlock12 = VLock(lock1)
    vlock21 = VLock(lock2)
    vlock22 = VLock(lock2)
    vlock31 = VLock(lock3)
    vlock32 = VLock(lock3)
    vlock41 = VLock(lock4)
    vlock42 = VLock(lock4)
    vlock51 = VLock(lock5)
    vlock52 = VLock(lock5)


    p1, c1 = VPipe()
    p2, c2 = VPipe()
    p3, c3 = VPipe()
    p4, c4 = VPipe()
    p5, c5 = VPipe()
    p6, c6 = VPipe()
    p7, c7 = VPipe()
    p8, c8 = VPipe()
    p9, c9 = VPipe()
    p10, c10 = VPipe()

    processes = [
            VProcess(
                target=lockedProducer, 
                args=(p1,vlock21, iterations, outputdir),
                name="p1"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p2,vlock22, iterations, outputdir),
                name="p2"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p3,vlock31, iterations, outputdir),
                name="p3"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p4,vlock32, iterations, outputdir),
                name="p4"
            ),
            VProcess(
                target=selectSharedLockTwoLockedProducersTwoConsumers, 
                args=(c1, c2, p5, p6, vlock11, vlock51, vs1, iterations),
                name="DS1"
            ),
            VProcess(
                target=selectSharedLockTwoLockedProducersTwoConsumers, 
                args=(c3, c4, p7, p8, vlock41, vlock52, vs2, iterations),
                name="DS2"
            ),
            VProcess(
                target=selectSharedLockTwoLockedProducersTwoConsumers, 
                args=(c6, c7, p9, p10, vlock12, vlock42, vs3, iterations),
                name="DS3"
            ),
            VProcess(
                target=consumer, 
                args=(c5, iterations, outputdir),
                name="c1"
            ),
            VProcess(
                target=consumer, 
                args=(c9, iterations, outputdir),
                name="c2"
            ),
            VProcess(
                target=consumer, 
                args=(c10, iterations, outputdir),
                name="c3"
            ),
            VProcess(
                target=consumer, 
                args=(c8, iterations, outputdir),
                name="c4"
            )
            ]

    locks = [vlock11, vlock12, vlock21, vlock22, vlock31, vlock32, vlock41, vlock42, vlock51, vlock52]
    connections = [p1, c1, p2, c2, p3, c3, p4, c4, p5, c5, p6, c6, p7, c7, p8, c8, p9, c9, p10, c10]
    selects = [vs1, vs2, vs3]

    return processes, connections, locks, selects

def complexTest2(iterations, outputdir="vtest/"):
    
    vs1 = VSelect(name="s1")
    vs2 = VSelect(name="s2")
    vs3 = VSelect(name="s3")

    lock1 = multiprocessing.Lock()
    lock2 = multiprocessing.Lock()
    lock3 = multiprocessing.Lock()
    lock4 = multiprocessing.Lock()
    lock5 = multiprocessing.Lock()

    vlock11 = VLock(lock1)
    #vlock12 = VLock(lock1)
    vlock21 = VLock(lock2)
    #vlock22 = VLock(lock2)
    vlock31 = VLock(lock3)
    #vlock32 = VLock(lock3)
    vlock41 = VLock(lock4)
    #vlock42 = VLock(lock4)
    vlock51 = VLock(lock5)
    #vlock52 = VLock(lock5)


    p1, c1 = VPipe()
    p2, c2 = VPipe()
    p3, c3 = VPipe()
    p4, c4 = VPipe()
    p5, c5 = VPipe()
    p6, c6 = VPipe()
    p7, c7 = VPipe()
    p8, c8 = VPipe()
    p9, c9 = VPipe()
    p10, c10 = VPipe()

    processes = [
            VProcess(
                target=lockedProducer, 
                args=(p1,vlock21, iterations, outputdir),
                name="p1"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p2,vlock21, iterations, outputdir),
                name="p2"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p3,vlock31, iterations, outputdir),
                name="p3"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p4,vlock31, iterations, outputdir),
                name="p4"
            ),
            VProcess(
                target=selectSharedLockTwoLockedProducersTwoConsumers2, 
                args=(c1, c2, p5, p6, vlock11, vlock51, iterations),
                name="DS1"
            ),
            VProcess(
                target=selectSharedLockTwoLockedProducersTwoConsumers2, 
                args=(c3, c4, p7, p8, vlock41, vlock51, iterations),
                name="DS2"
            ),
            VProcess(
                target=selectSharedLockTwoLockedProducersTwoConsumers2, 
                args=(c6, c7, p9, p10, vlock11, vlock41, iterations),
                name="DS3"
            ),
            VProcess(
                target=consumer, 
                args=(c5, iterations, outputdir),
                name="c1"
            ),
            VProcess(
                target=consumer, 
                args=(c9, iterations, outputdir),
                name="c2"
            ),
            VProcess(
                target=consumer, 
                args=(c10, iterations, outputdir),
                name="c3"
            ),
            VProcess(
                target=consumer, 
                args=(c8, iterations, outputdir),
                name="c4"
            )
            ]

    locks = [vlock11, vlock21, vlock31, vlock41, vlock51]
    connections = [p1, c1, p2, c2, p3, c3, p4, c4, p5, c5, p6, c6, p7, c7, p8, c8, p9, c9, p10, c10]
    #selects = [vs1, vs2, vs3]

    return processes, connections, locks, selects





def selectMultipleLockedProducersConsumersTest(iterations, outputdir="vtest/"):
    
    vs = VSelect(name="vselector")

    lock1 = multiprocessing.Lock()

    vlock1 = VLock(lock1)
    vlock2 = VLock(lock1)
    vlock3 = VLock(lock1)
    vlock4 = VLock(lock1)
    vlock5 = VLock(lock1)
    vlock6 = VLock(lock1)

    p1, c1 = VPipe()
    p2, c2 = VPipe()
    p3, c3 = VPipe()
    p4, c4 = VPipe()
    p5, c5 = VPipe()
    p6, c6 = VPipe()
    p7, c7 = VPipe()
    p8, c8 = VPipe()
    p9, c9 = VPipe()
    p10, c10 = VPipe()
    p11, c11 = VPipe()
    p12, c12 = VPipe()

    in_connections = [c1, c2, c3, c4, c5, c6]
    out_connections = [p7, p8, p9, p10, p11, p12]

    processes = [
            VProcess(
                target=lockedProducer, 
                args=(p1, vlock1, iterations, outputdir),
                name="p1"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p2, vlock2, iterations, outputdir),
                name="p2"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p3, vlock3, iterations, outputdir),
                name="p3"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p4, vlock4, iterations, outputdir),
                name="p4"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p5, vlock5, iterations, outputdir),
                name="p5"
            ),
            VProcess(
                target=lockedProducer, 
                args=(p6, vlock6, iterations, outputdir),
                name="p6"
            ),
            VProcess(
                target=selectVariableProducersConsumers1, 
                args=(in_connections, out_connections, vs, 6, iterations),
                name="DS"
            ),
            VProcess(
                target=consumer, 
                args=(c7, iterations, outputdir),
                name="c7"
            ),
            VProcess(
                target=consumer, 
                args=(c8, iterations, outputdir),
                name="c8"
            ),
            VProcess(
                target=consumer, 
                args=(c9, iterations, outputdir),
                name="c9"
            ),
            VProcess(
                target=consumer, 
                args=(c10, iterations, outputdir),
                name="c10"
            ),
            VProcess(
                target=consumer, 
                args=(c11, iterations, outputdir),
                name="c11"
            ),
            VProcess(
                target=consumer, 
                args=(c12, iterations, outputdir),
                name="c12"
            )]

    locks = [vlock1, vlock2, vlock3, vlock4, vlock5, vlock6]
    connections = [p1, c1, p2, c2, p3, c3, p4, c4, p5, c5, p6, c6, p7, c7, p8, c8, p9, c9, p10, c10, p11, c11, p12, c12]
    selects = [vs]

    return processes, connections, locks, selects

def selectMultipleProducersConsumersTest(iterations, outputdir="vtest/"):
    
    vs = VSelect(name="vselector")

    lock1 = multiprocessing.Lock()

    vlock1 = VLock(lock1)
    vlock2 = VLock(lock1)
    vlock3 = VLock(lock1)
    vlock4 = VLock(lock1)
    vlock5 = VLock(lock1)
    vlock6 = VLock(lock1)

    p1, c1 = VPipe()
    p2, c2 = VPipe()
    p3, c3 = VPipe()
    p4, c4 = VPipe()
    p5, c5 = VPipe()
    p6, c6 = VPipe()
    p7, c7 = VPipe()
    p8, c8 = VPipe()
    p9, c9 = VPipe()
    p10, c10 = VPipe()
    p11, c11 = VPipe()
    p12, c12 = VPipe()

    in_connections = [c1, c2, c3, c4, c5, c6]
    out_connections = [p7, p8, p9, p10, p11, p12]

    processes = [
            VProcess(
                target=producer, 
                args=(p1, iterations, outputdir),
                name="p1"
            ),
            VProcess(
                target=producer, 
                args=(p2, iterations, outputdir),
                name="p2"
            ),
            VProcess(
                target=producer, 
                args=(p3, iterations, outputdir),
                name="p3"
            ),
            VProcess(
                target=producer, 
                args=(p4, iterations, outputdir),
                name="p4"
            ),
            VProcess(
                target=producer, 
                args=(p5, iterations, outputdir),
                name="p5"
            ),
            VProcess(
                target=producer, 
                args=(p6, iterations, outputdir),
                name="p6"
            ),
            VProcess(
                target=selectVariableProducersConsumers1, 
                args=(in_connections, out_connections, vs, 6, iterations),
                name="DS"
            ),
            VProcess(
                target=consumer, 
                args=(c7, iterations, outputdir),
                name="c7"
            ),
            VProcess(
                target=consumer, 
                args=(c8, iterations, outputdir),
                name="c8"
            ),
            VProcess(
                target=consumer, 
                args=(c9, iterations, outputdir),
                name="c9"
            ),
            VProcess(
                target=consumer, 
                args=(c10, iterations, outputdir),
                name="c10"
            ),
            VProcess(
                target=consumer, 
                args=(c11, iterations, outputdir),
                name="c11"
            ),
            VProcess(
                target=consumer, 
                args=(c12, iterations, outputdir),
                name="c12"
            )]

    locks = [vlock1, vlock2, vlock3, vlock4, vlock5, vlock6]
    connections = [p1, c1, p2, c2, p3, c3, p4, c4, p5, c5, p6, c6, p7, c7, p8, c8, p9, c9, p10, c10, p11, c11, p12, c12]
    selects = [vs]

    return processes, connections, selects

def multipleSimpleConnectionsTest(iterations, outputdir="vtest/"):
    p = []
    c = []

    processes, channels = pingPongTest(iterations, outputdir)
    p.extend(processes)
    c.extend(channels)
    processes, channels = producerDoubleConsumerTest(iterations, outputdir)
    p.extend(processes)
    c.extend(channels)
    processes, channels = doubleProducerConsumerTest(iterations, outputdir)
    p.extend(processes)
    c.extend(channels)
    processes, channels = transmitterTest(iterations, outputdir)
    p.extend(processes)
    c.extend(channels)
    processes, channels = doubleInTransmitterTest(iterations, outputdir)
    p.extend(processes)
    c.extend(channels)
    processes, channels = doubleOutTransmitterTest(iterations, outputdir)
    p.extend(processes)
    c.extend(channels)
    processes, channels = p, c
    
    return processes, channels

outputdir = "vtest/"
if os.path.exists(outputdir):
    shutil.rmtree(outputdir)    
os.mkdir(outputdir)

locks = []
selects = []

#processes, channels, locks = nestedLocksTest(4)
processes, channels, locks = nestedLocksTest2(4)
#processes, channels, locks = nestedLocksSelectTest(2)

#Test 1
#processes, channels = multipleSimpleConnectionsTest(5, outputdir)

# Test 2
#processes, channels, locks = lockedMultiplePingPongTest(100, outputdir)

# Test 3
#processes, channels = twoDoubleProducerDoubleSendDoubleConsumerDoubleRecvTest(5, outputdir)

# Test 4
#processes, channels, locks = twoLockLockedProducerConsumerTest(10, outputdir)

# Test 5
#processes, channels, locks = selectSharedLockTwoLockedProducersTwoConsumersTest2(3, outputdir)

# Test 6
#processes, channels, locks, selects = selectMultipleLockedProducersConsumersTest(50, outputdir) # This one will end in an error from the manager. But writes the correct output.

# Test 7
#processes, channels, locks, selects = complexTest2(5, outputdir)

vmanager = VManager(processes, channels, locks, selects, outputFormat="png", interactiveLocks=False, draw=True, terminateProcesses=True)
#
vmanager.init_graph()
vmanager.start()

#vmanager.stepwiseTicks(processes) # uncomment this line and comment the one below for stepwise execution, if draw is disabled, you can choose when to draw the graph by typing in 'd'
vmanager.runTicksToEnd(processes)
#VSelect.dict = vmanager.processToManagerSendConn
#VSelect.string = "hej hej"
#VSelect.test2()