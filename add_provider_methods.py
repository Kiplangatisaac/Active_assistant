import re

with open(r'src\active_assistant\ui\main_window.py', 'r') as f:
    content = f.read()

# Find the _clear_custom_provider_form method and add new methods after it
new_methods = '''

    def _refresh_providers(self):
        """Refresh all provider statuses and models."""
        self._update_provider_status()
        for prov_id in self.provider_frames:
            self._detect_provider_models(prov_id)
    
    def _update_provider_status(self):
        """Update provider status labels."""
        for prov_id, frame_data in self.provider_frames.items():
            status_var = frame_data.get("status_var")
            if status_var:
                key_var = self.api_vars.get(f"{prov_id}_key")
                if key_var and key_var.get().strip():
                    status_var.set("🟢 Connected")
                else:
                    status_var.set("🔴 Not configured")
    
    def _on_provider_toggled(self, provider_id: str):
        """Handle provider enable/disable toggle."""
        enabled = self.api_vars.get(f"{provider_id}_enabled", ctk.BooleanVar()).get()
        cfg = get_config()
        if provider_id in cfg.api_providers:
            prov_cfg = cfg.api_providers[provider_id]
            prov_cfg.enabled = enabled
            cfg.save()
            self._add_activity("Provider", f"{provider_id} {'enabled' if enabled else 'disabled'}", "info")
    
    def _detect_provider_models(self, provider_id: str):
        """Auto-detect models for a provider (Ollama or cloud)."""
        frame_data = self.provider_frames.get(provider_id)
        if not frame_data:
            return
        
        status_var = frame_data.get("status_var")
        if status_var:
            status_var.set("🟡 Detecting...")
        
        prov_cfg = get_config().api_providers.get(provider_id)
        if not prov_cfg:
            if status_var:
                status_var.set("🔴 Not configured")
            return
        
        # Get provider info
        base_url = prov_cfg.base_url or ""
        api_key = ""
        key_var = self.api_vars.get(f"{provider_id}_key")
        if key_var:
            api_key = key_var.get().strip()
        
        # Run detection in background
        self._run_async(self._async_detect_models(provider_id, base_url, api_key))
    
    async def _async_detect_models(self, provider_id: str, base_url: str, api_key: str):
        """Detect models asynchronously for a provider."""
        try:
            models = []
            
            if provider_id == "ollama":
                # Ollama local model detection
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{base_url}/api/tags", timeout=5) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            models = [m["name"] for m in data.get("models", [])]
            elif provider_id in ["groq", "openai"]:
                # Cloud provider model detection
                import aiohttp
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                async with aiohttp.ClientSession() as session:
                    models_endpoint = f"{base_url}/models" if provider_id != "anthropic" else None
                    if models_endpoint:
                        async with session.get(models_endpoint, headers=headers, timeout=10) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if provider_id == "groq":
                                    models = [m["id"] for m in data.get("data", [])]
                                elif provider_id == "openai":
                                    models = [m["id"] for m in data.get("data", [])]
            elif provider_id == "anthropic":
                # Anthropic has known models
                models = [
                    "claude-3-5-sonnet-20241022",
                    "claude-3-5-haiku-20241022",
                    "claude-3-opus-20240229",
                    "claude-3-sonnet-20240229",
                    "claude-3-haiku-20240307"
                ]
            
            # Update UI on main thread
            if models:
                frame_data = self.provider_frames.get(provider_id)
                if frame_data and "models_combo" in frame_data:
                    combo = frame_data["models_combo"]
                    model_var = frame_data.get("model_var")
                    if combo:
                        combo.configure(values=sorted(models))
                        if models and not model_var.get():
                            model_var.set(models[0])
                
                # Update config with detected models
                cfg = get_config()
                if provider_id in cfg.api_providers:
                    prov_cfg = cfg.api_providers[provider_id]
                    if not prov_cfg.models:
                        prov_cfg.models = {}
                    # Map models to categories
                    model_map = {
                        "vision": next((m for m in models if "vision" in m.lower()), models[0]),
                        "chat": next((m for m in models if "chat" in m.lower() or "sonnet" in m.lower()), models[0]),
                        "fast": next((m for m in models if "fast" in m.lower() or "mini" in m.lower() or "haiku" in m.lower()), models[0]),
                        "reasoning": next((m for m in models if "reason" in m.lower() or "opus" in m.lower()), models[0]),
                    }
                    prov_cfg.models.update({k: v for k, v in model_map.items() if v})
                    cfg.save()
                
                self.after(0, lambda: self.provider_frames[provider_id]["status_var"].set(f"🟢 {len(models)} models"))
                self._add_activity("Models Detected", f"{provider_id}: {len(models)} models found", "success")
            else:
                self.after(0, lambda: self.provider_frames[provider_id]["status_var"].set("🟡 No models"))
                
        except Exception as e:
            self.after(0, lambda: self.provider_frames[provider_id]["status_var"].set("🔴 Error"))
            self._add_activity("Detection Failed", f"{provider_id}: {str(e)}", "error")

'''

# Find the _clear_custom_provider_form method and insert new methods after it
old_clear = '''    def _clear_custom_provider_form(self):
        """Clear custom provider form."""
        for key, var in self.custom_provider_vars.items():
            if key == "models":
                for v in var.values():
                    if isinstance(v, ctk.StringVar):
                        v.set("")
            elif isinstance(var, ctk.StringVar):
                var.set("")
    
    def _create_permissions_settings(self, parent):'''

new_clear = '''    def _clear_custom_provider_form(self):
        """Clear custom provider form."""
        for key, var in self.custom_provider_vars.items():
            if key == "models":
                for v in var.values():
                    if isinstance(v, ctk.StringVar):
                        v.set("")
            elif isinstance(var, ctk.StringVar):
                var.set("")

''' + new_methods + '''

    def _create_permissions_settings(self, parent):'''

content = content.replace(old_clear, new_clear)

with open(r'src\active_assistant\ui\main_window.py', 'w') as f:
    f.write(content)

print('Done')