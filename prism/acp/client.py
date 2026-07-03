"""
PRISM Agent - ACP (Agent Communication Protocol) 客户端
提供与 ACP 兼容 agent 通信的能力
"""

import json
import subprocess
from typing import Any, Dict, Optional


class ACPClient:
    """
    ACP 客户端
    通过 stdio 与 ACP 兼容 agent 通信
    """
    
    def __init__(self, command: str, args: Optional[list] = None):
        self.command = command
        self.args = args or []
        self.process: Optional[subprocess.Popen] = None
    
    def start(self) -> Dict[str, Any]:
        try:
            self.process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.process:
            return {'success': False, 'error': 'ACP client not started'}
        
        try:
            request = json.dumps({'jsonrpc': '2.0', 'id': 1, **payload}) + '\n'
            self.process.stdin.write(request)
            self.process.stdin.flush()
            response_line = self.process.stdout.readline()
            if not response_line:
                return {'success': False, 'error': 'No response from ACP agent'}
            response = json.loads(response_line)
            if 'result' in response:
                return {'success': True, 'result': response['result']}
            if 'error' in response:
                return {'success': False, 'error': response['error'].get('message', 'Unknown error')}
            return {'success': False, 'error': 'Invalid ACP response'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def close(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                logger.debug("acp client close failed: %s", traceback.format_exc())
            self.process = None
