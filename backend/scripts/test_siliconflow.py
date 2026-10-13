#!/usr/bin/env python3
"""
SiliconFlow API Test Script
Test SiliconFlow LLM integration with the provided API key.
"""
import asyncio
import sys
import os

sys.path.insert(0, '/workspace/backend')

from app.llm.siliconflow_provider import SiliconFlowProvider, SiliconFlowModel


SILICONFLOW_API_KEY = "REDACTED_API_KEY"


async def test_siliconflow():
    """Test SiliconFlow API connection and generation."""
    print("=" * 60)
    print("SiliconFlow API Integration Test")
    print("=" * 60)
    
    provider = SiliconFlowProvider(
        api_key=SILICONFLOW_API_KEY,
        default_model=SiliconFlowModel.QWEN_7B.value,
        timeout=120.0
    )
    
    print(f"\n✓ SiliconFlow Provider initialized")
    print(f"  Default model: {SiliconFlowModel.QWEN_7B.value}")
    print(f"  Base URL: https://api.siliconflow.cn/v1")
    
    print("\n" + "-" * 60)
    print("Available Models:")
    print("-" * 60)
    for model_id in provider.get_available_models():
        info = provider.get_model_info(model_id)
        print(f"  • {model_id}")
        print(f"    Name: {info['name']}")
        print(f"    Provider: {info['provider']}")
        print(f"    Description: {info['description']}")
        print()
    
    print("-" * 60)
    print("Testing Connection and Generation:")
    print("-" * 60)
    
    test_prompts = [
        ("Simple greeting", "请用一句话介绍自己"),
        ("Code generation", "用Python写一个快速排序算法"),
        ("Translation", "把'Hello, how are you?'翻译成中文"),
        ("Math problem", "计算: 123 + 456 = ?"),
    ]
    
    for test_name, prompt in test_prompts:
        print(f"\n📝 Test: {test_name}")
        print(f"   Prompt: {prompt}")
        try:
            response = await provider.generate(
                prompt=prompt,
                max_tokens=500,
                temperature=0.7
            )
            
            print(f"   ✅ Success!")
            print(f"   Model: {response.model}")
            print(f"   Latency: {response.latency_ms:.2f}ms")
            print(f"   Tokens: {response.usage.get('total_tokens', 0)}")
            print(f"   Response:\n{response.content[:200]}...")
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
    
    print("\n" + "=" * 60)
    print("SiliconFlow API Test Complete!")
    print("=" * 60)
    
    await provider.close()


async def test_chat_mode():
    """Test chat mode with conversation history."""
    print("\n" + "=" * 60)
    print("Testing Chat Mode:")
    print("=" * 60)
    
    provider = SiliconFlowProvider(
        api_key=SILICONFLOW_API_KEY,
        default_model=SiliconFlowModel.QWEN_7B.value
    )
    
    messages = [
        {"role": "system", "content": "你是一个乐于助人的AI助手。"},
        {"role": "user", "content": "你好，我叫小明"},
        {"role": "assistant", "content": "你好小明！很高兴认识你。有什么我可以帮助你的吗？"},
        {"role": "user", "content": "你能帮我写一首诗吗？"},
    ]
    
    print(f"\nConversation:")
    for msg in messages:
        print(f"  [{msg['role']}]: {msg['content'][:50]}...")
    
    try:
        response = await provider.chat(messages=messages, max_tokens=300)
        print(f"\n  [assistant]: {response.content}")
        print(f"\n✅ Chat mode test passed!")
    except Exception as e:
        print(f"\n❌ Chat mode test failed: {str(e)}")
    
    await provider.close()


if __name__ == "__main__":
    print("\n🔄 Starting SiliconFlow API tests...\n")
    
    try:
        asyncio.run(test_siliconflow())
        asyncio.run(test_chat_mode())
        print("\n🎉 All tests completed successfully!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
