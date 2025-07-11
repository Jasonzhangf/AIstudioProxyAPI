#!/usr/bin/env python3
"""
检测运行中的Camoufox实例的WebSocket端点
"""
import requests
import time
import json

def detect_websocket_endpoint(port):
    """检测指定端口的WebSocket端点"""
    try:
        # 尝试连接到调试端点
        debug_url = f"http://localhost:{port}/json/version"
        response = requests.get(debug_url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            ws_endpoint = data.get('webSocketDebuggerUrl', '')
            if ws_endpoint:
                return ws_endpoint
        
        # 如果version端点不工作，尝试list端点
        list_url = f"http://localhost:{port}/json/list"
        response = requests.get(list_url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                ws_endpoint = data[0].get('webSocketDebuggerUrl', '')
                if ws_endpoint:
                    return ws_endpoint
                    
    except Exception as e:
        print(f"检测端口 {port} 时出错: {e}")
    
    return None

def main():
    """主函数"""
    ports = [9230, 9240, 9269]
    
    print("🔍 检测WebSocket端点...")
    
    for port in ports:
        print(f"\n检测端口 {port}:")
        endpoint = detect_websocket_endpoint(port)
        
        if endpoint:
            print(f"✅ 找到WebSocket端点: {endpoint}")
        else:
            print(f"❌ 未找到WebSocket端点")
            
            # 检查端口是否有进程监听
            import socket
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('localhost', port))
                if result == 0:
                    print(f"   端口 {port} 有进程监听")
                else:
                    print(f"   端口 {port} 没有进程监听")
                sock.close()
            except:
                print(f"   无法检查端口 {port}")

if __name__ == "__main__":
    main()