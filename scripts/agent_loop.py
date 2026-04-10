#!/usr/bin/env python3
"""
ADDS Agent Loop 状态机

参考：Claude Code 第3章 - Agent Loop
核心思想：从"依赖 AI 判断"变为"显式状态转换"
"""

import asyncio
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

from model.base import ModelInterface


# ============================================================================
# 状态类型定义
# ============================================================================

class AgentType(Enum):
    """代理类型"""
    PM = "pm"
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    TESTER = "tester"
    REVIEWER = "reviewer"


class FeatureStatus(Enum):
    """功能状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    TESTING = "testing"
    COMPLETED = "completed"
    BUG = "bug"


class ContinueReason(Enum):
    """继续原因"""
    NEXT_TURN = "next_turn"
    AGENT_SWITCH = "agent_switch"
    FEATURE_COMPLETE = "feature_complete"
    REGRESSION_DETECTED = "regression_detected"
    RECOVERY_RETRY = "recovery_retry"


class TerminalReason(Enum):
    """终止原因"""
    ALL_COMPLETED = "all_completed"
    USER_ABORT = "user_abort"
    BLOCKING_ERROR = "blocking_error"
    MAX_TURNS = "max_turns"
    LOOP_DETECTED = "loop_detected"


# ============================================================================
# 状态数据结构
# ============================================================================

@dataclass
class Feature:
    """功能定义"""
    name: str
    description: str
    status: FeatureStatus = FeatureStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)


@dataclass
class State:
    """
    会话状态 - 跨迭代传递
    
    参考：Claude Code 第3章 - State 类型
    """
    # 当前状态
    current_agent: AgentType = AgentType.PM
    current_feature: Optional[str] = None
    current_feature_status: Optional[FeatureStatus] = None
    
    # 消息历史
    messages: List[Dict[str, Any]] = field(default_factory=list)
    
    # 迭代控制
    turn_count: int = 0
    max_turns: int = 50
    
    # 锁存字段（一旦确定，会话内不变）
    project_type: Optional[str] = None
    tech_stack: Optional[List[str]] = None
    initial_feature_count: int = 0
    
    # 恢复追踪
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3
    consecutive_failures: int = 0
    max_consecutive_failures: int = 3
    
    # 时间戳
    session_start: datetime = field(default_factory=datetime.now)
    last_turn_time: Optional[datetime] = None


# ============================================================================
# 锁存机制
# ============================================================================

class ProjectLatches:
    """
    项目级锁存器 - 会话内不变
    
    参考：Claude Code 第13章 - Beta Header 锁存
    """
    
    def __init__(self):
        self._project_type_latched = False
        self._tech_stack_latched = False
        self._initial_feature_count_latched = False
    
    def latch_project_type(self, state: State, project_type: str):
        """首次确定后，会话内不再变化"""
        if not self._project_type_latched:
            state.project_type = project_type
            self._project_type_latched = True
            print(f"✅ 锁存项目类型: {project_type}")
    
    def latch_tech_stack(self, state: State, tech_stack: List[str]):
        """技术栈一旦确定，不再变化"""
        if not self._tech_stack_latched:
            state.tech_stack = tech_stack
            self._tech_stack_latched = True
            print(f"✅ 锁存技术栈: {tech_stack}")
    
    def latch_initial_feature_count(self, state: State, count: int):
        """初始功能数量锁定"""
        if not self._initial_feature_count_latched:
            state.initial_feature_count = count
            self._initial_feature_count_latched = True
            print(f"✅ 锁存初始功能数量: {count}")


class FeatureStateLatches:
    """
    功能状态锁存 - 防止状态抖动
    
    参考：Claude Code 第13章 - TTL 资格锁存
    """
    
    def __init__(self):
        self._current_feature_latched = False
    
    def latch_current_feature(self, state: State, feature_name: str):
        """当前功能一旦开始，不允许中途切换"""
        if not self._current_feature_latched:
            state.current_feature = feature_name
            state.current_feature_status = FeatureStatus.IN_PROGRESS
            self._current_feature_latched = True
            print(f"✅ 锁存当前功能: {feature_name}")
        elif state.current_feature != feature_name:
            # 拒绝切换 - 保护当前功能
            raise RuntimeError(
                f"❌ 功能状态锁存保护: 当前功能 '{state.current_feature}' 正在进行中，"
                f"禁止切换到 '{feature_name}'"
            )
    
    def release_feature(self, state: State):
        """功能完成后释放锁存"""
        if self._current_feature_latched:
            self._current_feature_latched = False
            state.current_feature = None
            state.current_feature_status = None
            print("🔓 释放功能锁存")


# ============================================================================
# 失败关闭机制
# ============================================================================

class SafetyDefaults:
    """
    失败关闭 - 默认最安全行为
    
    参考：Claude Code 第2章 - Tool 接口
    """
    
    @staticmethod
    def safe_feature_selection(features: List[Feature]) -> Feature:
        """
        安全的功能选择
        
        默认：选择第一个 pending 功能
        失败时：停止而非猜测
        """
        pending = [f for f in features if f.status == FeatureStatus.PENDING]
        
        if not pending:
            raise RuntimeError(
                "❌ 无待处理功能: ADDS 要求至少有一个 pending 状态的功能才能继续。"
                "请检查 feature_list.md 或运行 'adds init' 初始化项目。"
            )
        
        # 安全默认：第一个 pending 功能
        selected = pending[0]
        print(f"✅ 安全选择功能: {selected.name} (第一个 pending)")
        return selected
    
    @staticmethod
    def safe_status_transition(current: FeatureStatus, target: FeatureStatus) -> bool:
        """
        安全的状态转换
        
        默认：只允许合法转换
        失败时：拒绝而非猜测
        """
        valid_transitions = {
            FeatureStatus.PENDING: [FeatureStatus.IN_PROGRESS],
            FeatureStatus.IN_PROGRESS: [FeatureStatus.TESTING, FeatureStatus.BUG],
            FeatureStatus.TESTING: [FeatureStatus.COMPLETED, FeatureStatus.BUG],
            FeatureStatus.BUG: [FeatureStatus.IN_PROGRESS],
            FeatureStatus.COMPLETED: []  # 终态
        }
        
        if target not in valid_transitions.get(current, []):
            raise RuntimeError(
                f"❌ 非法状态转换: {current.value} → {target.value}\n"
                f"合法目标: {[s.value for s in valid_transitions.get(current, [])]}"
            )
        
        print(f"✅ 合法状态转换: {current.value} → {target.value}")
        return True
    
    @staticmethod
    def safe_agent_selection(state: State, features: List[Feature]) -> AgentType:
        """
        安全的代理选择
        
        默认：基于规则的确定性选择
        失败时：回退到 PM Agent
        """
        # 规则 1：项目未初始化 → PM Agent
        if state.project_type is None:
            print("✅ 代理选择: PM Agent (项目未初始化)")
            return AgentType.PM
        
        # 规则 2：无架构设计 → Architect Agent
        # (简化实现，实际需要检查架构文件)
        
        # 规则 3：有 pending 功能 → Developer Agent
        pending_features = [f for f in features if f.status == FeatureStatus.PENDING]
        if pending_features:
            print(f"✅ 代理选择: Developer Agent (有 {len(pending_features)} 个 pending 功能)")
            return AgentType.DEVELOPER
        
        # 规则 4：有 testing 功能 → Tester Agent
        testing_features = [f for f in features if f.status == FeatureStatus.TESTING]
        if testing_features:
            print(f"✅ 代理选择: Tester Agent (有 {len(testing_features)} 个 testing 功能)")
            return AgentType.TESTER
        
        # 规则 5：所有功能 completed → Reviewer Agent
        if all(f.status == FeatureStatus.COMPLETED for f in features):
            print("✅ 代理选择: Reviewer Agent (所有功能已完成)")
            return AgentType.REVIEWER
        
        # 失败关闭：默认 PM Agent
        print("⚠️  代理选择: PM Agent (默认回退)")
        return AgentType.PM


# ============================================================================
# Agent Loop 主循环
# ============================================================================

class ADDSAgentLoop:
    """
    ADDS 主循环 - 显式状态机
    
    参考：Claude Code 第3章 - queryLoop
    """
    
    def __init__(self):
        self.state = State()
        self.project_latches = ProjectLatches()
        self.feature_latches = FeatureStateLatches()
        self.safety = SafetyDefaults()
        self.model: Optional[ModelInterface] = None  # 注入模型
        
    async def run(self, initial_features: List[Feature]):
        """
        主循环入口
        
        对应 Claude Code 的 query() 函数
        """
        print("=" * 80)
        print("🚀 ADDS Agent Loop 启动")
        print("=" * 80)
        
        # 锁存初始状态
        self.project_latches.latch_initial_feature_count(self.state, len(initial_features))
        
        # 进入主循环
        result = await self._loop(initial_features)
        
        print("\n" + "=" * 80)
        print(f"🏁 ADDS Agent Loop 终止: {result}")
        print("=" * 80)
        return result
    
    async def _loop(self, features: List[Feature]) -> TerminalReason:
        """
        主循环 - while (true) 状态机
        
        对应 Claude Code 的 queryLoop() 函数
        """
        while True:
            self.state.turn_count += 1
            self.state.last_turn_time = datetime.now()
            
            print(f"\n{'=' * 80}")
            print(f"📍 迭代 #{self.state.turn_count}")
            print(f"   当前代理: {self.state.current_agent.value}")
            print(f"   当前功能: {self.state.current_feature or 'None'}")
            print("=" * 80)
            
            # === 阶段 1：上下文预处理 ===
            self._preprocess_context()
            
            # === 阶段 2：路由决策 ===
            next_agent = self.safety.safe_agent_selection(self.state, features)
            if next_agent != self.state.current_agent:
                print(f"🔄 代理切换: {self.state.current_agent.value} → {next_agent.value}")
                self.state.current_agent = next_agent
            
            # === 阶段 3：执行当前代理 ===
            try:
                result = await self._execute_agent(features)
            except Exception as e:
                print(f"❌ 代理执行失败: {e}")
                self.state.consecutive_failures += 1
                
                if self.state.consecutive_failures >= self.state.max_consecutive_failures:
                    return TerminalReason.LOOP_DETECTED
                
                self.state.recovery_attempts += 1
                if self.state.recovery_attempts > self.state.max_recovery_attempts:
                    return TerminalReason.BLOCKING_ERROR
                
                continue
            
            # 成功执行，重置失败计数
            self.state.consecutive_failures = 0
            
            # === 阶段 4：终止判定 ===
            terminal = self._check_termination(features)
            if terminal:
                return terminal
            
            # === 阶段 5：继续判定 ===
            continue_reason = self._check_continue(features)
            if continue_reason:
                print(f"➡️  继续: {continue_reason.value}")
            
            # === 阶段 6：轮次限制检查 ===
            if self.state.turn_count >= self.state.max_turns:
                return TerminalReason.MAX_TURNS
            
            # 模拟异步
            await asyncio.sleep(0.1)
    
    def _preprocess_context(self):
        """
        上下文预处理
        
        参考：Claude Code 第3章 - 五级处理管线
        """
        # 检查环境健康
        print("🔍 检查环境健康...")
        # (简化实现)
        print("✅ 环境健康")
    
    async def _execute_agent(self, features: List[Feature]) -> Dict:
        """
        执行当前代理
        
        根据代理类型执行不同逻辑
        """
        agent = self.state.current_agent
        
        if agent == AgentType.PM:
            return await self._execute_pm_agent(features)
        elif agent == AgentType.DEVELOPER:
            return await self._execute_developer_agent(features)
        elif agent == AgentType.TESTER:
            return await self._execute_tester_agent(features)
        elif agent == AgentType.REVIEWER:
            return await self._execute_reviewer_agent(features)
        else:
            raise RuntimeError(f"未实现的代理类型: {agent}")
    
    async def _execute_pm_agent(self, features: List[Feature]) -> Dict:
        """PM Agent: 需求分析和任务分解"""
        print("\n📋 PM Agent 执行中...")
        
        # 模拟：设置项目类型
        self.project_latches.latch_project_type(self.state, "web_app")
        self.project_latches.latch_tech_stack(self.state, ["Python", "FastAPI"])
        
        print("✅ PM Agent 完成: 需求分析完成")
        return {"status": "completed"}
    
    async def _execute_developer_agent(self, features: List[Feature]) -> Dict:
        """Developer Agent: 功能实现"""
        print("\n💻 Developer Agent 执行中...")
        
        # 选择功能
        selected = self.safety.safe_feature_selection(features)
        
        # 锁存当前功能
        self.feature_latches.latch_current_feature(self.state, selected.name)
        
        # 模拟：状态转换
        self.safety.safe_status_transition(selected.status, FeatureStatus.IN_PROGRESS)
        selected.status = FeatureStatus.IN_PROGRESS
        
        # 如果有模型，调用模型获取实现建议
        if self.model:
            try:
                messages = [
                    {"role": "user", "content": f"请实现功能: {selected.name}\n描述: {selected.description}"}
                ]
                print(f"  📡 调用模型: {self.model.get_model_name()}")
                async for response in self.model.chat(messages, stream=False):
                    if response.finish_reason == "error":
                        print(f"  ⚠️  模型调用失败: {response.content[:200]}")
                    elif response.content:
                        print(f"  📝 模型响应: {response.content[:200]}...")
                    break  # 非流式，只需第一个响应
            except Exception as e:
                print(f"  ⚠️  模型调用异常: {e}")
        
        print(f"✅ Developer Agent 完成: 功能 '{selected.name}' 实现完成")
        
        # 模拟：测试通过，更新状态
        self.safety.safe_status_transition(selected.status, FeatureStatus.TESTING)
        selected.status = FeatureStatus.TESTING
        
        # 释放功能锁存
        self.feature_latches.release_feature(self.state)
        
        return {"status": "completed", "feature": selected.name}
    
    async def _execute_tester_agent(self, features: List[Feature]) -> Dict:
        """Tester Agent: 测试验证"""
        print("\n🧪 Tester Agent 执行中...")
        
        # 找到 testing 状态的功能
        testing_features = [f for f in features if f.status == FeatureStatus.TESTING]
        if not testing_features:
            raise RuntimeError("无 testing 状态的功能")
        
        feature = testing_features[0]
        
        # 模拟：测试通过
        self.safety.safe_status_transition(feature.status, FeatureStatus.COMPLETED)
        feature.status = FeatureStatus.COMPLETED
        
        print(f"✅ Tester Agent 完成: 功能 '{feature.name}' 测试通过")
        return {"status": "completed", "feature": feature.name}
    
    async def _execute_reviewer_agent(self, features: List[Feature]) -> Dict:
        """Reviewer Agent: 代码审查"""
        print("\n🔍 Reviewer Agent 执行中...")
        print("✅ Reviewer Agent 完成: 所有代码审查通过")
        return {"status": "completed"}
    
    def _check_termination(self, features: List[Feature]) -> Optional[TerminalReason]:
        """
        终止判定
        
        参考：Claude Code 第3章 - Terminal 类型
        """
        # 检查是否所有功能完成
        if all(f.status == FeatureStatus.COMPLETED for f in features):
            return TerminalReason.ALL_COMPLETED
        
        return None
    
    def _check_continue(self, features: List[Feature]) -> Optional[ContinueReason]:
        """
        继续判定
        """
        # 有 pending 功能
        if any(f.status == FeatureStatus.PENDING for f in features):
            return ContinueReason.NEXT_TURN
        
        # 有 testing 功能
        if any(f.status == FeatureStatus.TESTING for f in features):
            return ContinueReason.NEXT_TURN
        
        return None


# ============================================================================
# 测试入口
# ============================================================================

async def main():
    """测试 Agent Loop"""
    
    # 创建测试功能列表
    features = [
        Feature(
            name="user_authentication",
            description="用户认证功能",
            status=FeatureStatus.PENDING
        ),
        Feature(
            name="data_validation",
            description="数据验证功能",
            status=FeatureStatus.PENDING
        ),
        Feature(
            name="api_endpoints",
            description="API 端点功能",
            status=FeatureStatus.PENDING
        ),
    ]
    
    # 创建并运行 Agent Loop
    loop = ADDSAgentLoop()
    result = await loop.run(features)
    
    print(f"\n最终结果: {result.value}")
    print(f"功能状态:")
    for f in features:
        print(f"  - {f.name}: {f.status.value}")


if __name__ == "__main__":
    asyncio.run(main())
