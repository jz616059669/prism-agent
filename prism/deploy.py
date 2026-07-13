"""
PRISM Agent - 一键部署流水线
检测代码变更，自动构建 Docker 镜像 + 推送到 registry
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class DeployResult:
    success: bool
    image: str = ""
    tag: str = ""
    registry: str = ""
    logs: str = ""
    error: str = ""


class DeployPipeline:
    def __init__(self, repo_path: Optional[str] = None, registry: str = "localhost:5000") -> None:
        self.repo_path = Path(repo_path or os.getcwd())
        self.registry = registry

    def build(self, dockerfile: str = "Dockerfile", context: str = ".", tag: Optional[str] = None) -> DeployResult:
        tag = tag or f"{self.registry}/prism-agent:latest"
        logs: list[str] = []
        try:
            build = subprocess.run(
                ["docker", "build", "-t", tag, "-f", dockerfile, context],
                cwd=self.repo_path, capture_output=True, text=True, timeout=600
            )
            logs.append(build.stdout)
            if build.returncode != 0:
                return DeployResult(success=False, tag=tag, registry=self.registry, logs="\n".join(logs), error=build.stderr)
            return DeployResult(success=True, image=tag, tag=tag, registry=self.registry, logs="\n".join(logs))
        except Exception as exc:
            return DeployResult(success=False, tag=tag, registry=self.registry, error=str(exc), logs="\n".join(logs))

    def push(self, tag: str) -> DeployResult:
        logs: list[str] = []
        try:
            push = subprocess.run(["docker", "push", tag], capture_output=True, text=True, timeout=600)
            logs.append(push.stdout)
            if push.returncode != 0:
                return DeployResult(success=False, tag=tag, registry=self.registry, logs="\n".join(logs), error=push.stderr)
            return DeployResult(success=True, image=tag, tag=tag, registry=self.registry, logs="\n".join(logs))
        except Exception as exc:
            return DeployResult(success=False, tag=tag, registry=self.registry, error=str(exc), logs="\n".join(logs))

    def deploy(self, dockerfile: str = "Dockerfile", context: str = ".", tag: Optional[str] = None, push: bool = False) -> DeployResult:
        build_res = self.build(dockerfile=dockerfile, context=context, tag=tag)
        if not build_res.success:
            return build_res
        if push:
            push_res = self.push(build_res.tag)
            return push_res
        return build_res


deploy_pipeline = DeployPipeline()
