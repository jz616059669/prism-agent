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
    status: str = "stable"  # stable | beta | placeholder


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
            description="网文创作基础工具：大纲模板、人物设定、章节模板生成（无需 API key）",
            triggers=["写小说", "创作", "章节", "大纲", "人物", "生成大纲", "人物设定", "角色"],
            handler=self._skill_novel_writing,
            status="stable",
        ))
        
        # 6. 小说优化 skill
        self.register(Skill(
            name="novel_optimization",
            description="网文优化基础工具：去AI味、重复检测、节奏分析（无需 API key）",
            triggers=["优化", "去AI味", "重复", "润色", "修改", "节奏", "检测重复"],
            handler=self._skill_novel_optimization,
            status="stable",
        ))

        # 7. 章节推送 skill
        self.register(Skill(
            name="chapter_delivery",
            description="长篇小说单章提取与推送：从合并文稿中提取指定章节正文并输出平台版",
            triggers=["发章节", "第X章", "推送章节", "下一章", "提取第", "章节推送", "发第"],
            handler=self._skill_chapter_delivery,
            status="stable",
        ))
    
        # 8. 学习/蒸馏 skill
        self.register(Skill(
            name="learn",
            description="从对话/工作流蒸馏可复用 skill",
            triggers=["/learn", "learn", "蒸馏", "distill", "学习"],
            handler=self._skill_learn,
            status="stable",
        ))

        # 9. memory graph skill
        self.register(Skill(
            name="memory_graph",
            description="记忆可视化：构建记忆/技能关系图，输出 JSON 或 Mermaid",
            triggers=["记忆图", "memory graph", "journey", "可视化记忆"],
            handler=self._skill_memory_graph,
            status="stable",
        ))

        # 10. background fan-out skill
        self.register(Skill(
            name="background_fanout",
            description="并行多子Agent：同时运行多个子任务并汇总结果",
            triggers=["并行", "fanout", "多任务", "同时", "并发"],
            handler=self._skill_background_fanout,
            status="stable",
        ))

        # 11. completion contracts skill
        self.register(Skill(
            name="completion_contracts",
            description="输出自验证：校验 agent 输出是否符合预设规则",
            triggers=["completion contract", "验证", "校验", "verify", "contract"],
            handler=self._skill_completion_contracts,
            status="stable",
        ))
    
    def _skill_learn(self, **kwargs) -> Dict[str, Any]:
        """学习/蒸馏 skill"""
        request = kwargs.get('request') or kwargs.get('user_request') or ''
        skill_name = kwargs.get('skill_name') or 'distilled-skill'
        try:
            from prism.skills.learn import build_learn_prompt, distill_from_conversation
            prompt = build_learn_prompt(request)
            return distill_from_conversation(
                conversation_text=prompt,
                skill_name=skill_name,
                description=kwargs.get('description') or f'Auto-distilled skill: {skill_name}',
                triggers=kwargs.get('triggers') or [skill_name],
            )
        except Exception as exc:
            return {'success': False, 'error': str(exc)}

    def _skill_memory_graph(self, **kwargs) -> Dict[str, Any]:
        """记忆可视化 skill"""
        try:
            from prism.memory_graph import build_memory_graph, render_graph_mermaid
            payload = build_memory_graph(
                max_memories=int(kwargs.get('max_memories', 200)),
                min_overlap=int(kwargs.get('min_overlap', 2)),
            )
            output_format = kwargs.get('format', 'json')
            if output_format == 'mermaid':
                payload['mermaid'] = render_graph_mermaid(payload)
            return payload
        except Exception as exc:
            return {'success': False, 'error': str(exc)}

    def _skill_background_fanout(self, **kwargs) -> Dict[str, Any]:
        """background fan-out skill"""
        try:
            from prism.fanout import BackgroundFanOut
            tasks = kwargs.get('tasks') or {}
            if not tasks:
                return {'success': False, 'error': 'tasks is required: dict of name -> prompt'}
            def agent_factory(name: str):
                from prism.agent import Agent
                return Agent()
            runner = BackgroundFanOut(agent_factory)
            results = runner.run(tasks)
            return {
                'success': True,
                'results': results,
                'summary': runner.aggregate(results),
            }
        except Exception as exc:
            return {'success': False, 'error': str(exc)}

    def _skill_completion_contracts(self, **kwargs) -> Dict[str, Any]:
        """completion contracts skill"""
        try:
            from prism.completion_contracts import evaluate, validate_and_retry, CompletionContract
            output = kwargs.get('output') or ''
            contract_defs = kwargs.get('contracts') or []
            contracts = []
            for item in contract_defs:
                if isinstance(item, dict):
                    contracts.append(CompletionContract(
                        name=item.get('name', 'unnamed'),
                        rule=item.get('rule', 'contains'),
                        value=item.get('value'),
                        required=bool(item.get('required', True)),
                    ))
            if not contracts:
                return {'success': False, 'error': 'contracts is required: list of {name, rule, value}'}
            return evaluate(output, contracts)
        except Exception as exc:
            return {'success': False, 'error': str(exc)}
    
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
        """网页搜索 skill（DuckDuckGo HTML 版，无需 API key）"""
        query = kwargs.get("query") or ""
        max_results = int(kwargs.get("max_results") or 5)
        if not query:
            return {"success": False, "error": "query is required"}
        try:
            from prism.tools.registry import WebSearchTool
            return WebSearchTool().execute(query=query, max_results=max_results)
        except Exception as exc:
            return {"success": False, "error": str(exc), "query": query}
    
    def _skill_code_execution(self, **kwargs) -> Dict[str, Any]:
        """代码执行 skill（真正执行并返回结果）"""
        from prism.tools.registry import registry
        return registry.execute('code_execute', 
            code=kwargs.get('code'), 
            timeout=kwargs.get('timeout', 30))
    
    def _skill_novel_writing(self, **kwargs) -> Dict[str, Any]:
        """小说写作 skill（基础规则版，无需 API key）"""
        action = kwargs.get('action', 'outline')
        if action == 'generate_chapter':
            outline = kwargs.get('outline') or '未提供大纲'
            return {
                'success': True,
                'message': '基础章节生成完成（模板版，需要 LLM key 才能生成高质量正文）',
                'chapter': {
                    'title': kwargs.get('title', '未命名章节'),
                    'outline': outline,
                    'body': f'【{kwargs.get("title", "未命名章节")}】\n根据大纲：{outline}\n\n此处为基础模板，配置 API Key 后可生成高质量网文正文。',
                    'note': '请先在设置中配置 model.api_key 以启用 AI 生成'
                }
            }
        elif action == 'generate_outline':
            theme = kwargs.get('theme') or '未提供主题'
            return {
                'success': True,
                'message': '基础大纲生成完成（模板版）',
                'outline': [
                    f'第一章：{theme}的开端',
                    '第二章：主角登场',
                    '第三章：冲突升级',
                    '第四章：危机爆发',
                    '第五章：逆袭反转',
                ],
                'note': '模板大纲，配置 API Key 后可生成定制化大纲'
            }
        elif action == 'create_character':
            name = kwargs.get('name') or '无名'
            role = kwargs.get('role') or '配角'
            return {
                'success': True,
                'message': '基础人物设定完成',
                'character': {
                    'name': name,
                    'role': role,
                    'personality': kwargs.get('personality', '沉稳'),
                    'background': kwargs.get('background', '待补充'),
                    'traits': ['勇敢', '机智', '重情义']
                }
            }
        return {'success': False, 'error': f'Unknown action: {action}'}
    
    def _skill_novel_optimization(self, **kwargs) -> Dict[str, Any]:
        """小说优化 skill（基础规则版，无需 API key）"""
        action = kwargs.get('action', 'remove_ai_flavor')
        text = kwargs.get('text') or ''
        if action == 'remove_ai_flavor':
            ai_patterns = [
                ('——', '——'), ('这——就是——', '这就是'),
                ('值得一提的是', '值得注意的是'), ('综上所述', '总而言之一句话'),
                ('在这个...中', '在...里'), ('不可否认', '不得不承认'),
            ]
            result = text
            replacements = []
            for old, new in ai_patterns:
                if old in result:
                    result = result.replace(old, new)
                    replacements.append(f'{old} -> {new}')
            return {
                'success': True,
                'message': f'已替换 {len(replacements)} 处 AI 味表达',
                'replacements': replacements,
                'text': result
            }
        elif action == 'detect_repetition':
            sentences = [s.strip() for s in text.replace('。', '。|').replace('！', '！|').replace('？', '？|').split('|') if s.strip()]
            seen = {}
            duplicates = []
            for s in sentences:
                key = s[:20]
                seen[key] = seen.get(key, 0) + 1
                if seen[key] > 1:
                    duplicates.append(s)
            return {
                'success': True,
                'message': f'检测到 {len(duplicates)} 处疑似重复',
                'duplicates': duplicates[:10],
                'total_sentences': len(sentences)
            }
        elif action == 'suggest_pacing':
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
            long_paras = [i for i, p in enumerate(paragraphs, 1) if len(p) > 500]
            return {
                'success': True,
                'message': '节奏分析完成',
                'total_paragraphs': len(paragraphs),
                'long_paragraphs': long_paras[:5],
                'suggestion': '建议将超长段落拆分为 2-3 段，每段 300-500 字，提升阅读节奏。' if long_paras else '段落长度分布合理，节奏良好。'
            }
        return {'success': False, 'error': f'Unknown action: {action}'}
    
    def _skill_chapter_delivery(self, **kwargs) -> Dict[str, Any]:
        """小说章节推送 skill"""
        try:
            from prism.skills.chapter_delivery import chapter_delivery_handler
            return chapter_delivery_handler(**kwargs)
        except Exception as e:
            return {'success': False, 'error': f'chapter_delivery failed: {e}'}
    
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
        except Exception as exc:
            logger.warning("search hub failed: %s", exc)
            return []
    
    def browse_hub(self) -> List[Dict[str, Any]]:
        """浏览远程 Hub Skills"""
        hub_url = prism_config.get('skills.hub')
        if not hub_url:
            return []
        try:
            import requests
            url = f"{hub_url.rstrip('/')}/skills"
            resp = requests.get(url, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return data.get('skills', [])
            return []
        except Exception:
            return []
    
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
                'status': getattr(s, 'status', 'stable'),
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

    def recommend(self, text: str, max_items: int = 5) -> List[Dict[str, Any]]:
        """根据用户 query 推荐可用 skill，按匹配强度排序。"""
        matched = self.match(text)
        if not matched:
            return []
        scored = []
        text_lower = text.lower()
        for skill in matched:
            score = 0
            for trigger in skill.triggers:
                if not trigger:
                    continue
                if trigger.lower() in text_lower:
                    score += 2
                if trigger in text:
                    score += 1
            scored.append((score, skill))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                'name': s.name,
                'description': s.description,
                'score': score,
                'triggers': s.triggers,
            }
            for score, s in scored[: max(1, max_items)]
        ]

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

    def toggle_skill(self, name: str) -> Dict[str, Any]:
        """切换 Skill 启用状态"""
        skill = self.skills.get(name)
        if not skill:
            return {'success': False, 'error': f'Skill not found: {name}'}
        skill.enabled = not bool(skill.enabled)
        state = "启用" if skill.enabled else "禁用"
        return {'success': True, 'message': f'{name} 已{state}', 'enabled': skill.enabled}

    def get_skill_detail(self, name: str) -> Dict[str, Any]:
        """获取 Skill 详情"""
        skill = self.skills.get(name)
        if not skill:
            return {'success': False, 'error': f'Skill not found: {name}'}
        return {
            'success': True,
            'name': skill.name,
            'description': skill.description,
            'version': skill.version,
            'author': getattr(skill, 'author', 'unknown'),
            'enabled': skill.enabled,
            'triggers': skill.triggers,
            'status': getattr(skill, 'status', 'stable'),
            'handler': skill.handler.__name__ if skill.handler else None,
        }


# 全局 Skills 注册表
skills = SkillRegistry()
