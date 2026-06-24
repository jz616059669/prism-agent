"""
本地 Skill 示例：文件操作增强
"""


def register(registry):
    registry.register(
        name="file_operations",
        description="读取、写入、搜索本地文件",
        triggers=["读取文件", "写入文件", "搜索文件", "file", "read", "write"],
        enabled=True,
    )
