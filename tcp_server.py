import socket

# Define server address and port
server_address = ('localhost', 65432)

# Create a TCP/IP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind the socket to the address and port
sock.bind(server_address)

# Listen for incoming connections
sock.listen(1)

print(f"Server listening on {server_address}")

while True:
    # Wait for a connection
    connection, client_address = sock.accept()
    try:
        print(f"Connection from {client_address}")

        # Receive the data in small chunks and retransmit it
        while True:
            data = connection.recv(32)
            print(f"Received {data}")
            if data:
                # Send data back to the client
                connection.sendall(data)
            else:
                break
    finally:
        # Clean up the connection
        connection.close()
