#!/usr/bin/env python3
"""验证监控器系统完整功能"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def verify_monitor_system():
    """验证监控器系统完整功能"""
    print("🔍 验证监控器系统完整功能...")
    
    verification_results = {
        "monitor_message_flow": False,
        "monitor_field_only": False,
        "redis_integration": False,
        "session_trigger": False,
        "complete_react_cycle": False
    }
    
    try:
        # 测试1: Redis消息集成
        from src.stock_cli.utils.redis_bus import RedisBus
        test_message = "测试监控器消息"
        await RedisBus.publish_message("test_system", "default", test_message)
        verification_results["redis_integration"] = True
        print("✅ Redis消息集成正常")
        
        # 测试2: 监控器注册和管理
        from src.stock_cli.core.monitor_manager import get_monitor_manager
        manager = await get_monitor_manager()
        
        # 注册定时器监控器
        from src.stock_cli.monitors.timer import register_timer_monitor
        await register_timer_monitor()
        
        # 检查监控器是否存在
        monitors = manager.list_monitors()
        print(f"📋 可用监控器: {monitors}")
        monitor_names = [m["name"] for m in monitors]
        print(f"📋 监控器名称列表: {monitor_names}")
        if "timer" in monitor_names:
            verification_results["monitor_field_only"] = True
            print("✅ 监控器注册和管理正常")
        else:
            print("❌ 定时器监控器未找到")
        
        # 测试3: Session inbox触发器
        from src.stock_cli.triggers.session_inbox import session_inbox_trigger
        # 启动触发器（短暂运行）
        import asyncio
        task = asyncio.create_task(session_inbox_trigger("test_verify", {}))
        await asyncio.sleep(0.5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        verification_results["session_trigger"] = True
        print("✅ Session inbox触发器正常")
        
        # 测试4: 完整的ReAct循环（通过监控器消息）
        from src.stock_cli.core.session_manager import SessionManager
        session = SessionManager().get_session("default")
        
        # 发送监控器消息到test_verify会话（与inbox触发器监听同一个会话）
        monitor_msg = "测试完整的ReAct循环"
        await RedisBus.publish_message("monitor_system", "test_verify", monitor_msg)
        await asyncio.sleep(1)
        
        # 检查test_verify会话是否处理了消息
        from src.stock_cli.core.session_manager import SessionManager
        test_session = SessionManager().get_session("test_verify")
        qa_history = test_session.context.get("qa_history", [])
        print(f"📋 test_verify Session QA历史: {len(qa_history)} 条消息")
        for i, msg in enumerate(qa_history[-5:]):  # 显示最后5条消息
            print(f"  {i}: {msg['role']}: {msg['content'][:100]}...")
        
        monitor_msgs = [msg for msg in qa_history if "monitor_system" in str(msg.get("content", ""))]
        
        if monitor_msgs:
            verification_results["monitor_message_flow"] = True
            verification_results["complete_react_cycle"] = True
            print("✅ 完整的ReAct循环正常")
        else:
            print("❌ Session未收到监控器消息")
        
        # 汇总结果
        print("\n📊 验证结果汇总:")
        all_passed = True
        for test_name, passed in verification_results.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {test_name}: {'通过' if passed else '失败'}")
            if not passed:
                all_passed = False
        
        if all_passed:
            print("\n🎉 所有监控器系统功能验证通过！")
        else:
            print("\n⚠️  部分功能验证失败，请检查相关组件")
            
        return all_passed
        
    except Exception as e:
        print(f"❌ 验证过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 开始监控器系统验证")
    success = asyncio.run(verify_monitor_system())
    if success:
        print("🎉 监控器系统验证完成！")
    else:
        print("❌ 监控器系统验证失败")
        sys.exit(1)