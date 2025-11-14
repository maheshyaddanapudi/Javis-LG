"""
Worker registry with auto-discovery support.
Discovers workers from both Python code and YAML configuration.
"""

from typing import Dict, List, Optional, Type
import inspect
import importlib
import pkgutil
from pathlib import Path
import yaml

from .base import BaseWorkerAgent, WorkerMetadata
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient


class YamlWorkerAgent(BaseWorkerAgent):
    """
    Dynamically created worker from YAML configuration.
    Used when no code implementation exists.
    """
    
    def __init__(self, config: dict):
        self.config = config
        self._metadata = WorkerMetadata(
            name=config["name"],
            description=config["description"],
            capabilities=config["capabilities"],
            priority=config.get("priority", 0),
            enabled=config.get("enabled", True),
            mcp_server_config=config.get("mcp_server")
        )
        self._tools = None
        self._mcp_client = None
    
    def get_metadata(self) -> WorkerMetadata:
        return self._metadata
    
    async def get_tools(self) -> List[BaseTool]:
        """Load tools from MCP server if configured."""
        if self._tools is None and self._metadata.mcp_server_config:
            try:
                self._mcp_client = MultiServerMCPClient({
                    self.config["name"]: self._metadata.mcp_server_config
                })
                self._tools = await self._mcp_client.get_tools()
            except Exception as e:
                print(f"⚠️  Failed to load tools for {self.config['name']}: {e}")
                self._tools = []
        return self._tools or []
    
    async def execute(self, state: Dict) -> Dict:
        """Default pass-through execution."""
        return state


class WorkerRegistry:
    """
    Central registry for all worker agents.
    Supports auto-discovery from code and YAML configuration.
    """
    
    def __init__(self):
        self._workers: Dict[str, BaseWorkerAgent] = {}
        self._metadata: Dict[str, WorkerMetadata] = {}
        self._sources: Dict[str, str] = {}  # Track source: 'code' or 'yaml'
    
    def register(self, worker: BaseWorkerAgent, source: str = "code") -> None:
        """
        Register a worker instance.
        
        Args:
            worker: Worker instance to register
            source: Source type ('code' or 'yaml')
        """
        metadata = worker.get_metadata()
        
        if not metadata.enabled:
            print(f"⊘ Skipping disabled worker: {metadata.name}")
            return
        
        # Handle collision: code wins over YAML
        if metadata.name in self._workers:
            existing_source = self._sources[metadata.name]
            if source == "yaml" and existing_source == "code":
                print(f"⚠️  YAML worker '{metadata.name}' ignored (code version exists)")
                return
            elif source == "code" and existing_source == "yaml":
                print(f"⚠️  Replacing YAML worker '{metadata.name}' with code version")
        
        self._workers[metadata.name] = worker
        self._metadata[metadata.name] = metadata
        self._sources[metadata.name] = source
        
        source_icon = "📄" if source == "yaml" else "🔧"
        print(f"{source_icon} Registered: {metadata.name} ({source})")
    
    def get_worker(self, name: str) -> Optional[BaseWorkerAgent]:
        """Get worker by name."""
        return self._workers.get(name)
    
    def get_all_workers(self) -> List[BaseWorkerAgent]:
        """Get all registered workers."""
        return list(self._workers.values())
    
    def get_all_metadata(self) -> List[WorkerMetadata]:
        """Get metadata for all workers, sorted by priority."""
        return sorted(
            self._metadata.values(),
            key=lambda x: x.priority,
            reverse=True
        )
    
    def load_from_yaml(self, yaml_path: str = "config/workers.yaml") -> None:
        """
        Load workers from YAML configuration.
        
        Args:
            yaml_path: Path to YAML configuration file
        """
        print(f"\n📄 Loading YAML workers from: {yaml_path}")
        
        if not Path(yaml_path).exists():
            print(f"⚠️  YAML config not found: {yaml_path}")
            return
        
        try:
            with open(yaml_path, 'r') as f:
                config = yaml.safe_load(f)
            
            for worker_config in config.get("workers", []):
                # Skip if explicitly marked as code-based
                if worker_config.get("type") == "code":
                    continue
                
                # Create YAML-based worker
                worker = YamlWorkerAgent(worker_config)
                self.register(worker, source="yaml")
        
        except Exception as e:
            print(f"❌ Error loading YAML workers: {e}")
    
    def auto_discover(self, package_name: str = "workers") -> None:
        """
        Auto-discover worker implementations from Python package.
        
        Args:
            package_name: Python package to scan for workers
        """
        print(f"\n🔧 Auto-discovering code workers in: {package_name}")
        
        try:
            package = importlib.import_module(package_name)
            package_path = Path(package.__file__).parent
            
            # Iterate through all Python files in package
            for _, module_name, _ in pkgutil.iter_modules([str(package_path)]):
                if module_name.startswith('_'):
                    continue
                
                try:
                    module = importlib.import_module(f"{package_name}.{module_name}")
                    
                    # Find all classes that implement BaseWorkerAgent
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if (issubclass(obj, BaseWorkerAgent) and 
                            obj is not BaseWorkerAgent and
                            not inspect.isabstract(obj)):
                            
                            # Instantiate and register
                            worker_instance = obj()
                            self.register(worker_instance, source="code")
                
                except Exception as e:
                    print(f"⚠️  Error loading module {module_name}: {e}")
        
        except ImportError as e:
            print(f"⚠️  Warning: Could not import package {package_name}: {e}")
    
    def auto_discover_all(self, package_name: str = "workers") -> None:
        """
        Complete discovery process:
        1. Load YAML workers first
        2. Auto-discover code workers (which override YAML)
        
        Args:
            package_name: Python package to scan for workers
        """
        print("\n" + "="*60)
        print("🔍 Worker Discovery Process")
        print("="*60)
        
        # Step 1: YAML workers
        self.load_from_yaml()
        
        # Step 2: Code workers (will override YAML if collision)
        self.auto_discover(package_name)
        
        print("\n" + "="*60)
        print(f"✅ Discovery complete: {len(self._workers)} workers registered")
        print("="*60)
        
        # Summary
        code_workers = [k for k, v in self._sources.items() if v == "code"]
        yaml_workers = [k for k, v in self._sources.items() if v == "yaml"]
        
        if code_workers:
            print(f"\n🔧 Code workers: {', '.join(code_workers)}")
        if yaml_workers:
            print(f"📄 YAML workers: {', '.join(yaml_workers)}")


# Global registry instance
worker_registry = WorkerRegistry()
