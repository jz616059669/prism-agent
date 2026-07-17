from pathlib import Path

# patch main.py methods and chat.py methods
main_path = "prism-desktop/prism_desktop/main.py"
with open(main_path, "r", encoding="utf-8") as f:
    main_src = f.read()

old_paste = '''    def _paste_attachment(self):
        try:
            if hasattr(self.page, "clipboard") and self.page.clipboard is not None:
                text = self.page.clipboard.get_text() or ""
                if text.strip():
                    self.input_field.value = (self.input_field.value or "") + text
                    self._on_input_change()
                    self._set_status("已粘贴", ft.Colors.GREEN_400)
                else:
                    self._set_status("剪贴板为空", ft.Colors.AMBER_400)
            else:
                self._set_status("粘贴不可用", ft.Colors.AMBER_400)
        except Exception as exc:
            self._log_error("paste failed", exc)
            self._set_status("粘贴失败", ft.Colors.RED_400)

    def _save_session(self):'''
new_paste = '''    def _paste_attachment(self):
        try:
            if hasattr(self.page, "clipboard") and self.page.clipboard is not None:
                text = self.page.clipboard.get_text() or ""
                if text.strip():
                    self.input_field.value = (self.input_field.value or "") + text
                    self._on_input_change()
                    self._set_status("已粘贴", ft.Colors.GREEN_400)
                else:
                    self._set_status("剪贴板为空", ft.Colors.AMBER_400)
            else:
                self._set_status("粘贴不可用", ft.Colors.AMBER_400)
        except Exception as exc:
            self._log_error("paste failed", exc)
            self._set_status("粘贴失败", ft.Colors.RED_400)
        finally:
            self._clear_pending_images()

    def _pick_image(self):
        try:
            getattr(self, "_image_picker").pick_files(
                dialog_title="选择图片",
                file_type=ft.FilePickerFileType.IMAGE,
                allow_multiple=False,
            )
        except Exception as exc:
            self._log_error("pick image failed", exc)
            self._set_status("选择图片失败", ft.Colors.RED_400)

    def _on_image_picked(self, e):
        try:
            files = getattr(e, "files", []) or []
            if files:
                path = files[0].path
                if path:
                    self._pending_images.append(path)
                    self._refresh_image_previews()
                    self._set_status("已添加图片", ft.Colors.GREEN_400)
        except Exception as exc:
            self._log_error("image picked failed", exc)
            self._set_status("读取图片失败", ft.Colors.RED_400)

    def _refresh_image_previews(self):
        try:
            self._image_preview_row.controls.clear()
            if not self._pending_images:
                self._image_preview_row.visible = False
            else:
                self._image_preview_row.visible = True
                for p in self._pending_images:
                    thumb = ft.Image(
                        src=p,
                        width=64,
                        height=64,
                        fit=ft.ImageFit.COVER,
                        border_radius=8,
                    )
                    remove = ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        tooltip="移除",
                        icon_size=14,
                        icon_color=ft.Colors.ON_SURFACE_VARIANT,
                        bgcolor=ft.Colors.with_opacity(0, ft.Colors.TRANSPARENT),
                        style=ft.ButtonStyle(shape=ft.CircleBorder(), overlay_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE_VARIANT)),
                        on_click=lambda e, x=p: self._remove_pending_image(x),
                    )
                    self._image_preview_row.controls.append(
                        ft.Stack([thumb, ft.Container(remove, alignment=ft.alignment.top_right)], width=64, height=64)
                    )
            if getattr(self._image_preview_row, "page", None):
                self._image_preview_row.update()
        except Exception as exc:
            self._log_error("refresh preview failed", exc)

    def _remove_pending_image(self, path: str):
        try:
            self._pending_images = [p for p in self._pending_images if p != path]
            self._refresh_image_previews()
        except Exception as exc:
            self._log_error("remove image failed", exc)

    def _clear_pending_images(self):
        self._pending_images = []
        self._refresh_image_previews()

    def _save_session(self):'''
if old_paste not in main_src:
    raise SystemExit("paste block not found")
main_src = main_src.replace(old_paste, new_paste)

with open(main_path, "w", encoding="utf-8") as f:
    f.write(main_src)
print("patched main.py methods")

# patch chat.py
chat_path = "prism-desktop/prism_desktop/chat.py"
with open(chat_path, "r", encoding="utf-8") as f:
    chat_src = f.read()

old_send = '''    def _send(self, retry_text: str = ""):
        text = retry_text or (self.input_field.value or "").strip()
        if not text:
            return
        if not getattr(self, "agent", None):
            self._append("PRISM", "Error: agent 未初始化，请检查配置并保存后重试。")
            self._log_to_file("warning", "send_blocked", reason="agent is None")
            return
        self.input_field.value = ""
        self.input_field.update()
        self._generating = True
        self.stop_btn.visible = True
        self.stop_btn.update()
        self._append("你", text)'''
new_send = '''    def _send(self, retry_text: str = ""):
        text = retry_text or (self.input_field.value or "").strip()
        images = list(getattr(self, "_pending_images", []) or [])
        if not text and not images:
            return
        if not getattr(self, "agent", None):
            self._append("PRISM", "Error: agent 未初始化，请检查配置并保存后重试。")
            self._log_to_file("warning", "send_blocked", reason="agent is None")
            return
        self.input_field.value = ""
        self.input_field.update()
        self._generating = True
        self.stop_btn.visible = True
        self.stop_btn.update()
        if images:
            try:
                if hasattr(self, "_clear_pending_images"):
                    self._clear_pending_images()
            except Exception:
                pass
            display_text = text if text else "图片"
            self._append("你", display_text, images=images)
            multimodal_content = self._build_multimodal_content(text, images)
        else:
            self._append("你", text)
            multimodal_content = text
'''
chat_src = chat_src.replace(old_send, new_send)

old_run = '''                result = self.agent.chat(
                    text,
                    on_chunk=lambda c: _stream_chunk(c) if getattr(self, "_generating", False) else None,
                )'''
new_run = '''                result = self.agent.chat(
                    multimodal_content,
                    on_chunk=lambda c: _stream_chunk(c) if getattr(self, "_generating", False) else None,
                )'''
chat_src = chat_src.replace(old_run, new_run)

old_append_sig = '''    def _append(self, role: str, text: str, retry: bool = False, retry_text: str = "", placeholder: bool = False):'''
new_append_sig = '''    def _append(self, role: str, text: str, retry: bool = False, retry_text: str = "", placeholder: bool = False, images=None):'''
chat_src = chat_src.replace(old_append_sig, new_append_sig)

old_append_md = '''            role_text = ft.Text(role, size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500)
            time_text = ft.Text(timestamp, size=11, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.8)
            content = self._markdown_to_ft(text)
            row = ft.Row(
                [role_text, ft.Container(expand=True), time_text],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            message_widget = ft.Container(
                content=ft.Column(
                    [row, ft.Container(height=4), *content],
                    tight=True,
                    spacing=0,
                    horizontal_alignment=align,
                ),'''
new_append_md = '''            role_text = ft.Text(role, size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500)
            time_text = ft.Text(timestamp, size=11, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.8)
            row = ft.Row(
                [role_text, ft.Container(expand=True), time_text],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            children = [row, ft.Container(height=4)]
            if images:
                for img_path in images:
                    children.append(
                        ft.Image(
                            src=img_path,
                            width=220,
                            height=220,
                            fit=ft.ImageFit.CONTAIN,
                            border_radius=10,
                            repeat=ft.ImageRepeat.NO_REPEAT,
                        )
                    )
                children.append(ft.Container(height=4))
            children.extend(self._markdown_to_ft(text))
            message_widget = ft.Container(
                content=ft.Column(
                    children,
                    tight=True,
                    spacing=0,
                    horizontal_alignment=align,
                ),'''
chat_src = chat_src.replace(old_append_md, new_append_md)

old_end = '''    def _apply_prompt_template(self, prompt: str):
        try:
            current = self.input_field.value or ""
            self.input_field.value = prompt + current
            self.input_field.focus()
            self.input_field.update()
            if hasattr(self, "_on_input_change"):
                self._on_input_change()
        except Exception:
            pass'''
new_end = '''    def _apply_prompt_template(self, prompt: str):
        try:
            current = self.input_field.value or ""
            self.input_field.value = prompt + current
            self.input_field.focus()
            self.input_field.update()
            if hasattr(self, "_on_input_change"):
                self._on_input_change()
        except Exception:
            pass

    @staticmethod
    def _build_multimodal_content(text: str, image_paths):
        if not image_paths:
            return text or ""
        content = []
        if text.strip():
            content.append({"type": "text", "text": text.strip()})
        for p in image_paths:
            data_uri = p
            try:
                data = Path(p).read_bytes()
                mime = __import__("mimetypes").mimetypes.guess_type(p)[0] or "image/png"
                data_uri = f"data:{mime};base64,{__import__('base64').b64encode(data).decode('utf-8')}"
            except Exception:
                pass
            content.append({"type": "image_url", "image_url": {"url": data_uri}})
        return content if len(content) > 1 else (content[0].get("text", text) if content else text or "")'''
chat_src = chat_src.replace(old_end, new_end)

with open(chat_path, "w", encoding="utf-8") as f:
    f.write(chat_src)
print("patched chat.py")
