# ripRouting
# Implement Routing Daemons as normal userspace programs under Linux.
# Instead of sending routing packets over real network interfaces, 
# the routing daemons communicate with one another (which run in parallel on the same machine)
# through local UDP sockets. 
# Each instance of the demon runs as a separate process
