#!/usr/bin/env python3
"""
ADDS 代理基类和完整实现

参考：Claude Code 第2章 - 工具系统和第8章 - 工具级提示词
核心思想：每个代理有独立的职责边界和专属行为约束
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path


@dataclass
class AgentContext:
    """代理执行上下文"""
    project_root: Path
    feature_list_path: Path
    current_feature: Optional[str] = None
    current_status: Optional[str] = None
    messages: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """代理执行结果"""
    success: bool
    message: str
    actions: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    next_agent: Optional[str] = None
    next_action: Optional[str] = None
    error: Optional[str] = None


class BaseAgent(ABC):
    """
    代理基类
    
    参考：Claude Code 第2章 - Tool 接口设计
    """
    
    def __init__(self, context: AgentContext):
        self.context = context
        self.actions_log: List[str] = []
        self.evidence: Dict[str, Any] = {}
    
    @property
    @abstractmethod
    def name(self) -> str:
        """代理名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """代理描述"""
        pass
    
    @property
    @abstractmethod
    def allowed_actions(self) -> List[str]:
        """允许的操作列表"""
        pass
    
    @abstractmethod
    async def execute(self, features: List[Dict]) -> AgentResult:
        """
        执行代理任务
        
        Args:
            features: 功能列表
        
        Returns:
            执行结果
        """
        pass
    
    def log_action(self, action: str, details: str = ""):
        """记录操作"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {action}"
        if details:
            log_entry += f": {details}"
        self.actions_log.append(log_entry)
        print(f"  {log_entry}")
    
    def add_evidence(self, key: str, value: Any):
        """添加证据"""
        self.evidence[key] = value
    
    def check_boundary(self, action: str) -> bool:
        """检查操作是否在边界内"""
        if action not in self.allowed_actions:
            raise RuntimeError(
                f"❌ 代理 '{self.name}' 尝试执行越权操作: {action}\n"
                f"允许的操作: {self.allowed_actions}"
            )
        return True
    
    def get_system_prompt(self) -> str:
        """获取代理专属系统提示词"""
        # 子类可以重写此方法提供更详细的提示词
        return f"# {self.name}\n\n{self.description}"


# ==============================================================================
# PM Agent 实现
# ==============================================================================

class PMAgent(BaseAgent):
    """
    PM Agent - 产品经理代理
    
    职责：
    1. 分析用户需求
    2. 分解为原子功能（50-200个）
    3. 创建 feature_list.md
    4. 定义依赖关系和验收标准
    
    参考：ADDS 原始设计中的 PM Agent 职责
    """
    
    @property
    def name(self) -> str:
        return "PM Agent"
    
    @property
    def description(self) -> str:
        return """产品经理代理，负责需求分析和任务分解。

核心职责：
1. 理解和澄清用户需求
2. 将需求分解为可执行的原子功能
3. 定义功能间的依赖关系
4. 为每个功能设定验收标准
5. 创建和维护 feature_list.md

工作原则：
- 每个功能应该是独立可测试的
- 功能粒度：50-200行代码或1-3小时工作量
- 明确的验收标准，避免模糊描述
- 合理的依赖顺序，避免循环依赖"""

    @property
    def allowed_actions(self) -> List[str]:
        return [
            "analyze_requirements",
            "decompose_tasks",
            "create_feature_list",
            "define_dependencies",
            "set_acceptance_criteria",
            "update_feature_status"
        ]
    
    async def execute(self, features: List[Dict]) -> AgentResult:
        """执行 PM Agent 任务"""
        print(f"\n📋 {self.name} 执行中...")
        
        try:
            # 检查是否需要初始化项目
            if not self.context.feature_list_path.exists():
                self.log_action("create_feature_list", "创建初始功能列表")
                await self._create_initial_feature_list()
                self.add_evidence("files_created", [str(self.context.feature_list_path)])
                
                return AgentResult(
                    success=True,
                    message="项目初始化完成，功能列表已创建",
                    actions=self.actions_log,
                    evidence=self.evidence,
                    next_agent="architect"
                )
            
            # 检查是否需要添加新功能
            if self._should_add_features(features):
                self.log_action("analyze_requirements", "分析新需求")
                new_features = await self._analyze_new_requirements()
                
                self.log_action("decompose_tasks", f"分解为 {len(new_features)} 个功能")
                await self._add_features_to_list(new_features)
                
                self.add_evidence("features_added", len(new_features))
                
                return AgentResult(
                    success=True,
                    message=f"新增 {len(new_features)} 个功能",
                    actions=self.actions_log,
                    evidence=self.evidence,
                    next_agent="architect"
                )
            
            # 项目已完成
            if all(f['status'] == 'completed' for f in features):
                return AgentResult(
                    success=True,
                    message="所有功能已完成",
                    actions=self.actions_log,
                    evidence=self.evidence,
                    next_agent="reviewer"
                )
            
            # 默认：传递给下一个代理
            return AgentResult(
                success=True,
                message="PM 工作完成，传递给下一个代理",
                actions=self.actions_log,
                evidence=self.evidence,
                next_agent="architect"
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                message=f"PM Agent 执行失败: {str(e)}",
                error=str(e),
                actions=self.actions_log
            )
    
    async def _create_initial_feature_list(self):
        """创建初始功能列表"""
        template = """# 功能列表

> 本文档由 PM Agent 自动生成，请根据项目实际情况调整

## 项目信息
- 项目类型：web_app
- 技术栈：待 Architect Agent 确定
- 创建时间：{timestamp}

## 功能列表

### 阶段 1：基础功能

#### 功能 1: project_setup
- **描述**: 项目初始化和基础配置
- **状态**: pending
- **依赖**: 无
- **验收标准**:
  - 项目目录结构创建完成
  - 基础配置文件就绪
  - 依赖管理配置完成

#### 功能 2: database_setup
- **描述**: 数据库连接和基础模型定义
- **状态**: pending
- **依赖**: project_setup
- **验收标准**:
  - 数据库连接成功
  - 基础 ORM 模型定义
  - 迁移脚本可用

#### 功能 3: api_framework
- **描述**: API 框架搭建和基础路由
- **状态**: pending
- **依赖**: project_setup
- **验收标准**:
  - API 框架运行正常
  - 基础路由配置完成
  - 健康检查端点可用

### 阶段 2：核心功能

#### 功能 4: user_authentication
- **描述**: 用户认证功能（登录、注册、登出）
- **状态**: pending
- **依赖**: database_setup, api_framework
- **验收标准**:
  - 用户可以使用邮箱和密码注册
  - 用户可以使用邮箱和密码登录
  - 用户可以登出
  - 密码使用 bcrypt 加密存储

#### 功能 5: data_validation
- **描述**: 数据验证中间件
- **状态**: pending
- **依赖**: api_framework
- **验收标准**:
  - 输入数据格式验证
  - 业务规则验证
  - 错误信息友好提示

#### 功能 6: error_handling
- **描述**: 统一错误处理机制
- **状态**: pending
- **依赖**: api_framework
- **验收标准**:
  - 统一错误响应格式
  - 异常捕获和处理
  - 日志记录完善

---

## 统计信息
- 总功能数：6
- 待实现：6
- 进行中：0
- 测试中：0
- 已完成：0

## 依赖图
```
project_setup
├── database_setup
│   └── user_authentication
└── api_framework
    ├── data_validation
    ├── error_handling
    └── user_authentication
```
""".format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"))
        
        self.context.feature_list_path.parent.mkdir(parents=True, exist_ok=True)
        self.context.feature_list_path.write_text(template, encoding='utf-8')
    
    def _should_add_features(self, features: List[Dict]) -> bool:
        """判断是否需要添加新功能"""
        # 简化实现：检查是否有明确的用户需求
        return self.context.metadata.get('new_requirements', False)
    
    async def _analyze_new_requirements(self) -> List[Dict]:
        """分析新需求并分解为功能"""
        # 简化实现：返回示例功能
        return [
            {
                "name": "new_feature_1",
                "description": "新功能 1",
                "status": "pending",
                "dependencies": [],
                "acceptance_criteria": ["验收标准 1", "验收标准 2"]
            }
        ]
    
    async def _add_features_to_list(self, new_features: List[Dict]):
        """添加新功能到功能列表"""
        # 追加到现有文件
        with open(self.context.feature_list_path, 'a', encoding='utf-8') as f:
            for feature in new_features:
                f.write(f"\n#### 功能: {feature['name']}\n")
                f.write(f"- **描述**: {feature['description']}\n")
                f.write(f"- **状态**: {feature['status']}\n")
                f.write(f"- **依赖**: {', '.join(feature['dependencies']) or '无'}\n")
                f.write("- **验收标准**:\n")
                for criteria in feature['acceptance_criteria']:
                    f.write(f"  - {criteria}\n")


# ==============================================================================
# Architect Agent 实现
# ==============================================================================

class ArchitectAgent(BaseAgent):
    """
    Architect Agent - 架构师代理
    
    职责：
    1. 技术架构设计
    2. 技术栈选择
    3. 目录结构定义
    4. 技术决策文档
    
    参考：Claude Code 第1章 - 三层架构
    """
    
    @property
    def name(self) -> str:
        return "Architect Agent"
    
    @property
    def description(self) -> str:
        return """架构师代理，负责技术架构设计。

核心职责：
1. 根据项目需求选择技术栈
2. 设计系统架构和模块划分
3. 定义目录结构和文件组织
4. 制定技术决策和规范
5. 创建架构文档

工作原则：
- 选择成熟稳定的技术栈
- 模块职责清晰，低耦合
- 目录结构符合项目规模
- 技术决策有充分理由"""

    @property
    def allowed_actions(self) -> List[str]:
        return [
            "design_architecture",
            "select_tech_stack",
            "define_structure",
            "create_architecture_doc",
            "define_coding_standards"
        ]
    
    async def execute(self, features: List[Dict]) -> AgentResult:
        """执行 Architect Agent 任务"""
        print(f"\n🏗️  {self.name} 执行中...")
        
        try:
            # 检查是否已有架构设计
            arch_doc_path = self.context.project_root / ".ai" / "architecture.md"
            
            if not arch_doc_path.exists():
                self.log_action("design_architecture", "设计系统架构")
                await self._create_architecture_document()
                
                self.log_action("define_structure", "定义目录结构")
                await self._create_directory_structure()
                
                self.add_evidence("files_created", [str(arch_doc_path)])
                self.add_evidence("directories_created", ["src", "tests", "docs"])
                
                return AgentResult(
                    success=True,
                    message="架构设计完成",
                    actions=self.actions_log,
                    evidence=self.evidence,
                    next_agent="developer"
                )
            
            # 已有架构，直接传递
            return AgentResult(
                success=True,
                message="架构设计已存在",
                actions=self.actions_log,
                evidence=self.evidence,
                next_agent="developer"
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                message=f"Architect Agent 执行失败: {str(e)}",
                error=str(e),
                actions=self.actions_log
            )
    
    async def _create_architecture_document(self):
        """创建架构文档"""
        arch_doc = """# 系统架构设计

> 本文档由 Architect Agent 自动生成

## 1. 技术栈选择

### 后端
- **语言**: Python 3.11+
- **框架**: FastAPI
- **ORM**: SQLAlchemy
- **数据库**: PostgreSQL
- **缓存**: Redis

### 前端（如果需要）
- **框架**: React
- **状态管理**: Redux Toolkit
- **UI 库**: Material-UI

### 开发工具
- **包管理**: Poetry
- **代码格式化**: Black, isort
- **类型检查**: mypy
- **测试**: pytest

## 2. 系统架构

```
┌─────────────────────────────────────────┐
│            API Gateway                   │
├─────────────────────────────────────────┤
│  Auth │  User  │  Data  │  Error        │
│  模块  │  模块  │  模块   │  处理         │
├─────────────────────────────────────────┤
│         Business Logic Layer            │
├─────────────────────────────────────────┤
│         Data Access Layer               │
├─────────────────────────────────────────┤
│    PostgreSQL    │    Redis Cache       │
└─────────────────────────────────────────┘
```

## 3. 目录结构

```
project/
├── src/
│   ├── api/              # API 路由
│   ├── models/           # 数据模型
│   ├── services/         # 业务逻辑
│   ├── repositories/     # 数据访问
│   ├── middleware/       # 中间件
│   └── utils/            # 工具函数
├── tests/
│   ├── unit/             # 单元测试
│   ├── integration/      # 集成测试
│   └── fixtures/         # 测试数据
├── docs/                 # 文档
├── scripts/              # 脚本
├── .ai/                  # ADDS 元数据
└── config/               # 配置文件
```

## 4. 技术决策

### 为什么选择 FastAPI？
- 异步支持，性能优秀
- 自动 API 文档生成
- 类型提示友好
- 社区活跃

### 为什么选择 PostgreSQL？
- 成熟稳定的关系型数据库
- 支持 JSON 类型
- 事务处理可靠
- 生态完善

## 5. 编码规范

### 命名规范
- 文件名：snake_case
- 类名：PascalCase
- 函数名：snake_case
- 常量：UPPER_SNAKE_CASE

### 文档规范
- 所有公共函数必须有 docstring
- 使用 Google 风格的 docstring
- 类型注解必须完整

### 测试规范
- 测试覆盖率 >= 80%
- 每个模块至少一个测试文件
- 使用 pytest fixtures 管理测试数据
"""
        
        arch_doc_path = self.context.project_root / ".ai" / "architecture.md"
        arch_doc_path.parent.mkdir(parents=True, exist_ok=True)
        arch_doc_path.write_text(arch_doc, encoding='utf-8')
    
    async def _create_directory_structure(self):
        """创建目录结构"""
        directories = [
            "src/api",
            "src/models",
            "src/services",
            "src/repositories",
            "src/middleware",
            "src/utils",
            "tests/unit",
            "tests/integration",
            "tests/fixtures",
            "docs",
            "scripts",
            "config"
        ]
        
        for dir_path in directories:
            full_path = self.context.project_root / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            # 创建 __init__.py
            if dir_path.startswith("src/") or dir_path.startswith("tests/"):
                (full_path / "__init__.py").touch()


# ==============================================================================
# Developer Agent 实现
# ==============================================================================

class DeveloperAgent(BaseAgent):
    """
    Developer Agent - 开发者代理
    
    职责：
    1. 实现单个功能
    2. 编写单元测试
    3. 更新功能状态
    4. 提供实现证据
    
    参考：ADDS 核心原则 - 一次一个功能
    """
    
    @property
    def name(self) -> str:
        return "Developer Agent"
    
    @property
    def description(self) -> str:
        return """开发者代理，负责功能实现。

核心职责：
1. 选择一个待实现的功能（pending 状态）
2. 实现代码逻辑
3. 编写单元测试
4. 更新功能状态为 testing
5. 记录实现证据

工作原则：
- 一次只实现一个功能（核心约束）
- 必须先读取 feature_list.md
- 遵循架构设计和技术规范
- 代码必须有对应的测试
- 所有修改必须记录证据"""

    @property
    def allowed_actions(self) -> List[str]:
        return [
            "read_feature_list",
            "select_feature",
            "implement_feature",
            "write_unit_tests",
            "update_status",
            "record_evidence"
        ]
    
    async def execute(self, features: List[Dict]) -> AgentResult:
        """执行 Developer Agent 任务"""
        print(f"\n💻 {self.name} 执行中...")
        
        try:
            # 选择待实现功能
            pending_features = [f for f in features if f['status'] == 'pending']
            
            if not pending_features:
                return AgentResult(
                    success=True,
                    message="无待实现功能",
                    actions=self.actions_log,
                    evidence=self.evidence,
                    next_agent="tester"
                )
            
            # 选择第一个 pending 功能
            feature = pending_features[0]
            self.log_action("select_feature", f"选择功能: {feature['name']}")
            
            # 模拟实现
            self.log_action("implement_feature", f"实现功能: {feature['name']}")
            await self._implement_feature(feature)
            
            # 编写测试
            self.log_action("write_unit_tests", f"编写测试: {feature['name']}")
            await self._write_tests(feature)
            
            # 更新状态
            self.log_action("update_status", f"状态: pending → testing")
            feature['status'] = 'testing'
            
            # 记录证据
            self.add_evidence("feature_implemented", feature['name'])
            self.add_evidence("files_modified", [f"src/services/{feature['name']}.py"])
            self.add_evidence("tests_created", [f"tests/unit/test_{feature['name']}.py"])
            
            return AgentResult(
                success=True,
                message=f"功能 '{feature['name']}' 实现完成",
                actions=self.actions_log,
                evidence=self.evidence,
                next_agent="tester"
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                message=f"Developer Agent 执行失败: {str(e)}",
                error=str(e),
                actions=self.actions_log
            )
    
    async def _implement_feature(self, feature: Dict):
        """实现功能（模拟）"""
        # 在实际实现中，这里会调用代码生成工具
        # 这里只是模拟
        await self._simulate_delay()
    
    async def _write_tests(self, feature: Dict):
        """编写测试（模拟）"""
        # 在实际实现中，这里会生成测试代码
        await self._simulate_delay()
    
    async def _simulate_delay(self):
        """模拟延迟"""
        import asyncio
        await asyncio.sleep(0.1)


# ==============================================================================
# Tester Agent 实现
# ==============================================================================

class TesterAgent(BaseAgent):
    """
    Tester Agent - 测试者代理
    
    职责：
    1. 验证功能正确性
    2. 检测回归
    3. 更新功能状态
    
    参考：ADDS 核心原则 - 回归保护
    """
    
    @property
    def name(self) -> str:
        return "Tester Agent"
    
    @property
    def description(self) -> str:
        return """测试者代理，负责功能验证。

核心职责：
1. 选择待测试功能（testing 状态）
2. 运行测试套件
3. 检测回归
4. 更新功能状态为 completed 或 bug
5. 记录测试证据

工作原则：
- 必须运行实际测试，不能假设通过
- 检测回归：新功能不应破坏旧功能
- 测试失败必须记录原因
- 所有测试结果必须有证据"""

    @property
    def allowed_actions(self) -> List[str]:
        return [
            "read_feature_list",
            "select_testing_feature",
            "run_tests",
            "check_regression",
            "update_status",
            "record_evidence"
        ]
    
    async def execute(self, features: List[Dict]) -> AgentResult:
        """执行 Tester Agent 任务"""
        print(f"\n🧪 {self.name} 执行中...")
        
        try:
            # 选择待测试功能
            testing_features = [f for f in features if f['status'] == 'testing']
            
            if not testing_features:
                return AgentResult(
                    success=True,
                    message="无待测试功能",
                    actions=self.actions_log,
                    evidence=self.evidence,
                    next_agent="reviewer"
                )
            
            # 选择第一个 testing 功能
            feature = testing_features[0]
            self.log_action("select_testing_feature", f"选择功能: {feature['name']}")
            
            # 运行测试
            self.log_action("run_tests", f"运行测试: {feature['name']}")
            test_passed = await self._run_tests(feature)
            
            # 检测回归
            self.log_action("check_regression", "检测回归")
            regression_detected = await self._check_regression(features)
            
            # 更新状态
            if test_passed and not regression_detected:
                self.log_action("update_status", f"状态: testing → completed")
                feature['status'] = 'completed'
                status_msg = "completed"
            else:
                self.log_action("update_status", f"状态: testing → bug")
                feature['status'] = 'bug'
                status_msg = "bug"
            
            # 记录证据
            self.add_evidence("feature_tested", feature['name'])
            self.add_evidence("test_result", "PASS" if test_passed else "FAIL")
            self.add_evidence("regression_detected", regression_detected)
            
            return AgentResult(
                success=True,
                message=f"功能 '{feature['name']}' 测试完成，状态: {status_msg}",
                actions=self.actions_log,
                evidence=self.evidence,
                next_agent=None  # 由系统决定下一个代理
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                message=f"Tester Agent 执行失败: {str(e)}",
                error=str(e),
                actions=self.actions_log
            )
    
    async def _run_tests(self, feature: Dict) -> bool:
        """运行测试（模拟）"""
        # 在实际实现中，这里会调用 pytest 或其他测试工具
        await self._simulate_delay()
        return True  # 模拟测试通过
    
    async def _check_regression(self, features: List[Dict]) -> bool:
        """检测回归（模拟）"""
        # 在实际实现中，这里会运行旧功能的测试
        await self._simulate_delay()
        return False  # 模拟无回归
    
    async def _simulate_delay(self):
        """模拟延迟"""
        import asyncio
        await asyncio.sleep(0.1)


# ==============================================================================
# Reviewer Agent 实现
# ==============================================================================

class ReviewerAgent(BaseAgent):
    """
    Reviewer Agent - 审查者代理
    
    职责：
    1. 代码审查
    2. 安全审计
    3. 性能评估
    
    参考：Claude Code 第16章 - 安全与权限
    """
    
    @property
    def name(self) -> str:
        return "Reviewer Agent"
    
    @property
    def description(self) -> str:
        return """审查者代理，负责代码审查。

核心职责：
1. 代码风格一致性检查
2. 安全漏洞扫描
3. 性能瓶颈检测
4. 文档完整性验证
5. 生成审查报告

工作原则：
- 使用自动化工具（linter, 安全扫描器）
- 人工审查关键代码逻辑
- 记录所有发现的问题
- 提供改进建议"""

    @property
    def allowed_actions(self) -> List[str]:
        return [
            "read_feature_list",
            "code_review",
            "security_audit",
            "performance_eval",
            "generate_report"
        ]
    
    async def execute(self, features: List[Dict]) -> AgentResult:
        """执行 Reviewer Agent 任务"""
        print(f"\n🔍 {self.name} 执行中...")
        
        try:
            # 检查是否所有功能已完成
            if not all(f['status'] == 'completed' for f in features):
                return AgentResult(
                    success=True,
                    message="尚有功能未完成，跳过审查",
                    actions=self.actions_log,
                    evidence=self.evidence,
                    next_agent="developer"
                )
            
            # 代码审查
            self.log_action("code_review", "代码风格检查")
            code_issues = await self._code_review()
            
            # 安全审计
            self.log_action("security_audit", "安全漏洞扫描")
            security_issues = await self._security_audit()
            
            # 性能评估
            self.log_action("performance_eval", "性能分析")
            performance_issues = await self._performance_eval()
            
            # 生成报告
            self.log_action("generate_report", "生成审查报告")
            await self._generate_report(code_issues, security_issues, performance_issues)
            
            # 记录证据
            self.add_evidence("code_issues", len(code_issues))
            self.add_evidence("security_issues", len(security_issues))
            self.add_evidence("performance_issues", len(performance_issues))
            
            return AgentResult(
                success=True,
                message="审查完成",
                actions=self.actions_log,
                evidence=self.evidence,
                next_agent=None  # 项目完成
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                message=f"Reviewer Agent 执行失败: {str(e)}",
                error=str(e),
                actions=self.actions_log
            )
    
    async def _code_review(self) -> List[str]:
        """代码审查（模拟）"""
        await self._simulate_delay()
        return ["代码风格问题 1", "代码风格问题 2"]
    
    async def _security_audit(self) -> List[str]:
        """安全审计（模拟）"""
        await self._simulate_delay()
        return ["安全问题 1"]
    
    async def _performance_eval(self) -> List[str]:
        """性能评估（模拟）"""
        await self._simulate_delay()
        return ["性能问题 1"]
    
    async def _generate_report(self, code_issues, security_issues, performance_issues):
        """生成审查报告"""
        report = f"""# 代码审查报告

> 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 总体评估

- 代码问题: {len(code_issues)}
- 安全问题: {len(security_issues)}
- 性能问题: {len(performance_issues)}

## 详细问题

### 代码风格问题
{chr(10).join(f'- {issue}' for issue in code_issues)}

### 安全问题
{chr(10).join(f'- {issue}' for issue in security_issues)}

### 性能问题
{chr(10).join(f'- {issue}' for issue in performance_issues)}

## 改进建议

1. 修复所有安全问题（优先级最高）
2. 优化性能瓶颈
3. 统一代码风格
"""
        
        report_path = self.context.project_root / ".ai" / "review_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding='utf-8')
    
    async def _simulate_delay(self):
        """模拟延迟"""
        import asyncio
        await asyncio.sleep(0.1)


# ==============================================================================
# 代理工厂
# ==============================================================================

def create_agent(agent_type: str, context: AgentContext) -> BaseAgent:
    """
    创建代理实例
    
    Args:
        agent_type: 代理类型 (pm, architect, developer, tester, reviewer)
        context: 执行上下文
    
    Returns:
        代理实例
    """
    agents = {
        "pm": PMAgent,
        "architect": ArchitectAgent,
        "developer": DeveloperAgent,
        "tester": TesterAgent,
        "reviewer": ReviewerAgent
    }
    
    agent_class = agents.get(agent_type)
    if not agent_class:
        raise ValueError(f"未知代理类型: {agent_type}")
    
    return agent_class(context)


# ==============================================================================
# 测试代码
# ==============================================================================

async def test_agents():
    """测试所有代理"""
    from pathlib import Path
    import tempfile
    
    # 创建临时项目目录
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        context = AgentContext(
            project_root=project_root,
            feature_list_path=project_root / ".ai" / "feature_list.md"
        )
        
        # 测试 PM Agent
        pm_agent = create_agent("pm", context)
        result = await pm_agent.execute([])
        print(f"\nPM Agent 结果: {result.message}")
        
        # 测试 Architect Agent
        arch_agent = create_agent("architect", context)
        result = await arch_agent.execute([])
        print(f"\nArchitect Agent 结果: {result.message}")
        
        # 测试 Developer Agent
        dev_agent = create_agent("developer", context)
        result = await dev_agent.execute([{"name": "test_feature", "status": "pending"}])
        print(f"\nDeveloper Agent 结果: {result.message}")
        
        # 测试 Tester Agent
        test_agent = create_agent("tester", context)
        result = await test_agent.execute([{"name": "test_feature", "status": "testing"}])
        print(f"\nTester Agent 结果: {result.message}")
        
        # 测试 Reviewer Agent
        rev_agent = create_agent("reviewer", context)
        result = await rev_agent.execute([{"name": "test_feature", "status": "completed"}])
        print(f"\nReviewer Agent 结果: {result.message}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_agents())
