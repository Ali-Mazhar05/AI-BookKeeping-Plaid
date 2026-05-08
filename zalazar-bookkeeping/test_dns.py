import socket
import sys

hosts = [
    "aws-1-ap-northeast-1.pooler.supabase.com",
    "db.vlgtkscnskmhzmlkonhz.supabase.co"
]
port = 6543

for host in hosts:
    print(f"Testing getaddrinfo for {host}:{port}")
    try:
        infos = socket.getaddrinfo(host, port)
        print("Success!")
        for info in infos:
            print(info)
    except Exception as e:
        print(f"Failed: {e}")

print("\nTesting connection to IPv4 of pooler...")
host_ipv4 = "13.114.6.6"
try:
    s = socket.create_connection((host_ipv4, port), timeout=5)
    print(f"Successfully connected to {host_ipv4}:{port}")
    s.close()
except Exception as e:
    print(f"Connection to {host_ipv4} failed: {e}")
