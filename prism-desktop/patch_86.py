with open('prism_desktop/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix browser methods: add _set_browser_status and fix _browser_open
browser_methods = '''
    def _set_browser_status(self, connected: bool, title: str = ""):
        self.browser_connected = connected
        if connected:
            self.browser_status_icon.icon = ft.Icons.LANGUAGE_ROUNDED
            self.browser_status_icon.color = ft.Colors.GREEN_400
            self.browser_status_text.value = title or "已连接"
            self.browser_status_text.color = ft.Colors.GREEN_400
        else:
            self.browser_status_icon.icon = ft.Icons.LANGUAGE_ROUNDED
            self.browser_status_icon.color = ft.Colors.ON_SURFACE_VARIANT
            self.browser_status_text.value = "就绪"
            self.browser_status_text.color = ft.Colors.ON_SURFACE_VARIANT
        self.browser_status_icon.update()
        self.browser_status_text.update()

    def _browser_open(self):
        url = self.url_field.value.strip() if hasattr(self, 'url_field') else ""
        if not url:
            self._set_status("请输入网址", ft.Colors.RED_400)
            return
        self._append_terminal(f"browser open {url}")
        try:
            from prism.tools.browser import browser as browser_api
            result = browser_api.navigate(url, headless=True)
            if result.get('success'):
                self._set_browser_status(True, result.get('title', url))
                self._append_terminal(f"opened: {result.get('title', url)}")
            else:
                self._set_status(f"打开失败: {result.get('error', 'unknown')}", ft.Colors.RED_400)
        except Exception as e:
            self._append_terminal(f"browser error: {e}")
            self._set_status("浏览器异常", ft.Colors.RED_400)

'''

old_browser = '''    def _browser_open(self):
        url = self.browser_url_field.value.strip() if hasattr(self, 'browser_url_field') else ""
        if not url:
            self._set_status("请输入网址", ft.Colors.RED_400)
            return
        self._append_terminal(f"browser open {url}")
        try:
            from prism.tools.browser import browser as browser_api
            result = browser_api.navigate(url, headless=True)
            if result.get('success'):
                self._set_browser_status(True, result.get('title', url))
                self._append_terminal(f"opened: {result.get('title', url)}")
            else:
                self._set_status(f"打开失败: {result.get('error', 'unknown')}", ft.Colors.RED_400)
        except Exception as e:
            self._append_terminal(f"browser error: {e}")
            self._set_status("浏览器异常", ft.Colors.RED_400)

'''

content = content.replace(old_browser, browser_methods)

# 2. Add _refresh_skills and _install_skill_from_ui methods
skills_methods = '''
    def _refresh_skills(self):
        self._append_terminal("refresh skills ...")
        try:
            from prism.skills import skills
            skill_list = skills.list_skills()
            self.skill_list.controls.clear()
            if not skill_list:
                self.skill_list.controls.append(ft.Text("暂无 Skills", size=12, color=ft.Colors.ON_SURFACE_VARIANT))
            else:
                for skill in skill_list:
                    status = "启用" if skill.get('enabled') else "禁用"
                    row = ft.Row([
                        ft.Text(skill.get('name', 'unknown'), size=12, expand=True),
                        ft.Text(status, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=6, tight=True)
                    self.skill_list.controls.append(row)
            self.skill_list.update()
            self._append_terminal(f"skills refreshed: {len(skill_list)} 个")
        except Exception as e:
            self._append_terminal(f"skills error: {e}")
            self._set_status("Skills 刷新失败", ft.Colors.RED_400)

    def _install_skill_from_ui(self):
        name = self.skill_install_field.value.strip() if hasattr(self, 'skill_install_field') else ""
        if not name:
            self._set_status("请输入 Skill 名称或本地路径", ft.Colors.RED_400)
            return
        self._append_terminal(f"install skill: {name}")
        try:
            from prism.skills import skills
            result = skills.install_skill(name)
            if result.get('success'):
                self._set_status(result.get('message', '安装成功'), ft.Colors.GREEN_400)
                self._append_terminal(f"installed: {result.get('message')}")
                self._refresh_skills()
            else:
                self._set_status(f"安装失败: {result.get('error', 'unknown')}", ft.Colors.RED_400)
        except Exception as e:
            self._append_terminal(f"install error: {e}")
            self._set_status("Skill 安装异常", ft.Colors.RED_400)

'''

# Insert skills methods before _set_status
content = content.replace(
    '    def _set_status(self, text: str, color=ft.Colors.GREEN_400):',
    skills_methods + '    def _set_status(self, text: str, color=ft.Colors.GREEN_400):'
)

with open('prism_desktop/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('OK: batch 86 applied')
