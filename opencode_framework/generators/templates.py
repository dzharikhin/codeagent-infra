"""Template loading and rendering."""

import json
from importlib.resources import files
from typing import Dict, List, Optional


class TemplateHandler:
    """Handles loading and rendering of template files."""
    
    # Template filenames (without extension)
    DEVCONTAINER_TEMPLATE = "devcontainer.template.json"
    DOCKERFILE_TEMPLATE = "dockerfile.template"
    ENV_TEMPLATE = "env.template"
    COMPOSE_TEMPLATE = "docker-compose.template.yaml"
    README_TEMPLATE = "readme.template.md"
    GITIGNORE_TEMPLATE = "gitignore.template"
    
    @staticmethod
    def load_json_template(template_name: str) -> dict:
        """Load a JSON template file.
        
        Args:
            template_name: Name of template file (e.g., "devcontainer.template.json")
            
        Returns:
            Parsed JSON content as dictionary
        """
        content = files("opencode_framework.templates").joinpath(template_name).read_text()
        return json.loads(content)
    
    @staticmethod
    def load_text_template(template_name: str) -> str:
        """Load a text template file.
        
        Args:
            template_name: Name of template file (e.g., "env.template")
            
        Returns:
            Template content as string
        """
        return files("opencode_framework.templates").joinpath(template_name).read_text()
    
    @staticmethod
    def render_template(template: str, variables: Dict[str, str]) -> str:
        """Render template with variable substitution.
        
        Replaces {{VARIABLE}} placeholders with values from variables dict.
        Variables dict keys should include the full {{VARIABLE}} syntax.
        
        Args:
            template: Template string with {{VARIABLE}} placeholders
            variables: Dictionary mapping full placeholders (with braces) to values
            
        Returns:
            Rendered template with substitutions applied
        """
        result = template
        
        # Replace all {{VARIABLE}} patterns
        for placeholder, value in variables.items():
            result = result.replace(placeholder, value)
        
        return result
    
    @classmethod
    def load_devcontainer_template(cls) -> dict:
        """Load devcontainer template.
        
        Returns:
            Parsed devcontainer.json template
        """
        return cls.load_json_template(cls.DEVCONTAINER_TEMPLATE)
    
    @classmethod
    def load_dockerfile_template(cls) -> str:
        """Load Dockerfile template.
        
        Returns:
            Dockerfile template content
        """
        return cls.load_text_template(cls.DOCKERFILE_TEMPLATE)
    
    @classmethod
    def load_env_template(cls) -> str:
        """Load environment template.
        
        Returns:
            Environment template content
        """
        return cls.load_text_template(cls.ENV_TEMPLATE)
    
    @classmethod
    def load_compose_template(cls) -> str:
        """Load docker-compose template.
        
        Returns:
            Docker compose template content
        """
        return cls.load_text_template(cls.COMPOSE_TEMPLATE)
    
    @classmethod
    def load_readme_template(cls) -> str:
        """Load README template.
        
        Returns:
            README template content
        """
        return cls.load_text_template(cls.README_TEMPLATE)
    
    @classmethod
    def render_env_template(
        cls,
        global_config_path: Optional[str] = None,
        global_auth_path: Optional[str] = None,
        framework_repo_path: Optional[str] = None,
    ) -> str:
        """Render environment template with paths.
        
        Args:
            global_config_path: Path to global config directory
            global_auth_path: Path to global auth.json file
            framework_repo_path: Path to framework repository
            
        Returns:
            Rendered environment template
        """
        template = cls.load_env_template()
        
        replacements = {
            "{{OCF_LOCAL_GLOBAL_CONFIG_PATH}}": global_config_path or "",
            "{{OCF_LOCAL_GLOBAL_AUTH_PATH}}": global_auth_path or "",
            "{{OCF_LOCAL_FRAMEWORK_PATH}}": framework_repo_path or "",
        }
        
        return cls.render_template(template, replacements)
    
    @classmethod
    def render_compose_template(
        cls,
        repo_root_name: str,
        optional_features: Optional[List[str]] = None,
        port_mappings: Optional[List[str]] = None,
    ) -> str:
        """Render docker-compose template with container name.
        
        Args:
            repo_root_name: Name of the repo
            optional_features: List of enabled optional features (e.g., ["python"])
            port_mappings: List of Docker-style port mappings (e.g., ["8080:8080"])
            
        Returns:
            Rendered docker-compose content
        """
        template = cls.load_compose_template()
        
        additional_volume_mounts = ""
        docker_privileged = ""
        entrypoint = '["opencode"]'

        if optional_features and "python" in optional_features:
            additional_volume_mounts += (
                f"\n      - venv-{repo_root_name}:/{repo_root_name}/.venv"
            )

        if optional_features and "java" in optional_features:
            additional_volume_mounts += (
                f"\n      - m2-{repo_root_name}:/home/${{REMOTE_USER}}/.m2"
            )

        if optional_features and "docker" in optional_features:
            docker_privileged = "    privileged: true\n"
            entrypoint = '["/usr/local/share/docker-init.sh", "opencode"]'

        volume_keys = []
        if optional_features and "python" in optional_features:
            volume_keys.append(f"  venv-{repo_root_name}:")
        if optional_features and "java" in optional_features:
            volume_keys.append(f"  m2-{repo_root_name}:")
        top_level_volumes_section = ""
        if volume_keys:
            top_level_volumes_section = (
                "\nvolumes:\n" + "\n".join(volume_keys) + "\n"
            )

        ports_section = ""
        if port_mappings:
            port_lines = "".join(f"      - {p}\n" for p in port_mappings)
            ports_section = f"    ports:\n{port_lines}"

        replacements = {
            "{{OCF_REPO_ROOT_NAME}}": repo_root_name,
            "{{ADDITIONAL_VOLUME_MOUNTS}}": additional_volume_mounts,
            "{{TOP_LEVEL_VOLUMES_SECTION}}": top_level_volumes_section,
            "{{DOCKER_PRIVILEGED}}": docker_privileged,
            "{{PORTS_SECTION}}": ports_section,
            "{{ENTRYPOINT}}": entrypoint,
        }
        
        return cls.render_template(template, replacements)
    
    @classmethod
    def render_readme_template(
        cls,
        launch_command: str,
        debug_command: str,
        shell_command: str,
        branch_name: str,
    ) -> str:
        """Render README template with commands and branch name.
        
        Args:
            launch_command: CLI launch command
            debug_command: CLI debug command
            shell_command: CLI shell command
            branch_name: Git branch name for config worktree
            
        Returns:
            Rendered README content
        """
        template = cls.load_readme_template()
        
        replacements = {
            "{{LAUNCH_COMMAND}}": launch_command,
            "{{DEBUG_COMMAND}}": debug_command,
            "{{SHELL_COMMAND}}": shell_command,
            "{{BRANCH_NAME}}": branch_name,
        }
        
        return cls.render_template(template, replacements)
