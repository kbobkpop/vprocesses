# vprocesses
This a module for visualizing concurrent programs.

It is a small partial wrapper to the standard python multiprocessing module which is also required to run.

It has been implemented to use the same syntax as the multiprocessing module.

By importing the package as an alias to multiprocessing like this:
```python
import vprocesses as multiprocessing
```
You are able to instantiate <code>multiprocessing.Processes</code>, call <code>multiprocessing.Pipe()</code> and <code>multiprocessing.Lock()</code> and use the objects as you would with the standard multiprocessing module.

Calls to <code>select.select</code> are also possible either through <code>multiprocessing.VSelect.select()</code> or by simply importing VSelect as select like this:
```python
from vprocesses import VSelect as select
```
This allows the standard <code>select.select()</code> syntax.

When you have defined all your Processes, Locks and Connections they should be passed to the VManager() like this:
```python
processes = [p1, p2]
connections = [c1, c2, c3, c4]
locks = [lock1, lock2]

vm = multiprocessing.VManager(processes, connections, locks)
```
Which is following the above <code>import vprocesses as multiprocessing</code> statement.

Alternatively you can import the VManager class:
```python
from vprocesses import VManager
...
vm = VManager(processes, connections, locks)
```
This allows instantiating the VManager directly, without the multiprocessing prefix.

Having instantiated a VManager, you need to call <code>.start()</code> on the object in order to initalize the graph and start the processes.

You can now run a tick by calling <code>.runAllToTick()</code> with the list of processes as argument. This call returns a list of able processes which should be passed as argument for the next tick.

You can also call <code>.stepwiseTicks()</code> also with the list of processes to interactively running ticks by pressing 'enter' after each tick.

If you have set up your processes such that they terminate you can also call <code>.runTicksToEnd()</code> which will then loop through ticks until termination of all processes.

### Ticks
Ticks are defined as each process reaching a synchronization point. If a process reaches a .send() call, the process will block until the other side of the channel is ready to receive by having reached a .recv() call. When both sides on a channel have reached their respective synchronization points, data will be transmitted and both processes will continue until their next synchronization points. After each process has reached a synchronization point, the manager will draw in image and allow processes to progress when possible.

Here is a simple example of how that could look:

![alt text](https://github.com/kbobkpop/vprocesses/blob/master/nodes_edges_images/simpleExampleTick.png?raw=true)

### Tocks
As can be seen in the above image, except when the system starts, ticks always end with processes blocking or terminated. This results in a slightly undynamic image progression with little change between images.
For this reason there is also a 'Tock', which is an image rendered after the completion of a transmission. This should help in quickly seeing which processes progressed within the tick.

This is how the same above example would look like with tocks turned on:

![alt text](https://github.com/kbobkpop/vprocesses/blob/master/nodes_edges_images/simpleExample.png?raw=true)

Tocks are by default enabled, but can be disabled when instantiating the VManager by setting the optional argument <code>tick_tock=False</code>.

### Options for VManager
Optional parameters for the constructor of the VManager:
 - logging: True/False (default: False) - If True a logfile is created and written to in each tick.
 - log_file: name of the log file (default: 'log.txt')
 - output: path for the output of the drawings (default: 'output/Tick')
 - interactive_locks: True/False (default: False) - If True, the user can decided which process acquires a lock.
 - draw: True/False (default: True) - If True, renders are made automatically at the end of each tick.
 - tick_tock: True/False (default: True) - If True, transmission tock images will be rendered after completed transmissions. If False only tick images will be rendered.
 - incr_ticks: True/False (default: True). If True, a tick counter will be incremented each tick resulting in drawings with a new tick suffix. If False, ticks will not be incremented, and the same image will be overwritten each tick. This can be used with the <code>.stepwiseTicks()</code> method call to iteratively show the progression of the system withouth having to browse through images.

### Limitations
 - When calling the <code>vprocesses.Pipe()</code>, <bold> the first returned connection is the sending end of the channel, the second is the receiving end </code>. Used otherwise will result in undefined behaviour.
 - VSelect only supports the first parameter, <code>rlist</code> of the standard <code>select.select()</code>. To maintain syntax similarity to the standard <code>select.select()</code> you can pass <code>xlist</code>, <code>wlist</code> and <code>timeout</code> but they will have no effect.
 - If you create a system that could deadlock using the multiprocessing library, it can also deadlock using this module. The deadlock will in fact most likely show earlier as the channels are simulated to be unbuffered in the vprocesses implementation.

### Dependencies:

- graphviz 0.20.3
- python 3.8+

To install graphviz 0.20.3 use pip to install:

<code>$ pip install graphviz</code>

### Example 1:

![alt text](https://github.com/kbobkpop/vprocesses/blob/master/examples/producerConsumer/Tock_0.png?raw=true)
![alt text](https://github.com/kbobkpop/vprocesses/blob/master/examples/producerConsumer/Tick_1.png?raw=true)
![alt text](https://github.com/kbobkpop/vprocesses/blob/master/examples/producerConsumer/Tock_1.png?raw=true)
![alt text](https://github.com/kbobkpop/vprocesses/blob/master/examples/producerConsumer/Tick_2.png?raw=true)

A producer process is producing integers and sending them to a consumer process. The outline of the nodes being red, indicate that both processes are blocking and the '0' next to the edge indicates that the integer 0 is being sent by p1.

### Example 2:

![alt text](https://github.com/kbobkpop/vprocesses/blob/master/examples/lockedPingPong/Tock_0.png?raw=true)
![alt text](https://github.com/kbobkpop/vprocesses/blob/master/examples/lockedPingPong/Tick_1.png?raw=true)
![alt text](https://github.com/kbobkpop/vprocesses/blob/master/examples/lockedPingPong/Tock_1.png?raw=true)
![alt text](https://github.com/kbobkpop/vprocesses/blob/master/examples/lockedPingPong/Tick_2.png?raw=true)

A slightly more complex example of the four processes Albert, Bertha, Charlie and Dennis which parwise are sending the strings 'Hello' and 'Hi' back and forth. Though, before sending they are required to acquire the shared lock, lock1. A connection from a process to a lock is indicated by a black dashed edge. If the lock is acquired by a process the edge is solid and blue and if a process is waiting to acquire a lock the edge is dashed and purple.

### Example 3:

![alt text](https://github.com/kbobkpop/vprocesses/blob/master/examples/complex/Tock_0.png?raw=true)
![alt text](https://github.com/kbobkpop/vprocesses/blob/master/examples/complex/Tick_1.png?raw=true)
![alt text](https://github.com/kbobkpop/vprocesses/blob/master/examples/complex/Tock_1.png?raw=true)
![alt text](https://github.com/kbobkpop/vprocesses/blob/master/examples/complex/Tick_2.png?raw=true)

In this example the nodes Slct1, Slct2 and Slct3 all contain a VSelect.select(), which are their first synchronization poing. Slct3 is blocking at that call to .select() which is indicated by the red dashed outline of the node. Because Slct1 and Slct2 have data on an incoming channel their select call returns before the end of Tick 1, and instead they are blocking on their subsequent .recv() call.

All examples and more can be found in the examples directory.
