import re

with open(r'src\active_assistant\ui\main_window.py', 'r') as f:
    content = f.read()

# Replace the _create_provider_row method completely
old_create_provider_row = '''    def _create_provider_row(self, section, prov, cfg):
        """Create a row for a built-in provider."""
        frame = ctk.CTkFrame(section, fg_color="transparent")
        frame.pack(fill="x", pady=8)
        
        prov_cfg = get_config().api_providers.get(prov["id"])
        enabled = prov_cfg.enabled if prov_cfg else False
        default = prov_cfg.default if prov_cfg else False
        
        # Header with icon
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", pady=4)
        
        var = ctk.BooleanVar(value=enabled)
        self.api_vars[f"{prov['id']}_enabled"] = var
        
        ctk.CTkCheckBox(
            header, text=f"{prov['icon']} {prov['name']}", variable=var,
            font=("Segoe UI", 12, "bold"), text_color=self.theme["text_primary"]
        ).pack(side="left", padx=10)
        
        if default:
            ctk.CTkLabel(
                header, text="⭐ Default", font=("Segoe UI", 10),
                text_color=self.theme["accent"]
            ).pack(side="left", padx=10)
        
        # API Key entry
        key_var = ctk.StringVar(value="")
        self.api_vars[f"{prov['id']}_key"] = key_var
        
        key_frame = ctk.CTkFrame(frame, fg_color="transparent")
        key_frame.pack(fill="x", padx=40, pady=4)
        
        # Show/hide password toggle
        show_var = ctk.BooleanVar(value=False)
        
        def toggle_show():
            key_entry.configure(show="" if show_var.get() else "•")
        
        key_entry = ctk.CTkEntry(
            key_frame, placeholder_text=f"{prov['name']} API Key", textvariable=key_var,
            font=("Segoe UI", 11), show="•", width=300
        )
        key_entry.pack(side="left", padx=(0, 10))
        
        ctk.CTkCheckBox(
            key_frame, text="👁️", variable=show_var, width=30,
            command=toggle_show, font=("Segoe UI", 12)
        ).pack(side="left")
        
        # Test connection button
        ctk.CTkButton(
            key_frame, text="🔗 Test", width=80, font=("Segoe UI", 10),
            fg_color=self.theme["accent"],
            command=lambda p=prov["id"]: self._test_provider_connection(p)
        ).pack(side="right", padx=5)
        
        # Save to .env button
        ctk.CTkButton(
            key_frame, text="💾 Save to .env", width=100, font=("Segoe UI", 10),
            fg_color=self.theme["success"],
            command=lambda p=prov["id"], env=prov["env_var"]: self._save_api_key_to_env(p, env)
        ).pack(side="right", padx=5)
'''

new_create_provider_row = '''    def _create_provider_row(self, section, prov, cfg):
        """Create a row for a built-in provider with model auto-detection."""
        frame = ctk.CTkFrame(section, fg_color="transparent")
        frame.pack(fill="x", pady=8)
        
        prov_cfg = get_config().api_providers.get(prov["id"])
        enabled = prov_cfg.enabled if prov_cfg else False
        default = prov_cfg.default if prov_cfg else False
        
        # Store frame data for later updates
        frame_data = {
            "frame": frame,
            "status_var": ctk.StringVar(value="⚪ Unknown"),
            "model_var": ctk.StringVar(value=""),
            "models_combo": None,
            "model_var": ctk.StringVar(value=""),
        }
        self.provider_frames[prov["id"]] = frame_data
        
        # Header with icon and status
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", pady=4)
        
        var = ctk.BooleanVar(value=enabled)
        self.api_vars[f"{prov['id']}_enabled"] = var
        
        ctk.CTkCheckBox(
            header, text=f"{prov['icon']} {prov['name']}", variable=var,
            font=("Segoe UI", 12, "bold"), text_color=self.theme["text_primary"],
            command=lambda p=prov["id"]: self._on_provider_toggled(p)
        ).pack(side="left", padx=10)
        
        if default:
            ctk.CTkLabel(
                header, text="⭐ Default", font=("Segoe UI", 10),
                text_color=self.theme["accent"]
            ).pack(side="left", padx=10)
        
        # Status indicator
        status_label = ctk.CTkLabel(
            header, textvariable=frame_data["status_var"],
            font=("Segoe UI", 10), text_color=self.theme["text_muted"]
        )
        status_label.pack(side="left", padx=10)
        
        # API Key entry
        key_var = ctk.StringVar(value="")
        self.api_vars[f"{prov['id']}_key"] = key_var
        
        key_frame = ctk.CTkFrame(frame, fg_color="transparent")
        key_frame.pack(fill="x", padx=40, pady=4)
        
        # Show/hide password toggle
        show_var = ctk.BooleanVar(value=False)
        
        def toggle_show(p=prov['id']):
            entry = self._get_key_entry(p)
            if entry:
                entry.configure(show="" if show_var.get() else "•")
        
        key_entry = ctk.CTkEntry(
            key_frame, placeholder_text=f"{prov['name']} API Key", textvariable=key_var,
            font=("Segoe UI", 11), show="•", width=250
        )
        key_entry.pack(side="left", padx=(0, 10))
        
        ctk.CTkCheckBox(
            key_frame, text="👁️", variable=show_var, width=30,
            command=toggle_show, font=("Segoe UI", 12)
        ).pack(side="left")
        
        # Model selection dropdown (for providers with model detection)
        if prov.get("models_endpoint") or prov.get("local"):
            self._add_model_dropdown(key_frame, prov)
        
        # Test connection button
        ctk.CTkButton(
            key_frame, text="🔗 Test", width=70, font=("Segoe UI", 10),
            fg_color=self.theme["accent"],
            command=lambda p=prov["id"]: self._test_provider_connection(p)
        ).pack(side="right", padx=3)
        
        # Auto-detect models button (for Ollama and cloud providers)
        if prov.get("models_endpoint") or prov.get("local"):
            ctk.CTkButton(
                key_frame, text="🔍 Detect Models", width=100, font=("Segoe UI", 10),
                fg_color=self.theme["info"],
                command=lambda p=prov["id"]: self._detect_provider_models(p)
            ).pack(side="right", padx=3)
        
        # Save to .env button
        if prov.get("env_var"):
            ctk.CTkButton(
                key_frame, text="💾 Save", width=80, font=("Segoe UI", 10),
                fg_color=self.theme["success"],
                command=lambda p=prov["id"], env=prov["env_var"]: self._save_api_key_to_env(p, env)
            ).pack(side="right", padx=3)
        
        # Set as default button
        ctk.CTkButton(
            key_frame, text="⭐ Default", width=80, font=("Segoe UI", 10),
            fg_color=self.theme["warning"],
            command=lambda p=prov["id"]: self._set_default_provider(p)
        ).pack(side="right", padx=3)
        
        return frame
    
    def _get_key_entry(self, provider_id: str):
        """Find the key entry widget for a provider."""
        frame_data = self.provider_frames.get(provider_id)
        if frame_data and "frame" in frame_data:
            frame = frame_data["frame"]
            for child in frame.winfo_children():
                if isinstance(child, ctk.CTkFrame):
                    for widget in child.winfo_children():
                        if isinstance(widget, ctk.CTkEntry) and "API Key" in str(widget.cget("placeholder_text")):
                            return widget
        return None
    
    def _add_model_dropdown(self, parent_frame, prov):
        """Add model selection dropdown with auto-detection."""
        provider_id = prov["id"]
        frame_data = self.provider_frames.get(provider_id, {})
        
        model_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        model_frame.pack(fill="x", padx=40, pady=(4, 0))
        
        ctk.CTkLabel(
            model_frame, text="Model:", font=("Segoe UI", 10),
            text_color=self.theme["text_secondary"], width=60
        ).pack(side="left", padx=(0, 10))
        
        model_var = ctk.StringVar(value="")
        self.api_vars[f"{provider_id}_model"] = model_var
        frame_data["model_var"] = model_var
        
        combo = ctk.CTkComboBox(
            model_frame, variable=model_var, width=300, font=("Segoe UI", 10),
            values=["Loading..."], state="readonly"
        )
        combo.pack(side="left", padx=(0, 10))
        frame_data["models_combo"] = combo
        frame_data["model_var"] = model_var
        
        # Set default from config
        prov_cfg = get_config().api_providers.get(prov["id"])
        if prov_cfg and prov_cfg.models:
            default_model = prov_cfg.models.get("chat") or prov_cfg.models.get("vision") or ""
            if default_model:
                model_var.set(default_model)
        
        # Refresh models button
        ctk.CTkButton(
            model_frame, text="↻", width=30, font=("Segoe UI", 10),
            fg_color=self.theme["accent"],
            command=lambda p=prov["id"]: self._detect_provider_models(p)
        ).pack(side="left", padx=3)
'''

content = content.replace(old_create_provider_row, new_create_provider_row)

with open(r'src\active_assistant\ui\main_window.py', 'w') as f:
    f.write(content)

print('Done')