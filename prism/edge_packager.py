"""
PRISM Agent - 边缘部署包
生成离线 Docker 镜像，可部署到无外网环境
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EdgePackageResult:
    success: bool
    image: str = ""
    tar_path: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "image": self.image,
            "tar_path": self.tar_path,
            "error": self.error,
        }


class EdgePackager:
    def __init__(self, repo_path: Optional[str] = None) -> None:
        self.repo_path = Path(repo_path or os.getcwd())
        self._output_dir = self.repo_path / "dist-edge"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def build_offline_image(self, tag: str = "prism-agent:offline") -> EdgePackageResult:
        dockerfile = self.repo_path / "Dockerfile"
        if not dockerfile.exists():
            return EdgePackageResult(success=False, error="Dockerfile not found")
        try:
            build = subprocess.run(
                ["docker", "build", "--no-cache", "-t", tag, "-f", str(dockerfile), str(self.repo_path)],
                capture_output=True, text=True, timeout=900
            )
            if build.returncode != 0:
                return EdgePackageResult(success=False, error=build.stderr, image=tag)
            return EdgePackageResult(success=True, image=tag)
        except Exception as exc:
            return EdgePackageResult(success=False, error=str(exc), image=tag)

    def export_tar(self, tag: str) -> EdgePackageResult:
        tar_path = str(self._output_dir / "prism-agent-offline.tar")
        try:
            save = subprocess.run(["docker", "save", "-o", tar_path, tag], capture_output=True, text=True, timeout=600)
            if save.returncode != 0:
                return EdgePackageResult(success=False, error=save.stderr, image=tag)
            return EdgePackageResult(success=True, image=tag, tar_path=tar_path)
        except Exception as exc:
            return EdgePackageResult(success=False, error=str(exc), image=tag)

    def package(self, tag: str = "prism-agent:offline") -> EdgePackageResult:
        build_res = self.build_offline_image(tag=tag)
        if not build_res.success:
            return build_res
        return self.export_tar(tag)


edge_packager = EdgePackager()
