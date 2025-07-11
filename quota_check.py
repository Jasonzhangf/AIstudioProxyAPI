#!/usr/bin/env python3
"""
检查当前浏览器实例的quota状态
"""

import json
import requests

def check_quota_via_websocket(ws_url):
    """通过WebSocket检查quota错误"""
    try:
        import websocket
        print(f"         🔗 连接到: {ws_url}")
        ws = websocket.create_connection(ws_url, timeout=10)
        print(f"         ✅ WebSocket连接成功")
        
        # 检查是否有.model-error元素
        eval_cmd = {
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": """
                (() => {
                    const modelErrors = document.querySelectorAll('div.model-error');
                    const allErrors = document.querySelectorAll('[class*="error"], [class*="warning"]');
                    const results = [];
                    
                    // 检查model-error元素
                    for (const error of modelErrors) {
                        const text = error.textContent || error.innerText || '';
                        results.push('MODEL-ERROR: ' + text.trim());
                    }
                    
                    // 检查所有可能的错误元素
                    for (const error of allErrors) {
                        const text = error.textContent || error.innerText || '';
                        if (text.toLowerCase().includes('rate limit') || 
                            text.toLowerCase().includes('quota') || 
                            text.toLowerCase().includes('exceeded') ||
                            text.toLowerCase().includes('reached your') ||
                            text.toLowerCase().includes('try again later')) {
                            results.push('ERROR: ' + text.trim());
                        }
                    }
                    
                    return {
                        hasQuotaError: results.some(r => r.toLowerCase().includes('rate limit') || r.toLowerCase().includes('quota')),
                        errorMessages: results,
                        totalModelErrors: modelErrors.length,
                        totalErrorElements: allErrors.length,
                        url: window.location.href,
                        title: document.title
                    };
                })()
                """
            }
        }
        
        print(f"         📤 发送命令...")
        ws.send(json.dumps(eval_cmd))
        
        print(f"         📥 等待响应...")
        response_text = ws.recv()
        response = json.loads(response_text)
        ws.close()
        
        print(f"         📋 响应: {response}")
        
        if 'result' in response and 'result' in response['result']:
            result = response['result']['result']['value']
            return result
        else:
            print(f"         ⚠️  响应格式异常: {response}")
            return None
        
    except Exception as e:
        print(f"         ❌ WebSocket检查失败: {e}")
        return None

def check_quota_status():
    """检查当前浏览器实例的quota状态"""
    print("🔍 检查当前浏览器实例的quota状态...")
    
    # 测试各个浏览器实例
    browser_ports = [9222, 9223, 9224]
    
    for port in browser_ports:
        try:
            print(f"\n📡 检查浏览器实例端口 {port}")
            
            # 获取页面信息
            json_url = f"http://localhost:{port}/json"
            response = requests.get(json_url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                # 检查是否是单个WebSocket端点
                if isinstance(data, dict) and 'wsEndpointPath' in data:
                    ws_endpoint = data['wsEndpointPath']
                    print(f"   📄 WebSocket端点: {ws_endpoint}")
                    
                    # 构建完整的WebSocket URL
                    ws_url = f"ws://localhost:{port}{ws_endpoint}"
                    print(f"   🔍 检查页面内容中的quota错误...")
                    
                    # 检查quota
                    quota_result = check_quota_via_websocket(ws_url)
                    
                    if quota_result:
                        print(f"   📊 检查结果:")
                        print(f"       总共model-error元素: {quota_result.get('totalModelErrors', 0)}")
                        print(f"       发现quota错误: {quota_result.get('hasQuotaError', False)}")
                        
                        if quota_result.get('hasQuotaError'):
                            print(f"   🚨 检测到QUOTA错误!")
                            for msg in quota_result.get('errorMessages', []):
                                print(f"       错误信息: {msg}")
                            return True  # 找到quota错误
                        else:
                            print(f"   ✅ 未检测到quota错误")
                else:
                    print(f"   ⚠️  未知的响应格式: {data}")
                        
            else:
                print(f"   ❌ 连接失败，状态码: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ 连接端口 {port} 失败: {e}")
    
    print("\n✅ quota状态检查完成")
    return False

if __name__ == "__main__":
    found_quota_error = check_quota_status()
    if found_quota_error:
        print("\n🚨 总结：发现了quota错误，自动降级机制应该会被触发！")
    else:
        print("\n✅ 总结：未发现quota错误")