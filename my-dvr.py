#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: Devarsh Thaker
"""

# start off by necessary imports
from threading import Thread
import socket
from copy import deepcopy

# socket for each node will be global as it needs to be accessed everywhere
socket_for_node = {}

# keep track of total nodes here 
round = 0

# infinity will be represented as a float, for the nodes whos DV not yet calculated
# DV
inf = float('inf')

# every round, the order goes A->B->C->D->E->A...
next_node = {
    "A": "B",
    "B": "C",
    "C": "D",
    "D": "E",
    "E": "A"
}



# does the dv need to be updated is checked here
# if not changed then no update, if changed then update
def isNotChanged(matrixA, matrixB):
    #if any 1 of matrix is none then return false
    if matrixA is None and not matrixB is None:
        return False

    if matrixA is None and matrixB is None:
        return True

    if matrixB is None:
        return False

    #compare each value for the DV and return false
    for k in matrixA.keys():
        if k not in matrixB:
            return False

        if len(matrixA[k]) != len(matrixB[k]):
            return False

        for i in range(len(matrixA[k])):
            if matrixB[k][i] != matrixA[k][i]:
                return False
    
    # default return is true
    return True


# The thread representing the node and execute the DV
class NodeExecute(Thread):
    def __init__(self, threadID, name, neighbors):
        Thread.__init__(self)

        self.threadID = threadID
        self.name = name

        # Store the neighbors names as list and distance to each as dict
        self.neighbors = neighbors.keys()
        self.distances = neighbors

        # Set up the server socket, threadid is 3001 order and local host
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('localhost', threadID))
        s.listen(5)

        self.serverSocket = s

        # as E is the last one, this is only for E node
        self.lastRoundChangedTotal = None

        # dv table is set here, used a dictionary
        dv_table = {}

        # Add its own distance vector
        dv_table[name] = []
        for node in socket_for_node.keys():
            if self.name == node:
                dv_table[name].append(0.0)
            elif node in self.neighbors:
                # Distance between this node and its neighbor
                dv_table[name].append(self.distances[node])
            else:
                # inf represents infinite distance
                dv_table[name].append(inf)

        # Add the neighbors distance vectors
        for neighbor in self.neighbors:
            dv_table[neighbor] = []

            for _ in range(len(socket_for_node.keys())):
                # We have no information on the neighbors DV yet
                dv_table[neighbor].append(inf)

        self.dvMatrix = dv_table
        self.lastMatrix = None

        # Initialize the round at which the last DV matrix was stored
        self.lastChangedRound = -1

    # here the DVtable is updated, using bellman ford eq
    def updateDVTable(self, data, neighbor):
        # update the table accordingly
        print("Updating DV matrix at node %s" % self.name)
        self.dvMatrix[neighbor] = data

        #for each new value calculate minimum to node
        for i in range(len(socket_for_node.keys())):
            minDist = self.dvMatrix[self.name][i]

            for neighbor in self.neighbors:
                minDist = min(minDist, self.distances[neighbor] + self.dvMatrix[neighbor][i])

            self.dvMatrix[self.name][i] = minDist


    #start up here
    def run(self):

        # use the global variable round
        global round

        # for the node this is the loop
        while True:
            # setup connection to accept the incoming message
            conn, addr = self.serverSocket.accept()

            # as long as message is received
            while True:
                try:
                    # get the data
                    data = conn.recvfrom(1024)
                except ConnectionResetError as e:
                    # connection reset error
                    print("Connetion problem for %s " % self.name)
                    break

                # if no data has been received
                if not data:
                    print("Data not received %s" % self.name)
                    continue
                #data has been received but as bytes so decode
                else:
                    data = data[0].decode('utf-8')
                    if len(data) == 0:
                        break

                # check if this the last one, print out and close the connections
                if 'end' in data:

                    # now no new updates are left so print
                    print("Node %s DV = %s" % (self.name, self.dvMatrix[self.name]))

                    # after E we print...
                    if self.name == 'E':
                        print("Number of rounds till convergence (Round # when one of the nodes last updated its DV) "
                              "= %d" % self.lastRoundChangedTotal)
                        print("------")

                        # Ends here
                        return

                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    # move on to the next node in order A,B,C,D,E
                    s.connect(('localhost', socket_for_node[next_node[self.name]]))
                    s.sendall(b'end')
                    #close connection
                    s.close()
                    return

                # check the changed data here
                elif 'changed?' in data:

                    # did previous round change the dv?
                    if self.lastChangedRound != round:
                        # if not changed then no update, send previous changed
                        conn.sendall(b'false;%d' %self.lastChangedRound)
                    else:
                        conn.sendall(b'true')

                # if its the nodes turn to send the message
                elif 'turn' in data:

                    # Update the round and do again
                    if self.name == 'A':
                        round += 1

                    print("------")
                    print("Round %d: %s" % (round, self.name))
                    print("Current DV matrix =" + str(self.dvMatrix))

                    lastMatrixStr = "None" if self.lastMatrix is None else str(self.lastMatrix)
                    print("Last DV matrix = " + lastMatrixStr)

                    #changed or not? change the statusa
                    if isNotChanged(self.dvMatrix, self.lastMatrix):
                        status = "Same"
                    else:
                        status = "Updated"

                    print("Updated from last DV matrix or the same? " + status)

                    # send out the current dv to all the neighbors so for loop
                    #printing accordingly
                    for neighbor in self.neighbors:
                        print("\nSending DV to node %s" % neighbor)
                        neighborSocket = socket_for_node[neighbor]

                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.connect(('localhost', neighborSocket))

                        # Send this nodes distance vector to the neighbor by encoding
                        s.sendall(bytes(self.name + ";" + " ".join(list(map(str, self.dvMatrix[self.name]))),
                                        encoding='utf8'))
                        while True:
                            done = s.recv(1024)
                            
                            # if done end...
                            if done:
                                break
                        s.shutdown(1)
                        s.close()

                    # get the current matrix and store as the last matrix for next node message
                    #using deep copy here
                    self.lastMatrix = deepcopy(self.dvMatrix)

                    # if the end of round is there, print accordingly 
                    if self.name == 'E':

                        roundChange = False
                        #here we keep track of all the changed rounds
                        lastRoundChange = 0
                        
                        
                        # all the nodes report if the node has changed
                        # if changed set roundChanged to True
                        for nodeName in socket_for_node.keys():

                            if nodeName == self.name:
                                if self.lastChangedRound == round:
                                    roundChange = True
                                else:
                                    lastRoundChange = max(self.lastChangedRound, lastRoundChange)

                                continue

                            #broadcast the message asking changed
                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            s.connect(('localhost', socket_for_node[nodeName]))
                            s.sendall(b'changed?')

                            while True:
                                changed = s.recvfrom(1024)

                                if changed:
                                    break

                            if changed[0].decode('utf-8').strip().split(";")[0] == 'true':
                                # If any DV was changed, set roundChange = true
                                roundChange = True
                            else:
                                nodeRoundChange = int(changed[0].decode('utf-8').strip().split(";")[1])
                                lastRoundChange = max(lastRoundChange, nodeRoundChange)

                            s.close()

                        #no changes so the end is sent
                        if not roundChange:

                            self.lastRoundChangedTotal = lastRoundChange
                            print("-------")
                            print("Final Output:")

                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            s.connect(('localhost', socket_for_node[next_node[self.name]]))
                            s.sendall(b'end')

                            s.close()
                            break

                    # next run incoming
                    nextNode = next_node[self.name]
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.connect(('localhost', socket_for_node[nextNode]))
                    s.sendall(b'turn')
                    s.close()

                    break

                # dv is received
                else:

                    # which neighnbor send the dv?
                    neighborName = data.split(";")[0]
                    try:
                        # neighborDv is updated
                        neighborDV = list(map(float, data.split(";")[1].split()))
                    except IndexError as e:
                        continue

                    #print out the message
                    print("Node %s received DV from %s" % (self.name, neighborName))

                    #update the DVTable
                    self.updateDVTable(neighborDV, neighborName)

                    print("New DV matrix at node %s = " % self.name + str(self.dvMatrix))

                    # was there a change?
                    changed = not isNotChanged(self.dvMatrix, self.lastMatrix)

                    if changed:
                        self.lastChangedRound = round

                    # finished so send call done to all
                    conn.sendall(b'done')

                    break


# network_init is here...
def network_init():
    
    # first open the network.txt file
    fileName = "network.txt"
    
    # matrix for adjacent/neighbors for nodes
    matrix_adjacent = []
    numNodes = 5
    nodeNames = ['A', 'B', 'C', 'D', 'E']

    with open(fileName) as nwFile:
        
        # Read the file and save the adjacency matrix
        #iterate over the file and remove spaces and \n
        for _ in range(numNodes):
            line = nwFile.readline()
            #now save each line in row then append row to matrix_adjacent
            row = list(map(float, line.strip().split(" ")))        
            matrix_adjacent.append(row)

    # list of nodes and list of neighbors
    nodes_list = []
    list_of_neighbor = []

    # get the neighbors and the distance
    for i in range(numNodes):
        name = nodeNames[i]
        neighbors = {}

        for j in range(numNodes):
            if matrix_adjacent[i][j] != 0:
                neighbors[nodeNames[j]] = matrix_adjacent[i][j]

        list_of_neighbor.append(neighbors)

        # here id for threads are set to as in order 3001 to be unique
        # tried 1001 and 2001 but they were giving permission denied errors
        # those are same as the ports for the socket as thats how the sockets
        # will be identified
        thread_number = (i + 1) * 3000 + 1
        socket_for_node[name] = thread_number

    for i in range(numNodes):
        
        #for each of the node
        name = nodeNames[i]
        
        #need thread for each node to do it simultaneously
        # go to the NodeExecute Class, give socket, name and list of neighbors
        nodeThread = NodeExecute(socket_for_node[name], name, list_of_neighbor[i])
        
        # append it in on nodes list
        nodes_list.append(nodeThread)
        nodeThread.start()

    # Now start the sending of the nodes and neighbors starting from A
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('localhost', socket_for_node['A']))
    s.sendall(b'turn')
    #close the connection
    s.close()
    #done here....


# main is here, calls network_init()
def main():
#    print("In main")
    network_init()
    
# program starts here at the bottom.
if __name__ == '__main__':
    main()
