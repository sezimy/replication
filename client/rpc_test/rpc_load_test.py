import unittest
import time
import threading
import statistics
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from protocol.client_rpc_protocol import ClientRpcProtocol
from network.client_rpc_handler import ClientRpcHandler

class TestRPCLoad(unittest.TestCase):
    def setUp(self):
        self.rpc = ClientRpcProtocol()
        self.test_data = {
            'username': 'testuser',
            'password': 'TestPass123!',
            'message': 'Hello, World!',
            'recipient': 'user2'
        }
        self.message_sizes = []
        self.serialization_times = []

    def test_message_size_analysis(self):
        """Analyze sizes of different message types"""
        messages = {
            'Login': ('L', [self.test_data['username'], self.test_data['password']]),
            'Register': ('R', [self.test_data['username'], self.test_data['password']]),
            'Chat': ('M', [self.test_data['username'], self.test_data['recipient'], self.test_data['message']]),
            'Delete': ('D', [self.test_data['message'], time.time(), self.test_data['username'], self.test_data['recipient']]),
            'Logoff': ('O', [self.test_data['username']])
        }
        
        print("\nRPC Message Size Analysis:")
        for msg_type, (code, params) in messages.items():
            data = self.rpc.serialize_message(code, params)
            size = len(data)
            self.message_sizes.append(size)
            print(f"{msg_type}: {size} bytes")
        
        avg_size = statistics.mean(self.message_sizes)
        print(f"\nAverage message size: {avg_size:.2f} bytes")
        print(f"Min size: {min(self.message_sizes)} bytes")
        print(f"Max size: {max(self.message_sizes)} bytes")

    def test_serialization_performance(self):
        """Test serialization performance under load"""
        iterations = 1000
        start_time = time.time()
        
        for i in range(iterations):
            msg_start = time.time()
            self.rpc.serialize_message('M', [
                self.test_data['username'],
                self.test_data['recipient'],
                f"Message {i}"
            ])
            self.serialization_times.append(time.time() - msg_start)
        
        total_time = time.time() - start_time
        avg_time = statistics.mean(self.serialization_times)
        
        print(f"\nSerialization Performance:")
        print(f"Total time for {iterations} messages: {total_time:.2f} seconds")
        print(f"Average time per message: {avg_time*1000:.2f} ms")
        print(f"Messages per second: {iterations/total_time:.2f}")

    def test_concurrent_load(self):
        """Test performance under concurrent load"""
        thread_count = 10
        messages_per_thread = 100
        all_times = []
        
        def send_messages():
            thread_times = []
            for i in range(messages_per_thread):
                start = time.time()
                self.rpc.serialize_message('M', [
                    self.test_data['username'],
                    self.test_data['recipient'],
                    f"Message {i}"
                ])
                thread_times.append(time.time() - start)
            all_times.extend(thread_times)
        
        threads = []
        start_time = time.time()
        
        for _ in range(thread_count):
            thread = threading.Thread(target=send_messages)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        total_messages = thread_count * messages_per_thread
        
        print(f"\nConcurrent Load Test Results:")
        print(f"Total messages: {total_messages}")
        print(f"Total time: {total_time:.2f} seconds")
        print(f"Average time per message: {statistics.mean(all_times)*1000:.2f} ms")
        print(f"Messages per second: {total_messages/total_time:.2f}")

if __name__ == '__main__':
    unittest.main()
