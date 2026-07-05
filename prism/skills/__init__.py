"""
PRISM Agent - Skills 系统
整合 Hermes 的 skill 机制 + Codex 的经验复用
"""

import os
import json
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime

from prism.config import config as prism_config


@dataclass
class Skill:
    """Skill 定义"""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "unknown"
    triggers: List[str] = field(default_factory=list)  # 触发关键词
    handler: Optional[Callable] = None
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillRegistry:
    """
    Skill 注册表
    整合 Hermes 的 skill 加载机制
    """
    
    def __init__(self, skills_dir: Optional[str] = None):
        self.skills_dir = Path(skills_dir or Path.home() / ".prism" / "skills")
        self.skills: Dict[str, Skill] = {}
        self._load_builtin_skills()
        self._load_external_skills()
    
    def _load_builtin_skills(self):
        """加载内置 Skills"""
        
        # 1. 文件操作 skill
        self.register(Skill(
            name="file_operations",
            description="文件读写、搜索、补丁操作",
            triggers=["读取文件", "写入文件", "修改文件", "搜索文件"],
            handler=self._skill_file_operations,
        ))
        
        # 2. 终端执行 skill
        self.register(Skill(
            name="terminal_execution",
            description="执行 shell 命令、运行脚本",
            triggers=["执行命令", "运行脚本", "terminal", "shell"],
            handler=self._skill_terminal_execution,
        ))
        
        # 3. 网页搜索 skill
        self.register(Skill(
            name="web_search",
            description="搜索网页、获取网页内容",
            triggers=["搜索", "查找", "网页", "search"],
            handler=self._skill_web_search,
        ))
        
        # 4. 代码执行 skill
        self.register(Skill(
            name="code_execution",
            description="执行 Python 代码、数据分析",
            triggers=["运行代码", "执行脚本", "python", "计算"],
            handler=self._skill_code_execution,
        ))
        
        # 5. 小说写作 skill
        self.register(Skill(
            name="novel_writing",
            description="网文创作：章节生成、大纲规划、人物设定",
            triggers=["写小说", "创作", "章节", "大纲", "人物"],
            handler=self._skill_novel_writing,
        ))
        
        # 6. 小说优化 skill
        self.register(Skill(
            name="novel_optimization",
            description="网文优化：去AI味、重复检测、节奏调整",
            triggers=["优化", "去AI味", "重复", "润色", "修改"],
            handler=self._skill_novel_optimization,
        ))
    
    def _skill_file_operations(self, **kwargs) -> Dict[str, Any]:
        """文件操作 skill"""
        from prism.tools.registry import registry
        action = kwargs.get('action', 'read')
        if action == 'read':
            return registry.execute('file_read', path=kwargs.get('path'))
        elif action == 'write':
            return registry.execute('file_write', path=kwargs.get('path'), content=kwargs.get('content'))
        elif action == 'patch':
            return registry.execute('file_patch', 
                path=kwargs.get('path'),
                old_string=kwargs.get('old_string'),
                new_string=kwargs.get('new_string'))
        return {'success': False, 'error': f'Unknown action: {action}'}
    
    def _skill_terminal_execution(self, **kwargs) -> Dict[str, Any]:
        """终端执行 skill"""
        from prism.tools.registry import registry
        return registry.execute('terminal', 
            command=kwargs.get('command'),
            timeout=kwargs.get('timeout', 180))
    
    def _skill_web_search(self, **kwargs) -> Dict[str, Any]:
        """网页搜索 skill（简化版）"""
        return {
            'success': True,
            'message': 'Web search requires external API integration',
            'query': kwargs.get('query'),
        }
    
    def _skill_code_execution(self, **kwargs) -> Dict[str, Any]:
        """代码执行 skill（简化版）"""
        return {
            'success': True,
            'message': 'Code execution requires sandbox setup',
            'code': kwargs.get('code'),
        }
    
    def _skill_novel_writing(self, **kwargs) -> Dict[str, Any]:
        """小说写作 skill"""
        action = kwargs.get('action', 'generate')
        if action == 'generate':
            return {
                'success': True,
                'message': 'Novel generation requires LLM integration',
                'chapter': kwargs.get('chapter'),
                'outline': kwargs.get('outline'),
            }
        return {'success': False, 'error': f'Unknown action: {action}'}
    
    def _skill_novel_optimization(self, **kwargs) -> Dict[str, Any]:
        """小说优化 skill"""
        action = kwargs.get('action', 'detect')
        if action == 'detect':
            return {
                'success': True,
                'message': 'AI flavor detection requires pattern matching',
                'patterns': kwargs.get('patterns', ['——', '这——就是——']),
            }
        elif action == 'remove':
            return {
                'success': True,
                'message': 'AI flavor removal requires batch processing',
                'target': kwargs.get('target'),
            }
        return {'success': False, 'error': f'Unknown action: {action}'}
    
    def _load_external_skills(self):
        """从 skills 目录加载外部 skills"""
        if not self.skills_dir.exists():
            return
        
        for skill_file in self.skills_dir.glob("*.py"):
            try:
                spec = importlib.util.spec_from_file_location(
                    skill_file.stem, skill_file
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                if hasattr(module, 'register'):
                    module.register(self)
            except Exception as e:
                logger.warning("load external skill failed: %s", skill_file, exc_info=True)
    
    def search_hub(self, query: str) -> List[Dict[str, Any]]:
        """搜索远程 Hub Skills"""
        hub_url = prism_config.get('skills.hub')
        if not hub_url:
            return []
        try:
            import requests
            url = f"{hub_url.rstrip('/')}/skills"
            params = {'q': query}
            resp = requests.get(url, params=params, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return data.get('skills', [])
            return []
        except Exception:
            return []
    
    def browse_hub(self) -> List[Dict[str, Any]]:
        """浏览远程 Hub Skills"""
        return self.search_hub('')
    
    def register(self, skill: Skill):
        """注册 skill"""
        self.skills[skill.name] = skill
    
    def get(self, name: str) -> Optional[Skill]:
        """获取 skill"""
        return self.skills.get(name)
    
    def list_skills(self) -> List[Dict[str, Any]]:
        """列出所有 skills"""
        return [
            {
                'name': s.name,
                'description': s.description,
                'version': s.version,
                'enabled': s.enabled,
                'triggers': s.triggers,
            }
            for s in self.skills.values()
        ]
    
    def execute(self, name: str, **kwargs) -> Dict[str, Any]:
        """执行 skill"""
        skill = self.skills.get(name)
        if not skill:
            return {'success': False, 'error': f'Skill not found: {name}'}
        
        if not skill.enabled:
            return {'success': False, 'error': f'Skill disabled: {name}'}
        
        if not skill.handler:
            return {'success': False, 'error': f'Skill has no handler: {name}'}
        
        try:
            return skill.handler(**kwargs)
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def match(self, text: str) -> List[Skill]:
        """根据文本匹配相关 skills"""
        text_lower = text.lower()
        matched = []
        matched_names = set()
        
        def _try_add(skill: Skill):
            if skill.enabled and skill.name not in matched_names:
                matched.append(skill)
                matched_names.add(skill.name)
        
        for skill in self.skills.values():
            if not skill.enabled:
                continue
            
            for trigger in skill.triggers:
                if not trigger:
                    continue
                trigger_lower = trigger.lower()
                if trigger_lower in text_lower:
                    _try_add(skill)
                    break
                if trigger in text:
                    _try_add(skill)
                    break
        
        if not matched:
            for skill in self.skills.values():
                if not skill.enabled:
                    continue
                if skill.name in text or skill.name.lower() in text_lower:
                    _try_add(skill)
        
        return matched

    def install_skill(self, name: str) -> Dict[str, Any]:
        """安装 Skill"""
        if name in self.skills:
            return {'success': True, 'message': f'{name} 已安装'}
        
        skill_dir = self.skills_dir
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        # 本地路径安装
        local_candidate = Path(name)
        if local_candidate.exists():
            # 目录批量安装
            if local_candidate.is_dir():
                installed = []
                for skill_file in local_candidate.glob('*.py'):
                    if skill_file.name == '__init__.py':
                        continue
                    target = skill_dir / skill_file.name
                    if target.exists():
                        continue
                    target.write_text(skill_file.read_text(encoding='utf-8'), encoding='utf-8')
                    installed.append(target.name)
                self._load_external_skills()
                return {'success': True, 'message': f'已从目录安装 {len(installed)} 个 skills: {", ".join(installed)}'}
            
            # 单文件安装
            target = skill_dir / f"{local_candidate.stem}.py"
            if target.exists():
                return {'success': False, 'error': f'{target.name} 已存在'}
            target.write_text(local_candidate.read_text(encoding='utf-8'), encoding='utf-8')
            self._load_external_skills()
            return {'success': True, 'message': f'已从本地安装 {target.name}'}
        
        # hub 安装
        target = skill_dir / f"{name}.py"
        if target.exists():
            return {'success': False, 'error': f'{name} 已存在'}
        
        hub_url = prism_config.get('skills.hub')
        if hub_url:
            try:
                import requests
                url = f"{hub_url.rstrip('/')}/skills/{name}.py"
                resp = requests.get(url, timeout=20)
                if resp.status_code == 200 and resp.text.strip():
                    target.write_text(resp.text, encoding='utf-8')
                    self._load_external_skills()
                    return {'success': True, 'message': f'已从 hub 安装 {name}'}
            except Exception as e:
                return {'success': False, 'error': f'hub 安装失败: {e}'}
        
        return {'success': False, 'error': f'未找到 skill: {name}'}

    def uninstall_skill(self, name: str) -> Dict[str, Any]:
        """移除 Skill"""
        if name not in self.skills:
            return {'success': True, 'message': f'{name} 未安装'}
        
        target = self.skills_dir / f"{name}.py"
        if target.exists():
            target.unlink()
        
        self.skills.pop(name, None)
        return {'success': True, 'message': f'已移除 {name}'}


# 全局 Skills 注册表
skills = SkillRegistry()
