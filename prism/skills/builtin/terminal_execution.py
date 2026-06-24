"""
本地 Skill 示例：终端执行
"""


def register(registry):
    registry.register(
        name="terminal_execution",
        description="执行终端命令并返回结果",
        triggers=["执行命令", "终端", "terminal", "bash", "cmd"],
        enabled=True,
    )
