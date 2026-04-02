#!/usr/bin/env python3
"""
ADDS 规范遵循追踪器

参考：Claude Code 第14章 - 缓存中断检测
核心思想：监控 AI 是否遵循规范，而非依赖 AI 自觉
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum
import json


class ViolationType(Enum):
    """违规类型"""
    MULTIPLE_FEATURES_PER_SESSION = "multiple_features_per_session"
    MISSING_FEATURE_LIST = "missing_feature_list"
    INVALID_STATUS_TRANSITION = "invalid_status_transition"
    AGENT_BOUNDARY_VIOLATION = "agent_boundary_violation"
    MISSING_EVIDENCE = "missing_evidence"
    STATE_DRIVEN_VIOLATION = "state_driven_violation"
    SAFETY_CONSTRAINT_VIOLATION = "safety_constraint_violation"
    REGRESSION_DETECTED = "regression_detected"


@dataclass
class Violation:
    """违规记录"""
    type: ViolationType
    details: str
    timestamp: datetime = field(default_factory=datetime.now)
    severity: str = "warning"  # warning, error, critical
    feature_name: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity,
            "feature_name": self.feature_name
        }


@dataclass
class ComplianceMetrics:
    """合规性指标"""
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    compliance_score: float = 1.0
    
    violations: List[Violation] = field(default_factory=list)
    
    # 按类型统计
    violations_by_type: Dict[str, int] = field(default_factory=dict)
    
    def record_violation(self, violation: Violation):
        """记录违规"""
        self.violations.append(violation)
        self.failed_checks += 1
        self.total_checks += 1
        
        # 更新统计
        vtype = violation.type.value
        self.violations_by_type[vtype] = self.violations_by_type.get(vtype, 0) + 1
        
        # 降低合规分数
        if violation.severity == "critical":
            self.compliance_score *= 0.5
        elif violation.severity == "error":
            self.compliance_score *= 0.7
        else:
            self.compliance_score *= 0.9
    
    def record_pass(self):
        """记录通过"""
        self.passed_checks += 1
        self.total_checks += 1
    
    def get_summary(self) -> Dict:
        """获取摘要"""
        return {
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "pass_rate": self.passed_checks / max(self.total_checks, 1),
            "compliance_score": self.compliance_score,
            "violations_count": len(self.violations),
            "violations_by_type": self.violations_by_type
        }


class ComplianceTracker:
    """
    规范遵循追踪器
    
    参考：Claude Code 第14章 - 缓存中断检测系统
    
    核心思想：
    1. 不依赖 AI 自觉报告违规
    2. 主动检测是否遵循规范
    3. 记录证据，而非依赖 AI 声称
    """
    
    def __init__(self):
        self.metrics = ComplianceMetrics()
        self.session_features: List[str] = []  # 本会话已处理的功能
        self.current_feature: Optional[str] = None
        
    def check_one_feature_per_session(self, feature_name: str) -> bool:
        """
        检查：一次只实现一个功能
        
        参考：ADDS 核心原则
        """
        if feature_name in self.session_features:
            # 功能已完成，允许再次处理（如修复 bug）
            return True
        
        if self.current_feature is not None and feature_name != self.current_feature:
            # 当前有功能正在进行，不允许切换
            self.metrics.record_violation(Violation(
                type=ViolationType.MULTIPLE_FEATURES_PER_SESSION,
                details=f"当前功能 '{self.current_feature}' 正在进行中，尝试切换到 '{feature_name}'",
                severity="critical",
                feature_name=feature_name
            ))
            return False
        
        self.current_feature = feature_name
        self.metrics.record_pass()
        return True
    
    def check_feature_list_exists(self, feature_list_path: str = ".ai/feature_list.md") -> bool:
        """
        检查：状态驱动 - feature_list.md 必须存在
        
        参考：ADDS 核心原则
        """
        import os
        
        if not os.path.exists(feature_list_path):
            self.metrics.record_violation(Violation(
                type=ViolationType.MISSING_FEATURE_LIST,
                details=f"feature_list.md 不存在于 {feature_list_path} - AI 跳过了状态检查",
                severity="critical"
            ))
            return False
        
        self.metrics.record_pass()
        return True
    
    def check_valid_status_transition(
        self,
        current_status: str,
        target_status: str,
        feature_name: str
    ) -> bool:
        """
        检查：合法的状态转换
        
        参考：ADDS 核心原则
        """
        valid_transitions = {
            "pending": ["in_progress"],
            "in_progress": ["testing", "bug"],
            "testing": ["completed", "bug"],
            "bug": ["in_progress"],
            "completed": []
        }
        
        if target_status not in valid_transitions.get(current_status, []):
            self.metrics.record_violation(Violation(
                type=ViolationType.INVALID_STATUS_TRANSITION,
                details=f"非法状态转换: {current_status} → {target_status}",
                severity="error",
                feature_name=feature_name
            ))
            return False
        
        self.metrics.record_pass()
        return True
    
    def check_agent_boundary(
        self,
        agent_type: str,
        action: str,
        feature_name: Optional[str] = None
    ) -> bool:
        """
        检查：代理边界 - 每个代理只能执行自己职责范围的操作
        
        参考：ADDS 五大代理模型
        """
        agent_boundaries = {
            "pm": ["analyze_requirements", "decompose_tasks", "create_feature_list"],
            "architect": ["design_architecture", "select_tech_stack", "define_structure"],
            "developer": ["implement_feature", "write_unit_tests", "update_code"],
            "tester": ["run_tests", "validate_feature", "detect_regression"],
            "reviewer": ["code_review", "security_audit", "performance_eval"]
        }
        
        allowed_actions = agent_boundaries.get(agent_type, [])
        
        if action not in allowed_actions:
            self.metrics.record_violation(Violation(
                type=ViolationType.AGENT_BOUNDARY_VIOLATION,
                details=f"代理 '{agent_type}' 尝试执行越权操作: {action}",
                severity="error",
                feature_name=feature_name
            ))
            return False
        
        self.metrics.record_pass()
        return True
    
    def check_evidence_provided(
        self,
        feature_name: str,
        evidence: Dict
    ) -> bool:
        """
        检查：证据优先 - 功能完成必须提供证据
        
        参考：ADDS 核心原则
        """
        required_fields = ["files_modified", "tests_run", "tools_executed"]
        
        missing_fields = [f for f in required_fields if f not in evidence or not evidence[f]]
        
        if missing_fields:
            self.metrics.record_violation(Violation(
                type=ViolationType.MISSING_EVIDENCE,
                details=f"功能 '{feature_name}' 缺少证据字段: {missing_fields}",
                severity="error",
                feature_name=feature_name
            ))
            return False
        
        self.metrics.record_pass()
        return True
    
    def check_state_driven(
        self,
        expected_status: str,
        actual_status: str,
        feature_name: str
    ) -> bool:
        """
        检查：状态驱动 - 实际状态必须与预期一致
        
        参考：ADDS 核心原则
        """
        if expected_status != actual_status:
            self.metrics.record_violation(Violation(
                type=ViolationType.STATE_DRIVEN_VIOLATION,
                details=f"功能 '{feature_name}' 状态不一致: 预期 '{expected_status}', 实际 '{actual_status}'",
                severity="error",
                feature_name=feature_name
            ))
            return False
        
        self.metrics.record_pass()
        return True
    
    def check_safety_constraint(
        self,
        operation: str,
        is_allowed: bool,
        details: str = ""
    ) -> bool:
        """
        检查：安全约束 - 危险操作必须被拒绝
        
        参考：Claude Code 第16章 - 权限系统
        """
        dangerous_operations = [
            "rm -rf",
            "git push --force",
            "git reset --hard",
            "curl ... | bash",
        ]
        
        if operation in dangerous_operations and is_allowed:
            self.metrics.record_violation(Violation(
                type=ViolationType.SAFETY_CONSTRAINT_VIOLATION,
                details=f"危险操作被允许: {operation}. {details}",
                severity="critical"
            ))
            return False
        
        self.metrics.record_pass()
        return True
    
    def check_regression(
        self,
        old_tests_passed: bool,
        new_tests_passed: bool,
        feature_name: str
    ) -> bool:
        """
        检查：回归检测 - 新功能不应破坏旧功能
        
        参考：ADDS 核心原则
        """
        if old_tests_passed and not new_tests_passed:
            self.metrics.record_violation(Violation(
                type=ViolationType.REGRESSION_DETECTED,
                details=f"功能 '{feature_name}' 导致回归: 旧测试失败",
                severity="critical",
                feature_name=feature_name
            ))
            return False
        
        self.metrics.record_pass()
        return True
    
    def mark_feature_completed(self, feature_name: str):
        """标记功能已完成"""
        self.session_features.append(feature_name)
        self.current_feature = None
    
    def get_compliance_report(self) -> str:
        """生成合规报告"""
        summary = self.metrics.get_summary()
        
        report = f"""
# ADDS 规范遵循报告

## 总体指标
- 总检查数: {summary['total_checks']}
- 通过数: {summary['passed_checks']}
- 失败数: {summary['failed_checks']}
- 通过率: {summary['pass_rate']:.1%}
- 合规分数: {summary['compliance_score']:.2f}

## 违规统计
"""
        
        if summary['violations_by_type']:
            report += "\n### 按类型统计\n"
            for vtype, count in summary['violations_by_type'].items():
                report += f"- {vtype}: {count} 次\n"
        else:
            report += "\n✅ 无违规记录\n"
        
        if self.metrics.violations:
            report += "\n### 详细违规列表\n\n"
            for v in self.metrics.violations[-10:]:  # 最近 10 条
                report += f"- [{v.severity.upper()}] {v.type.value}: {v.details}\n"
        
        return report
    
    def save_report(self, filepath: str = ".ai/compliance_report.json"):
        """保存报告到文件"""
        import os
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": self.metrics.get_summary(),
            "violations": [v.to_dict() for v in self.metrics.violations]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 合规报告已保存到: {filepath}")


def main():
    """测试合规追踪器"""
    
    tracker = ComplianceTracker()
    
    print("=" * 80)
    print("ADDS 规范遵循追踪器测试")
    print("=" * 80)
    
    # 测试 1：一次一个功能
    print("\n[测试 1] 一次一个功能")
    tracker.check_one_feature_per_session("feature_1")
    tracker.check_one_feature_per_session("feature_1")  # 允许
    tracker.check_one_feature_per_session("feature_2")  # 应该失败
    
    # 测试 2：状态驱动
    print("\n[测试 2] 状态驱动")
    tracker.check_feature_list_exists(".ai/feature_list.md")  # 可能失败
    tracker.check_valid_status_transition("pending", "in_progress", "feature_1")
    tracker.check_valid_status_transition("pending", "completed", "feature_1")  # 应该失败
    
    # 测试 3：代理边界
    print("\n[测试 3] 代理边界")
    tracker.check_agent_boundary("developer", "implement_feature", "feature_1")
    tracker.check_agent_boundary("developer", "design_architecture", "feature_1")  # 应该失败
    
    # 测试 4：证据优先
    print("\n[测试 4] 证据优先")
    tracker.check_evidence_provided("feature_1", {
        "files_modified": ["main.py"],
        "tests_run": ["test_main.py"],
        "tools_executed": ["pytest"]
    })
    tracker.check_evidence_provided("feature_2", {
        "files_modified": [],  # 缺少证据
    })
    
    # 测试 5：安全约束
    print("\n[测试 5] 安全约束")
    tracker.check_safety_constraint("rm -rf", is_allowed=False)  # 正确拒绝
    tracker.check_safety_constraint("rm -rf", is_allowed=True)   # 应该失败
    
    # 生成报告
    print("\n" + "=" * 80)
    print(tracker.get_compliance_report())
    
    # 保存报告
    tracker.save_report()


if __name__ == "__main__":
    main()
