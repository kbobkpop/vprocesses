# vprocesses
This a package for visualizing concurrent programs.

It is a small partial wrapper to the standard python multiprocessing module which is also required to run.

It has been implemented to use the same syntax as the multiprocessing module.

By importing the package as an alias to multiprocessing like this:
```python
import vprocesses as multiprocessing
```
You are able to instantiate call <code>multiprocessing.Processes</code>, call <code>multiprocessing.Pipe()</code> and <code>multiprocessing.Lock()</code> and use the objects as you would with the normal multiprocessing module.

Calls to <code>select.select</code> are also possible either through <code>multiprocessing.VSelect.select()</code> or by simply importing VSelect as select like this:
```python
from vprocesses import VSelect as select
```
This allows the standard <code>select.select()</code> syntax.

When you have defined all your Processes, Locks and Connections they should be passed to the VManager() which can be instantiated like this multiprocessing.VManager() based on the above mentioned import statement.

Having instantiated a VManager, you need to call <code>.start()</code> on the object in order to initalize the graph and start the processes.

You can now run a tick by calling <code>.runAllToTick()</code> with the list of processes as argument.

You can also call <code>.stepwiseTicks()</code> also with the list of processes to interactively running ticks by pressing 'enter' after each tick.

If you have set up your processes such that they terminate you can also call <code>.runTicksToEnd()</code> which will then loop through ticks until termination of all processes.

##### Ticks
Ticks are defined as each process reaching a synchronization point. If a process is sending something on a channel the data will first be able to be received on the next tick. The sending and receiving process will both block until the transmission has been completed.

This definition is perhaps a bit arbitrary, and I am considering to change it in the future, but it was chosen to give a good visualization, which hopefully can aid in understanding concurrent systems and concurrent programming.

##### Options for VManager
Optional parameters for the constructor of the VManager:
 - logging: True/False (default: False) - If True a logfile is created and written to in each tick.
 - logFile: name of the log file (default: 'log.txt')
 - output: path for the output of the drawings (default: 'output/Tick')
 - interactiveLocks: True/False (default: False) - If True, the user can decided which process acquires a lock.
 - draw: True/False (default: True) - If True, renders are made automatically at the end of each tick.
 - tickTock: True/False (default: True) - If True, transmission will at the earliest complete the tick after the sending process reaches it's <code>.send()<\code> point. If False (beta) transmission will happen as soon as the sending and receiving side is ready. This works but I am not sure if I like the visualization it produces currently.
 - incrTicks: True/False (default: True). If True, a tick counter will be incremented each tick resulting in drawings with a new tick suffix. If False, ticks will not be incremented, and the same image will be overwritten each tick. This can be used with the <code>.stepwiseTicks()</code> method call to iteratively show the progression of the system withouth having to browse through images.

#### Limitations
 - When calling the <code>vprocesses.Pipe()<\code>, <bold> the first returned connection is the sending end of the channel, the second is the receiving end </code>. Used otherwise will result in undefined behaviour.
 - VSelect only supports the first parameter, <code>rlist</code> of the standard <code>select.select()</code>. To maintain syntax similarity to the standard <code>select.select()<\code> you can pass <code>xlist<\code>, <code>wlist<\code> and <code>timeout<\code> but they will have no effect.

##### Dependencies:

- graphviz 0.20.3 
- python 3.8+

To install graphviz 0.20.3 use pip to install:

<code>$ pip install graphviz</code>

##### Example 1:

![alt text](https://github.com/kbobkpop/vprocesses/blob/master/vprocesses/producerConsumerTest/Tick_0.png?raw=true)
![alt text](https://github.com/kbobkpop/vprocesses/blob/master/vprocesses/producerConsumerTest/Tick_1.png?raw=true)
![alt text](https://github.com/kbobkpop/vprocesses/blob/master/vprocesses/producerConsumerTest/Tick_2.png?raw=true)

A producer process is producing integer and sending them to a consumer process. The outline of the nodes being red, indicate that both processes are blocking and the '0' next to the edge indicates that the integer 0 is is being sent by p1. 

##### Example 2:

![alt text](https://github.com/kbobkpop/vprocesses/blob/master/vprocesses/lockedPingPongTest/Tick_0.png?raw=true)
![alt text](https://github.com/kbobkpop/vprocesses/blob/master/vprocesses/lockedPingPongTest/Tick_1.png?raw=true)
![alt text](https://github.com/kbobkpop/vprocesses/blob/master/vprocesses/lockedPingPongTest/Tick_2.png?raw=true)


A slightly more complex example of the four processes Albert, Bertha, Charlie and Dennis which parwise are sending the strings 'Hello' and 'Hi' back and forth. Though before sending they are required to acquire the shared lock, lock1. A connection from a process to a lock is indicated by black dashed edge. If the lock is acquired by a process the edge is solid and blue and if a process is waiting to acquire a lock the edge is dashed and purple.

##### Example 3:

![alt text](https://github.com/kbobkpop/vprocesses/blob/master/vprocesses/selectTest/Tick_0.png?raw=true)
![alt text](https://github.com/kbobkpop/vprocesses/blob/master/vprocesses/selectTest/Tick_1.png?raw=true)
![alt text](https://github.com/kbobkpop/vprocesses/blob/master/vprocesses/selectTest/Tick_2.png?raw=true)

In this example there is one node, s1, which is waiting at a select call, indiciated by the dashed red outline, until something is on one of the channels leading towards it.

All examples and more can be found in the examples directory.
