"""
RedisBus: 轻量级会话发现与通信总线（基于 redis.asyncio）

功能：
- 会话注册/注销：在线会话集合，支持动态发现
- 会话列表：列出所有在线会话
- 消息发布/订阅：向指定 session 渠道发送/接收通信消息

配置来源（可选）：
- config/settings.yaml 中的 redis 配置（若不存在则使用默认）
  示例：
    redis:
      host: "127.0.0.1"
      port: 6379
      db: 0
      password: ""
      prefix: "stock_cli"

默认：
- host=127.0.0.1, port=6379, db=0, password=None, prefix="stock_cli"
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

try:
    # redis-py 4.x+
    from redis.asyncio import Redis
    from redis.asyncio.client import PubSub
except Exception as e:  # pragma: no cover
    raise RuntimeError("需要 'redis' 依赖（pyproject.toml 已包含）。请执行: uv sync") from e

logger = logging.getLogger(__name__)


class RedisBus:
    _client: Optional[Redis] = None
    _prefix: str = "stock_cli"
    _lock = asyncio.Lock()

    @classmethod
    async def _load_settings(cls) -> Dict[str, Any]:
        """尝试从 settings.yaml 读取 redis 配置，不存在则返回默认。"""
        try:
            from ..core.config_resolver import resolve_settings_path, load_settings  # 避免循环导入
            settings_path = resolve_settings_path()
            settings = load_settings(settings_path) or {}
            redis_cfg = settings.get("redis", {}) or {}
            logger.info("加载Redis配置: %s", redis_cfg)
        except Exception as e:
            logger.warning("加载Redis配置失败，使用默认配置: %s", e)
            redis_cfg = {}

        host = redis_cfg.get("host", "127.0.0.1")
        port = int(redis_cfg.get("port", 6379))
        db = int(redis_cfg.get("db", 0))
        password = redis_cfg.get("password") or None
        prefix = str(redis_cfg.get("prefix", "stock_cli"))
        config = {
            "host": host,
            "port": port,
            "db": db,
            "password": password,
            "prefix": prefix,
        }
        logger.info("Redis配置: %s", config)
        return config

    @classmethod
    async def _ensure_client(cls) -> Redis:
        """懒加载单例 Redis 客户端。"""
        if cls._client is not None:
            logger.debug("使用已存在的Redis客户端")
            return cls._client
        async with cls._lock:
            if cls._client is not None:
                logger.debug("使用已存在的Redis客户端(双重检查)")
                return cls._client
            logger.info("初始化Redis客户端")
            cfg = await cls._load_settings()
            cls._prefix = cfg["prefix"]
            cls._client = Redis(
                host=cfg["host"],
                port=cfg["port"],
                db=cfg["db"],
                password=cfg["password"],
                decode_responses=True,  # 自动解码为 str
            )
            # 简单 ping 验证
            try:
                await cls._client.ping()
                logger.info("RedisBus 连接成功 %s:%s db=%s", cfg["host"], cfg["port"], cfg["db"])
            except Exception as e:
                logger.error("RedisBus 无法连接至 Redis: %r", e)
                raise
            return cls._client

    @classmethod
    def _key_sessions(cls) -> str:
        return f"{cls._prefix}:sessions"

    @classmethod
    def _channel_for_session(cls, session_id: str) -> str:
        return f"{cls._prefix}:comm:{session_id}"

    # ---------- 会话注册/发现 ----------

    @classmethod
    async def register_session(cls, session_id: str) -> None:
        """
        将 session_id 加入在线集合。建议在 chat/trigger 启动时调用。
        """
        client = await cls._ensure_client()
        await client.sadd(cls._key_sessions(), session_id)
        # 可选择设置心跳键（这里暂不做心跳，实现简化）
        logger.debug("RedisBus 注册会话: %s", session_id)

    @classmethod
    async def unregister_session(cls, session_id: str) -> None:
        """
        将 session_id 从在线集合移除。建议在 chat/trigger 退出时调用。
        """
        try:
            client = await cls._ensure_client()
            await client.srem(cls._key_sessions(), session_id)
            logger.debug("RedisBus 注销会话: %s", session_id)
        except Exception as e:
            # 退出流程不应因注销失败而中断
            logger.warning("RedisBus 注销会话失败 session_id=%s err=%r", session_id, e)

    @classmethod
    async def list_active_sessions(cls) -> List[str]:
        """
        获取所有在线的 session_id 列表。
        """
        client = await cls._ensure_client()
        members = await client.smembers(cls._key_sessions())
        # decode_responses=True 已保证为 str
        return sorted(list(members)) if members else []

    # ---------- 消息发布/订阅 ----------

    @classmethod
    async def publish_message(cls, from_session: str, target_session: str, message: str, extra: Optional[Dict[str, Any]] = None) -> int:
        """
        向目标 session 的通信频道发布消息。

        返回：发布的订阅者数量（<=0 表示可能无人订阅）
        """
        logger.info("准备发布消息: from=%s, target=%s, message=%s", from_session, target_session, message)
        try:
            client = await cls._ensure_client()
            payload = {
                "from": from_session,
                "to": target_session,
                "message": message,
                "ts": int(time.time()),
            }
            if isinstance(extra, dict):
                payload.update(extra)
            channel = cls._channel_for_session(target_session)
            logger.info("发布消息到频道: %s, payload=%s", channel, payload)
            try:
                subs = await client.publish(channel, json.dumps(payload, ensure_ascii=False))
                logger.info("RedisBus 发送通信: %s -> %s, subs=%s", from_session, target_session, subs)
                
                # 检查订阅者数量
                try:
                    numsub = await client.pubsub_numsub(channel)
                    logger.info("发布后频道订阅者数量: %s -> %s", channel, dict(numsub))
                except Exception as e:
                    logger.warning("检查发布后订阅者数量失败: %s", e)
                    
                return int(subs or 0)
            except Exception as e:
                logger.error("RedisBus 发布消息失败 channel=%s err=%r", channel, e)
                raise
        except Exception as e:
            # 如果连接失败，重新初始化客户端
            logger.warning("RedisBus 连接失败，尝试重新初始化: %s", e)
            async with cls._lock:
                if cls._client is not None:
                    try:
                        await cls._client.close()
                    except Exception:
                        pass
                    cls._client = None
            # 重新尝试连接
            client = await cls._ensure_client()
            payload = {
                "from": from_session,
                "to": target_session,
                "message": message,
                "ts": int(time.time()),
            }
            if isinstance(extra, dict):
                payload.update(extra)
            channel = cls._channel_for_session(target_session)
            logger.info("重新连接后发布消息到频道: %s, payload=%s", channel, payload)
            subs = await client.publish(channel, json.dumps(payload, ensure_ascii=False))
            logger.info("RedisBus 重新连接后发送通信: %s -> %s, subs=%s", from_session, target_session, subs)
            
            # 检查订阅者数量
            try:
                numsub = await client.pubsub_numsub(channel)
                logger.info("重新连接后发布消息，频道订阅者数量: %s -> %s", channel, dict(numsub))
            except Exception as e:
                logger.warning("检查重新连接后订阅者数量失败: %s", e)
                
            return int(subs or 0)

    @classmethod
    async def subscribe_messages(cls, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """
        订阅当前 session 的通信频道，产生一个异步迭代器，逐条返回 JSON 消息。

        用法：
            async for msg in RedisBus.subscribe_messages(session_id):
                ...
        """
        logger.info("开始订阅消息: session_id=%s", session_id)
        client = await cls._ensure_client()
        channel = cls._channel_for_session(session_id)
        logger.info("准备订阅频道: %s", channel)
        pubsub: PubSub = client.pubsub()
        await pubsub.subscribe(channel)
        logger.info("RedisBus 订阅会话频道: %s", channel)
        
        # 检查订阅状态
        try:
            channels = await client.pubsub_channels()
            logger.info("当前所有订阅频道: %s", channels)
            numsub = await client.pubsub_numsub(channel)
            logger.info("频道订阅者数量: %s -> %s", channel, dict(numsub))
        except Exception as e:
            logger.warning("检查订阅状态失败: %s", e)

        try:
            while True:
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message is None:
                        await asyncio.sleep(0.1)
                        continue
                    if message.get("type") != "message":
                        continue
                    data = message.get("data")
                    if isinstance(data, str):
                        try:
                            obj = json.loads(data)
                        except Exception as e:
                            logger.warning("RedisBus 解析消息失败: %s, data=%s", e, data)
                            obj = {"raw": data}
                    else:
                        obj = {"raw": data}
                    logger.info("RedisBus 收到消息: channel=%s, obj=%s", channel, obj)
                    yield obj
                except asyncio.CancelledError:
                    logger.info("RedisBus 订阅被取消: %s", channel)
                    raise
                except Exception as ie:
                    logger.warning("RedisBus 订阅循环异常: %r", ie)
                    logger.exception("RedisBus 订阅循环详细异常:")
                    await asyncio.sleep(0.5)
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
                logger.info("RedisBus 取消订阅频道: %s", channel)
            except Exception as e:
                logger.warning("RedisBus 取消订阅失败: %s", e)

    # ---------- 清理 ----------

    @classmethod
    async def cleanup(cls) -> None:
        """关闭底层连接（可选调用）。"""
        if cls._client is not None:
            try:
                await cls._client.close()
            except Exception:
                pass
            finally:
                cls._client = None