def _upload_file(self):
        """Open file dialog and add file to attachments."""
        from tkinter import filedialog
        filetypes = [
            ("All files", "*.*"),
            ("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
            ("Documents", "*.pdf *.docx *.doc *.txt *.md *.xlsx *.csv *.pptx"),
            ("Code", "*.py *.js *.ts *.html *.css *.json *.yaml *.yml *.cpp *.c *.h *.rs *.go"),
            ("Archives", "*.zip *.tar *.gz *.7z *.rar"),
        ]
        files = filedialog.askopenfilenames(
            title="Select files to attach",
            filetypes=filetypes
        )
        
        for file_path in files:
            self._add_attachment(file_path)
    
    def _add_attachment(self, file_path: str):
        """Add file to attachment list and show in UI."""
        import os
        from pathlib import Path
        
        file_info = {
            "path": file_path,
            "name": Path(file_path).name,
            "size": os.path.getsize(file_path),
            "type": self._get_file_type(file_path)
        }
        
        self.chat_attachments.append(file_info)
        self._update_attachment_ui()
    
    def _get_file_type(self, file_path: str) -> str:
        """Determine file type for display."""
        ext = Path(file_path).suffix.lower()
        if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
            return "image"
        elif ext in ['.pdf', '.docx', '.doc', '.txt', '.md', '.xlsx', '.csv', '.pptx']:
            return "document"
        elif ext in ['.py', '.js', '.ts', '.html', '.css', '.json', '.yaml', '.yml', '.cpp', '.c', '.h', '.rs', '.go']:
            return "code"
        elif ext in ['.zip', '.tar', '.gz', '.7z', '.rar']:
            return "archive"
        elif ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm']:
            return "video"
        elif ext in ['.mp3', '.wav', '.flac', '.m4a']:
            return "audio"
        return "file"
    
    def _update_attachment_ui(self):
        """Update attachment display in UI."""
        # Clear existing
        for widget in self.attachment_frame.winfo_children():
            widget.destroy()
        
        if not self.chat_attachments:
            self.attachment_frame.grid_remove()
            return
        
        self.attachment_frame.grid()
        
        for i, att in enumerate(self.chat_attachments):
            att_frame = ctk.CTkFrame(self.attachment_frame, fg_color=self.theme["bg_tertiary"])
            att_frame.pack(fill="x", padx=5, pady=2)
            
            # Icon based on type
            icons = {"image": "🖼️", "document": "📄", "code": "💻", "archive": "📦", "video": "🎬", "audio": "🎵", "file": "📎"}
            icon = icons.get(att["type"], "📎")
            
            ctk.CTkLabel(
                att_frame, text=f"{icon} {att['name']}", font=("Segoe UI", 11),
                text_color=self.theme["text_primary"]
            ).pack(side="left", padx=10, pady=5)
            
            # Size
            size_kb = att['size'] / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            ctk.CTkLabel(
                att_frame, text=size_str, font=("Segoe UI", 9),
                text_color=self.theme["text_muted"]
            ).pack(side="left", padx=10)
            
            # Remove button
            ctk.CTkButton(
                att_frame, text="✕", width=25, height=25,
                fg_color=self.theme["error"], hover_color="#dc2626",
                command=lambda idx=i: self._remove_attachment(idx)
            ).pack(side="right", padx=5)
    
    def _remove_attachment(self, index: int):
        """Remove attachment from list."""
        if 0 <= index < len(self.chat_attachments):
            self.chat_attachments.pop(index)
            self._update_attachment_ui()
    
    def _send_chat(self):
        """Send chat message with attachments."""
        text = self.chat_input.get("1.0", "end-1c").strip()
        if not text and not self.chat_attachments:
            return
        
        self.chat_input.delete("1.0", "end")
        
        # Build message with attachments
        message_parts = [text] if text else []
        
        for att in self.chat_attachments:
            message_parts.append(f"\n[Attached: {att['name']} ({att['type']})]")
        
        full_message = "\n".join(message_parts)
        
        # Add user message with attachment info
        self._add_chat_message("user", full_message)
        
        # Clear attachments after sending
        self.chat_attachments.clear()
        self._update_attachment_ui()
        
        # Process asynchronously
        self._run_async(self._process_chat(full_message))