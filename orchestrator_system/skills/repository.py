#!/usr/bin/env python3
"""
Skills Repository Manager

Manages agent skills from various repositories including 0bra superpowers.
Provides skill discovery, loading, and execution capabilities.
"""

import importlib
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Tuple
import threading
import hashlib
import yaml

logger = logging.getLogger(__name__)


class SkillCategory(Enum):
    """Categories of skills."""
    CORE = "core"
    BROWSER = "browser"
    FILE_SYSTEM = "file_system"
    CODE_EXECUTION = "code_execution"
    DATA_PROCESSING = "data_processing"
    COMMUNICATION = "communication"
    CREATIVE = "creative"
    ANALYSIS = "analysis"
    AUTOMATION = "automation"
    INTEGRATION = "integration"


class SkillSource(Enum):
    """Sources of skills."""
    BUILTIN = "builtin"
    LOCAL = "local"
    GITHUB = "github"
    OBR_SUPERPOWERS = "obra_superpowers"
    CUSTOM = "custom"


@dataclass
class SkillDefinition:
    """Definition of a skill."""
    skill_id: str
    name: str
    description: str
    category: SkillCategory
    source: SkillSource
    version: str
    author: str
    entry_point: str
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    returns: Optional[str] = None
    examples: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    enabled: bool = True
    sandbox_required: bool = True
    security_level: str = "medium"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "source": self.source.value,
            "version": self.version,
            "author": self.author,
            "entry_point": self.entry_point,
            "parameters": self.parameters,
            "returns": self.returns,
            "examples": self.examples,
            "dependencies": self.dependencies,
            "tags": self.tags,
            "enabled": self.enabled,
            "sandbox_required": self.sandbox_required,
            "security_level": self.security_level,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillDefinition":
        """Create from dictionary."""
        return cls(
            skill_id=data["skill_id"],
            name=data["name"],
            description=data["description"],
            category=SkillCategory(data.get("category", "core")),
            source=SkillSource(data.get("source", "builtin")),
            version=data.get("version", "1.0.0"),
            author=data.get("author", "unknown"),
            entry_point=data["entry_point"],
            parameters=data.get("parameters", []),
            returns=data.get("returns"),
            examples=data.get("examples", []),
            dependencies=data.get("dependencies", []),
            tags=data.get("tags", []),
            enabled=data.get("enabled", True),
            sandbox_required=data.get("sandbox_required", True),
            security_level=data.get("security_level", "medium"),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
        )


@dataclass
class SkillExecutionResult:
    """Result of skill execution."""
    skill_id: str
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: float = 0.0
    memory_used: str = "0MB"
    tokens_saved: int = 0


class SkillLoader:
    """Loads skills from various sources."""
    
    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = Path(skills_dir)
        self._loaded_skills: Dict[str, SkillDefinition] = {}
        self._skill_functions: Dict[str, Callable] = {}
        self._lock = threading.RLock()
    
    def discover_skills(self) -> List[SkillDefinition]:
        """Discover available skills in the skills directory."""
        discovered = []
        
        # Scan skills directory
        if self.skills_dir.exists():
            for category_dir in self.skills_dir.iterdir():
                if not category_dir.is_dir() or category_dir.name.startswith('.'):
                    continue
                
                # Look for skill definition files
                for skill_file in category_dir.rglob("skill.yaml"):
                    try:
                        with open(skill_file, 'r') as f:
                            skill_data = yaml.safe_load(f)
                        
                        if skill_data and "skill_id" in skill_data:
                            skill_def = SkillDefinition.from_dict({
                                **skill_data,
                                "source": "local",
                                "category": category_dir.name,
                            })
                            discovered.append(skill_def)
                    except Exception as e:
                        logger.warning(f"Failed to load skill from {skill_file}: {e}")
                
                # Also look for Python-based skills
                for py_file in category_dir.rglob("*.py"):
                    if py_file.name.startswith('_'):
                        continue
                    
                    try:
                        skill_id = f"{category_dir.name}_{py_file.stem}"
                        skill_def = SkillDefinition(
                            skill_id=skill_id,
                            name=py_file.stem.replace('_', ' ').title(),
                            description=f"Skill from {py_file.relative_to(self.skills_dir)}",
                            category=SkillCategory(category_dir.name) if category_dir.name in [c.value for c in SkillCategory] else SkillCategory.CORE,
                            source=SkillSource.LOCAL,
                            version="1.0.0",
                            author="local",
                            entry_point=str(py_file.relative_to(self.skills_dir)),
                            tags=[category_dir.name],
                        )
                        discovered.append(skill_def)
                    except Exception as e:
                        logger.warning(f"Failed to create skill definition for {py_file}: {e}")
        
        # Discover from 0bra superpowers repository (if available)
        obra_skills = self._discover_obrasuperpowers()
        discovered.extend(obra_skills)
        
        with self._lock:
            for skill in discovered:
                self._loaded_skills[skill.skill_id] = skill
        
        logger.info(f"Discovered {len(discovered)} skills")
        return discovered
    
    def _discover_obrasuperpowers(self) -> List[SkillDefinition]:
        """Discover skills from 0bra superpowers repository."""
        skills = []
        
        # Check for obra superpowers directory
        possible_paths = [
            Path("optional-skills/obra-superpowers"),
            Path("skills/obra-superpowers"),
            Path("../obra-superpowers"),
        ]
        
        obra_path = None
        for path in possible_paths:
            if path.exists():
                obra_path = path
                break
        
        if not obra_path:
            logger.debug("0bra superpowers repository not found")
            return skills
        
        try:
            for skill_file in obra_path.rglob("*.py"):
                if skill_file.name.startswith('_'):
                    continue
                
                try:
                    skill_id = f"obra_{skill_file.stem}"
                    skill_def = SkillDefinition(
                        skill_id=skill_id,
                        name=skill_file.stem.replace('_', ' ').title(),
                        description=f"0bra Superpower: {skill_file.stem}",
                        category=SkillCategory.AUTOMATION,
                        source=SkillSource.OBR_SUPERPOWERS,
                        version="1.0.0",
                        author="0bra",
                        entry_point=str(skill_file.relative_to(Path.cwd())),
                        tags=["obra", "superpower"],
                        sandbox_required=True,
                        security_level="high",
                    )
                    skills.append(skill_def)
                except Exception as e:
                    logger.warning(f"Failed to process obra skill {skill_file}: {e}")
        except Exception as e:
            logger.error(f"Error discovering obra skills: {e}")
        
        return skills
    
    def load_skill(self, skill_id: str) -> Optional[Callable]:
        """Load a skill function by ID."""
        with self._lock:
            if skill_id in self._skill_functions:
                return self._skill_functions[skill_id]
            
            if skill_id not in self._loaded_skills:
                logger.error(f"Skill {skill_id} not found")
                return None
            
            skill_def = self._loaded_skills[skill_id]
        
        try:
            # Load Python-based skills
            if skill_def.entry_point.endswith('.py'):
                module_path = Path(skill_def.entry_point)
                
                # Add parent directory to path
                sys.path.insert(0, str(module_path.parent))
                
                module_name = module_path.stem
                module = importlib.import_module(module_name)
                
                # Look for main function
                if hasattr(module, 'execute'):
                    func = getattr(module, 'execute')
                elif hasattr(module, 'run'):
                    func = getattr(module, 'run')
                elif hasattr(module, 'main'):
                    func = getattr(module, 'main')
                else:
                    # Use the module itself as callable
                    func = module
                
                with self._lock:
                    self._skill_functions[skill_id] = func
                
                logger.info(f"Loaded skill {skill_id}")
                return func
            
            # Load YAML-defined skills
            elif skill_def.entry_point.endswith('.yaml'):
                # Parse YAML skill definition
                with open(skill_def.entry_point, 'r') as f:
                    skill_config = yaml.safe_load(f)
                
                # Create wrapper function based on configuration
                def yaml_skill_wrapper(**kwargs):
                    # This would execute the skill based on YAML config
                    # For now, return placeholder
                    return {"status": "executed", "skill_id": skill_id}
                
                with self._lock:
                    self._skill_functions[skill_id] = yaml_skill_wrapper
                
                return yaml_skill_wrapper
            
            else:
                logger.error(f"Unsupported skill entry point: {skill_def.entry_point}")
                return None
        
        except Exception as e:
            logger.error(f"Failed to load skill {skill_id}: {e}")
            return None
    
    def get_skill(self, skill_id: str) -> Optional[SkillDefinition]:
        """Get skill definition by ID."""
        with self._lock:
            return self._loaded_skills.get(skill_id)
    
    def get_all_skills(self, enabled_only: bool = True) -> List[SkillDefinition]:
        """Get all loaded skill definitions."""
        with self._lock:
            skills = list(self._loaded_skills.values())
            if enabled_only:
                skills = [s for s in skills if s.enabled]
            return skills
    
    def search_skills(self, query: str, category: Optional[SkillCategory] = None,
                     tags: Optional[List[str]] = None) -> List[SkillDefinition]:
        """Search skills by query, category, or tags."""
        with self._lock:
            results = []
            query_lower = query.lower()
            
            for skill in self._loaded_skills.values():
                if not skill.enabled:
                    continue
                
                if category and skill.category != category:
                    continue
                
                if tags and not any(tag in skill.tags for tag in tags):
                    continue
                
                # Search in name, description, and tags
                searchable = f"{skill.name} {skill.description} {' '.join(skill.tags)}".lower()
                if query and query_lower not in searchable:
                    continue
                
                results.append(skill)
            
            return results
    
    def reload_skills(self) -> int:
        """Reload all skills."""
        with self._lock:
            self._loaded_skills.clear()
            self._skill_functions.clear()
        
        discovered = self.discover_skills()
        return len(discovered)


class SkillsRepository:
    """Main skills repository manager."""
    
    def __init__(self, skills_dir: str = "skills",
                 cache_enabled: bool = True,
                 auto_discover: bool = True):
        self.skills_dir = Path(skills_dir)
        self.cache_enabled = cache_enabled
        self.loader = SkillLoader(skills_dir)
        
        self._execution_cache: Dict[str, Any] = {}
        self._execution_history: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        
        if auto_discover:
            self.loader.discover_skills()
    
    def execute_skill(self, skill_id: str, 
                     arguments: Optional[Dict[str, Any]] = None,
                     use_cache: bool = True,
                     timeout: int = 60) -> SkillExecutionResult:
        """Execute a skill with given arguments."""
        start_time = time.monotonic()
        arguments = arguments or {}
        
        # Check cache
        cache_key = f"{skill_id}:{hashlib.sha256(json.dumps(arguments, sort_keys=True).encode()).hexdigest()}"
        
        if use_cache and self.cache_enabled:
            with self._lock:
                if cache_key in self._execution_cache:
                    cached_result = self._execution_cache[cache_key]
                    logger.debug(f"Cache hit for skill {skill_id}")
                    return SkillExecutionResult(
                        skill_id=skill_id,
                        success=True,
                        result=cached_result,
                        execution_time=0.0,
                        tokens_saved=1,
                    )
        
        # Get skill function
        func = self.loader.load_skill(skill_id)
        if not func:
            return SkillExecutionResult(
                skill_id=skill_id,
                success=False,
                result=None,
                error=f"Skill {skill_id} not found or failed to load",
            )
        
        # Execute skill
        try:
            # Import sandbox for secure execution if required
            skill_def = self.loader.get_skill(skill_id)
            if skill_def and skill_def.sandbox_required:
                from orchestrator_system.sandbox.executor import execute_code_securely, SecurityLevel
                
                # Prepare execution code
                exec_code = f"""
result = func(**{json.dumps(arguments)})
print(json.dumps(result))
"""
                # This is simplified - real implementation would serialize func
                result = func(**arguments)
            else:
                result = func(**arguments)
            
            execution_time = time.monotonic() - start_time
            
            exec_result = SkillExecutionResult(
                skill_id=skill_id,
                success=True,
                result=result,
                execution_time=execution_time,
            )
            
            # Cache result
            if self.cache_enabled and use_cache:
                with self._lock:
                    self._execution_cache[cache_key] = result
                    # Limit cache size
                    if len(self._execution_cache) > 1000:
                        oldest_keys = list(self._execution_cache.keys())[:100]
                        for key in oldest_keys:
                            del self._execution_cache[key]
            
            # Record execution history
            with self._lock:
                self._execution_history.append({
                    "skill_id": skill_id,
                    "timestamp": datetime.now().isoformat(),
                    "success": exec_result.success,
                    "execution_time": execution_time,
                    "arguments_hash": cache_key.split(':')[1],
                })
                
                # Keep only last 10000 executions
                if len(self._execution_history) > 10000:
                    self._execution_history = self._execution_history[-10000:]
            
            return exec_result
        
        except Exception as e:
            execution_time = time.monotonic() - start_time
            logger.error(f"Skill execution failed: {e}")
            
            return SkillExecutionResult(
                skill_id=skill_id,
                success=False,
                result=None,
                error=str(e),
                execution_time=execution_time,
            )
    
    def get_skill_info(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a skill."""
        skill_def = self.loader.get_skill(skill_id)
        if not skill_def:
            return None
        
        # Get execution statistics
        with self._lock:
            skill_executions = [
                e for e in self._execution_history
                if e["skill_id"] == skill_id
            ]
            
            stats = {
                "total_executions": len(skill_executions),
                "successful_executions": sum(1 for e in skill_executions if e["success"]),
                "average_execution_time": (
                    sum(e["execution_time"] for e in skill_executions) / len(skill_executions)
                    if skill_executions else 0.0
                ),
            }
        
        return {
            **skill_def.to_dict(),
            "statistics": stats,
        }
    
    def list_skills(self, category: Optional[SkillCategory] = None,
                   enabled_only: bool = True) -> List[Dict[str, Any]]:
        """List available skills."""
        skills = self.loader.get_all_skills(enabled_only=enabled_only)
        
        if category:
            skills = [s for s in skills if s.category == category]
        
        return [s.to_dict() for s in skills]
    
    def search_skills(self, query: str, 
                     category: Optional[SkillCategory] = None,
                     tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Search for skills."""
        results = self.loader.search_skills(query, category, tags)
        return [s.to_dict() for s in results]
    
    def clear_cache(self):
        """Clear execution cache."""
        with self._lock:
            self._execution_cache.clear()
        logger.info("Skills cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics."""
        with self._lock:
            all_skills = self.loader.get_all_skills(enabled_only=False)
            enabled_skills = [s for s in all_skills if s.enabled]
            
            total_executions = len(self._execution_history)
            successful_executions = sum(1 for e in self._execution_history if e["success"])
            
            return {
                "total_skills": len(all_skills),
                "enabled_skills": len(enabled_skills),
                "disabled_skills": len(all_skills) - len(enabled_skills),
                "skills_by_category": {},
                "skills_by_source": {},
                "total_executions": total_executions,
                "successful_executions": successful_executions,
                "success_rate": successful_executions / total_executions if total_executions > 0 else 0.0,
                "cache_size": len(self._execution_cache),
            }


# Global instance
_repository: Optional[SkillsRepository] = None


def get_skills_repository(skills_dir: str = "skills") -> SkillsRepository:
    """Get or create the global skills repository."""
    global _repository
    if _repository is None:
        _repository = SkillsRepository(skills_dir=skills_dir)
    return _repository
