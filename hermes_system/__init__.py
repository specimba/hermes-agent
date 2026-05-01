"""
HERMES - Hierarchical Executive Resource Management & Execution System
Quick Start Ready for OpenCLAW Integration
Experience Layer Implementation
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
import queue
import hashlib
import sqlite3
from contextlib import contextmanager
import subprocess
import tempfile
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('hermes_system.log')
    ]
)
logger = logging.getLogger("HERMES")

# ============================================================================
# CORE ENUMS AND DATA CLASSES
# ============================================================================

class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"
    WAITING = "waiting"

class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class MemoryType(Enum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"

class SecurityLevel(Enum):
    SANDBOXED = "sandboxed"
    RESTRICTED = "restricted"
    STANDARD = "standard"
    PRIVILEGED = "privileged"

@dataclass
class AgentConfig:
    id: str
    name: str
    task_type: str
    strictness_level: int
    deployment_date: str
    status: str = AgentStatus.IDLE.value
    group_id: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    memory_enabled: bool = True
    sandbox_enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class Task:
    id: str
    description: str
    agent_id: Optional[str]
    priority: int
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    feedback_score: Optional[int] = None
    feedback_comment: Optional[str] = None

@dataclass
class AgentGroup:
    id: str
    name: str
    criteria_type: str  # task_type, strictness, deployment_date
    criteria_value: Any
    agent_ids: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class Feedback:
    id: str
    agent_id: str
    task_id: str
    score: int  # 1-5 or -1/1 for thumbs
    comment: Optional[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

# ============================================================================
# MEMORY LAYER WITH CACHE SYSTEM
# ============================================================================

class MemoryManager:
    """Persistent memory layer with LRU caching for token optimization"""
    
    def __init__(self, db_path: str = "hermes_memory.db"):
        self.db_path = db_path
        self.cache = {}  # LRU cache
        self.cache_max_size = 1000
        self._init_db()
        
    def _init_db(self):
        """Initialize SQLite database for persistent memory"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                agent_id TEXT,
                memory_type TEXT,
                content TEXT,
                metadata TEXT,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT,
                created_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS semantic_cache (
                hash_key TEXT PRIMARY KEY,
                response TEXT,
                tokens_used INTEGER,
                created_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_agent_memory 
            ON memories(agent_id, memory_type)
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Memory database initialized")
    
    def _generate_cache_key(self, prompt: str) -> str:
        """Generate hash key for semantic caching"""
        return hashlib.sha256(prompt.encode()).hexdigest()
    
    def get_cached_response(self, prompt: str) -> Optional[str]:
        """Check semantic cache for existing response"""
        cache_key = self._generate_cache_key(prompt)
        
        if cache_key in self.cache:
            logger.debug(f"Cache hit for key: {cache_key[:16]}...")
            return self.cache[cache_key]
        
        # Check database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT response FROM semantic_cache WHERE hash_key = ?",
            (cache_key,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if result:
            self.cache[cache_key] = result[0]
            self._manage_cache_size()
            logger.debug(f"DB cache hit for key: {cache_key[:16]}...")
            return result[0]
        
        return None
    
    def store_cached_response(self, prompt: str, response: str, tokens_used: int):
        """Store response in semantic cache"""
        cache_key = self._generate_cache_key(prompt)
        self.cache[cache_key] = response
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO semantic_cache 
            (hash_key, response, tokens_used, created_at)
            VALUES (?, ?, ?, ?)
        ''', (cache_key, response, tokens_used, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        self._manage_cache_size()
        logger.debug(f"Stored cached response: {cache_key[:16]}...")
    
    def _manage_cache_size(self):
        """Manage LRU cache size"""
        if len(self.cache) > self.cache_max_size:
            # Remove oldest entries
            oldest_keys = list(self.cache.keys())[:100]
            for key in oldest_keys:
                del self.cache[key]
    
    def add_memory(self, agent_id: str, memory_type: MemoryType, 
                   content: str, metadata: Dict = None):
        """Add memory for an agent"""
        memory_id = str(uuid.uuid4())
        metadata_json = json.dumps(metadata or {})
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO memories 
            (id, agent_id, memory_type, content, metadata, last_accessed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (memory_id, agent_id, memory_type.value, content, 
              metadata_json, datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        logger.info(f"Added {memory_type.value} memory for agent {agent_id}")
        return memory_id
    
    def get_memories(self, agent_id: str, memory_type: Optional[MemoryType] = None,
                     limit: int = 10) -> List[Dict]:
        """Retrieve memories for an agent"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if memory_type:
            cursor.execute('''
                SELECT content, metadata, last_accessed, created_at
                FROM memories
                WHERE agent_id = ? AND memory_type = ?
                ORDER BY last_accessed DESC
                LIMIT ?
            ''', (agent_id, memory_type.value, limit))
        else:
            cursor.execute('''
                SELECT content, metadata, last_accessed, created_at
                FROM memories
                WHERE agent_id = ?
                ORDER BY last_accessed DESC
                LIMIT ?
            ''', (agent_id, limit))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'content': row[0],
                'metadata': json.loads(row[1]),
                'last_accessed': row[2],
                'created_at': row[3]
            })
            
            # Update access count
            cursor.execute('''
                UPDATE memories 
                SET access_count = access_count + 1, last_accessed = ?
                WHERE agent_id = ? AND content = ?
            ''', (datetime.now().isoformat(), agent_id, row[0]))
        
        conn.commit()
        conn.close()
        return results
    
    def clear_agent_memories(self, agent_id: str):
        """Clear all memories for an agent"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM memories WHERE agent_id = ?",
            (agent_id,)
        )
        conn.commit()
        conn.close()
        logger.info(f"Cleared memories for agent {agent_id}")

# ============================================================================
# NVIDIA OPEN SHELL SANDBOX ENVIRONMENT
# ============================================================================

class SandboxEnvironment:
    """Secure code execution sandbox with containerized isolation"""
    
    def __init__(self, security_level: SecurityLevel = SecurityLevel.SANDBOXED):
        self.security_level = security_level
        self.temp_dirs = []
        self.max_execution_time = 30  # seconds
        self.max_memory_mb = 512
        self.allowed_imports = self._get_allowed_imports()
        
    def _get_allowed_imports(self) -> List[str]:
        """Get allowed imports based on security level"""
        base_imports = ['math', 'json', 're', 'datetime', 'collections', 'itertools']
        
        if self.security_level == SecurityLevel.PRIVILEGED:
            return base_imports + ['numpy', 'pandas', 'requests', 'asyncio']
        elif self.security_level == SecurityLevel.STANDARD:
            return base_imports + ['numpy', 'asyncio']
        else:
            return base_imports
    
    @contextmanager
    def create_sandbox(self):
        """Create isolated sandbox environment"""
        temp_dir = tempfile.mkdtemp(prefix='hermes_sandbox_')
        self.temp_dirs.append(temp_dir)
        
        # Create security constraints
        constraints_file = os.path.join(temp_dir, 'constraints.txt')
        with open(constraints_file, 'w') as f:
            f.write(f"max_execution_time={self.max_execution_time}\n")
            f.write(f"max_memory_mb={self.max_memory_mb}\n")
            f.write(f"allowed_imports={','.join(self.allowed_imports)}\n")
        
        try:
            yield temp_dir
        finally:
            self.cleanup_sandbox(temp_dir)
    
    def cleanup_sandbox(self, temp_dir: str):
        """Cleanup sandbox environment"""
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            if temp_dir in self.temp_dirs:
                self.temp_dirs.remove(temp_dir)
            logger.info(f"Cleaned up sandbox: {temp_dir}")
    
    def execute_code(self, code: str, language: str = 'python', 
                     timeout: Optional[int] = None) -> Dict:
        """Execute code in sandboxed environment"""
        result = {
            'success': False,
            'output': '',
            'error': '',
            'execution_time': 0,
            'memory_used': 0
        }
        
        timeout = timeout or self.max_execution_time
        
        with self.create_sandbox() as sandbox_dir:
            start_time = time.time()
            
            try:
                if language == 'python':
                    result = self._execute_python(code, sandbox_dir, timeout)
                elif language == 'bash':
                    result = self._execute_bash(code, sandbox_dir, timeout)
                else:
                    result['error'] = f"Unsupported language: {language}"
                    
            except Exception as e:
                result['error'] = str(e)
                logger.error(f"Sandbox execution error: {e}")
            
            result['execution_time'] = time.time() - start_time
            
        return result
    
    def _execute_python(self, code: str, sandbox_dir: str, timeout: int) -> Dict:
        """Execute Python code in sandbox"""
        script_path = os.path.join(sandbox_dir, 'script.py')
        
        # Validate imports
        if not self._validate_imports(code):
            return {
                'success': False,
                'output': '',
                'error': 'Unauthorized import detected',
                'execution_time': 0,
                'memory_used': 0
            }
        
        with open(script_path, 'w') as f:
            f.write(code)
        
        try:
            # Execute with timeout and resource limits
            cmd = [
                sys.executable,
                '-c',
                f'''
import sys
sys.path.insert(0, "{sandbox_dir}")
exec(open("{script_path}").read())
                '''
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=sandbox_dir
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                return {
                    'success': process.returncode == 0,
                    'output': stdout,
                    'error': stderr,
                    'execution_time': 0,
                    'memory_used': 0
                }
            except subprocess.TimeoutExpired:
                process.kill()
                return {
                    'success': False,
                    'output': '',
                    'error': f'Execution timeout after {timeout}s',
                    'execution_time': timeout,
                    'memory_used': 0
                }
                
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': str(e),
                'execution_time': 0,
                'memory_used': 0
            }
    
    def _execute_bash(self, code: str, sandbox_dir: str, timeout: int) -> Dict:
        """Execute bash commands in sandbox"""
        script_path = os.path.join(sandbox_dir, 'script.sh')
        
        with open(script_path, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write(code)
        
        os.chmod(script_path, 0o755)
        
        try:
            process = subprocess.Popen(
                ['bash', script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=sandbox_dir
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                return {
                    'success': process.returncode == 0,
                    'output': stdout,
                    'error': stderr,
                    'execution_time': 0,
                    'memory_used': 0
                }
            except subprocess.TimeoutExpired:
                process.kill()
                return {
                    'success': False,
                    'output': '',
                    'error': f'Execution timeout after {timeout}s',
                    'execution_time': timeout,
                    'memory_used': 0
                }
                
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': str(e),
                'execution_time': 0,
                'memory_used': 0
            }
    
    def _validate_imports(self, code: str) -> bool:
        """Validate that only allowed imports are used"""
        import ast
        
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split('.')[0] not in self.allowed_imports:
                            return False
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split('.')[0] not in self.allowed_imports:
                        return False
            return True
        except:
            return False

# ============================================================================
# SKILLS REPOSITORY MANAGER (0bra Superpowers Integration)
# ============================================================================

class SkillsRepository:
    """Manage agent skills from 0bra superpowers repository"""
    
    def __init__(self):
        self.skills = {}
        self.skill_categories = {}
        self.execution_cache = {}
        self._load_default_skills()
    
    def _load_default_skills(self):
        """Load default skills based on 0bra superpowers patterns"""
        default_skills = {
            'data_analysis': {
                'category': 'analytics',
                'description': 'Analyze datasets and generate insights',
                'parameters': ['dataset', 'analysis_type'],
                'code_template': 'analyze_data({dataset}, {analysis_type})'
            },
            'web_scraping': {
                'category': 'data_collection',
                'description': 'Extract data from websites',
                'parameters': ['url', 'selectors'],
                'code_template': 'scrape_web({url}, {selectors})'
            },
            'text_processing': {
                'category': 'nlp',
                'description': 'Process and analyze text content',
                'parameters': ['text', 'operation'],
                'code_template': 'process_text({text}, {operation})'
            },
            'image_recognition': {
                'category': 'computer_vision',
                'description': 'Analyze and classify images',
                'parameters': ['image_path', 'model'],
                'code_template': 'recognize_image({image_path}, {model})'
            },
            'code_generation': {
                'category': 'development',
                'description': 'Generate code snippets',
                'parameters': ['language', 'requirements'],
                'code_template': 'generate_code({language}, {requirements})'
            },
            'api_integration': {
                'category': 'integration',
                'description': 'Integrate with external APIs',
                'parameters': ['endpoint', 'method', 'payload'],
                'code_template': 'call_api({endpoint}, {method}, {payload})'
            }
        }
        
        self.skills = default_skills
        
        # Categorize skills
        for skill_name, skill_data in default_skills.items():
            category = skill_data['category']
            if category not in self.skill_categories:
                self.skill_categories[category] = []
            self.skill_categories[category].append(skill_name)
        
        logger.info(f"Loaded {len(self.skills)} default skills")
    
    def discover_skills(self) -> Dict[str, List[str]]:
        """Discover available skills by category"""
        return self.skill_categories
    
    def get_skill(self, skill_name: str) -> Optional[Dict]:
        """Get skill details"""
        return self.skills.get(skill_name)
    
    def search_skills(self, query: str) -> List[Dict]:
        """Search skills by keyword"""
        results = []
        query_lower = query.lower()
        
        for skill_name, skill_data in self.skills.items():
            if (query_lower in skill_name.lower() or 
                query_lower in skill_data['description'].lower() or
                query_lower in skill_data['category'].lower()):
                results.append({
                    'name': skill_name,
                    **skill_data
                })
        
        return results
    
    def execute_skill(self, skill_name: str, parameters: Dict, 
                      use_cache: bool = True) -> Any:
        """Execute a skill with optional caching"""
        cache_key = f"{skill_name}:{hash(frozenset(parameters.items()))}"
        
        if use_cache and cache_key in self.execution_cache:
            logger.debug(f"Skill cache hit: {skill_name}")
            return self.execution_cache[cache_key]
        
        skill = self.get_skill(skill_name)
        if not skill:
            raise ValueError(f"Skill not found: {skill_name}")
        
        # Simulate skill execution (in real implementation, this would call actual code)
        result = self._simulate_skill_execution(skill_name, parameters)
        
        if use_cache:
            self.execution_cache[cache_key] = result
        
        return result
    
    def _simulate_skill_execution(self, skill_name: str, parameters: Dict) -> Dict:
        """Simulate skill execution for demonstration"""
        return {
            'skill': skill_name,
            'parameters': parameters,
            'status': 'completed',
            'result': f"Executed {skill_name} with params: {parameters}",
            'timestamp': datetime.now().isoformat()
        }

# ============================================================================
# AGENT GROUPING SYSTEM
# ============================================================================

class AgentGroupManager:
    """Manage agent groups based on various criteria"""
    
    def __init__(self):
        self.groups: Dict[str, AgentGroup] = {}
    
    def create_group(self, name: str, criteria_type: str, 
                     criteria_value: Any) -> AgentGroup:
        """Create a new agent group"""
        group_id = str(uuid.uuid4())
        group = AgentGroup(
            id=group_id,
            name=name,
            criteria_type=criteria_type,
            criteria_value=criteria_value
        )
        self.groups[group_id] = group
        logger.info(f"Created group: {name} ({criteria_type}: {criteria_value})")
        return group
    
    def delete_group(self, group_id: str) -> bool:
        """Delete a group"""
        if group_id in self.groups:
            del self.groups[group_id]
            logger.info(f"Deleted group: {group_id}")
            return True
        return False
    
    def assign_agent_to_group(self, group_id: str, agent_id: str) -> bool:
        """Assign an agent to a group"""
        if group_id not in self.groups:
            return False
        
        group = self.groups[group_id]
        if agent_id not in group.agent_ids:
            group.agent_ids.append(agent_id)
            logger.info(f"Assigned agent {agent_id} to group {group.name}")
        
        return True
    
    def remove_agent_from_group(self, group_id: str, agent_id: str) -> bool:
        """Remove an agent from a group"""
        if group_id not in self.groups:
            return False
        
        group = self.groups[group_id]
        if agent_id in group.agent_ids:
            group.agent_ids.remove(agent_id)
            logger.info(f"Removed agent {agent_id} from group {group.name}")
            return True
        
        return False
    
    def auto_assign_agents(self, agents: List[AgentConfig]) -> None:
        """Auto-assign agents to groups based on criteria"""
        for agent in agents:
            for group in self.groups.values():
                should_assign = False
                
                if group.criteria_type == 'task_type':
                    should_assign = agent.task_type == group.criteria_value
                elif group.criteria_type == 'strictness':
                    should_assign = agent.strictness_level == group.criteria_value
                elif group.criteria_type == 'deployment_date':
                    # Group by month/year
                    agent_month = agent.deployment_date[:7]
                    should_assign = agent_month == group.criteria_value
                
                if should_assign:
                    self.assign_agent_to_group(group.id, agent.id)
    
    def get_groups_for_agent(self, agent_id: str) -> List[AgentGroup]:
        """Get all groups an agent belongs to"""
        return [
            group for group in self.groups.values()
            if agent_id in group.agent_ids
        ]
    
    def get_agents_in_group(self, group_id: str) -> List[str]:
        """Get all agents in a group"""
        if group_id in self.groups:
            return self.groups[group_id].agent_ids
        return []

# ============================================================================
# FEEDBACK SYSTEM
# ============================================================================

class FeedbackManager:
    """Manage agent performance feedback"""
    
    def __init__(self):
        self.feedback_records: List[Feedback] = []
        self.agent_scores: Dict[str, List[int]] = {}
    
    def submit_feedback(self, agent_id: str, task_id: str, 
                       score: int, comment: Optional[str] = None) -> Feedback:
        """Submit feedback for an agent's task"""
        feedback = Feedback(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            task_id=task_id,
            score=score,
            comment=comment
        )
        
        self.feedback_records.append(feedback)
        
        # Update agent scores
        if agent_id not in self.agent_scores:
            self.agent_scores[agent_id] = []
        self.agent_scores[agent_id].append(score)
        
        logger.info(f"Feedback submitted for agent {agent_id}: score={score}")
        return feedback
    
    def get_agent_average_score(self, agent_id: str) -> float:
        """Get average score for an agent"""
        if agent_id not in self.agent_scores or not self.agent_scores[agent_id]:
            return 0.0
        return sum(self.agent_scores[agent_id]) / len(self.agent_scores[agent_id])
    
    def get_feedback_statistics(self, agent_id: Optional[str] = None) -> Dict:
        """Get feedback statistics"""
        if agent_id:
            records = [f for f in self.feedback_records if f.agent_id == agent_id]
        else:
            records = self.feedback_records
        
        if not records:
            return {'total': 0, 'average': 0, 'distribution': {}}
        
        scores = [r.score for r in records]
        distribution = {}
        for score in set(scores):
            distribution[score] = scores.count(score)
        
        return {
            'total': len(records),
            'average': sum(scores) / len(scores),
            'distribution': distribution,
            'recent': [asdict(r) for r in records[-10:]]
        }
    
    def get_alignment_recommendations(self, agent_id: str) -> List[str]:
        """Get alignment adjustment recommendations based on feedback"""
        avg_score = self.get_agent_average_score(agent_id)
        recommendations = []
        
        if avg_score < 2.0:
            recommendations.append("Consider reducing strictness level")
            recommendations.append("Review task assignment criteria")
        elif avg_score < 3.5:
            recommendations.append("Provide additional training data")
            recommendations.append("Adjust response parameters")
        elif avg_score >= 4.5:
            recommendations.append("Agent performing optimally")
            recommendations.append("Consider increasing task complexity")
        
        return recommendations

# ============================================================================
# MAIN HERMES ORCHESTRATOR
# ============================================================================

class HermesOrchestrator:
    """Main HERMES orchestration system"""
    
    def __init__(self):
        self.agents: Dict[str, AgentConfig] = {}
        self.tasks: Dict[str, Task] = {}
        self.memory_manager = MemoryManager()
        self.sandbox = SandboxEnvironment()
        self.skills_repo = SkillsRepository()
        self.group_manager = AgentGroupManager()
        self.feedback_manager = FeedbackManager()
        self.running = False
        self.task_queue = queue.PriorityQueue()
        
        # Initialize default groups
        self._initialize_default_groups()
    
    def _initialize_default_groups(self):
        """Initialize default agent groups"""
        self.group_manager.create_group("High Priority Tasks", "task_type", "critical")
        self.group_manager.create_group("Strict Agents", "strictness", 5)
        self.group_manager.create_group("Standard Agents", "strictness", 3)
    
    def create_agent(self, name: str, task_type: str, strictness_level: int,
                    skills: List[str] = None, sandbox_enabled: bool = True) -> AgentConfig:
        """Create a new agent"""
        agent_id = str(uuid.uuid4())
        agent = AgentConfig(
            id=agent_id,
            name=name,
            task_type=task_type,
            strictness_level=strictness_level,
            deployment_date=datetime.now().isoformat(),
            skills=skills or [],
            sandbox_enabled=sandbox_enabled
        )
        
        self.agents[agent_id] = agent
        self.group_manager.auto_assign_agents([agent])
        
        # Add initial memory
        if agent.memory_enabled:
            self.memory_manager.add_memory(
                agent_id, 
                MemoryType.EPISODIC,
                f"Agent {name} created with task type {task_type}"
            )
        
        logger.info(f"Created agent: {name} ({agent_id})")
        return agent
    
    def update_agent(self, agent_id: str, **kwargs) -> bool:
        """Update agent configuration"""
        if agent_id not in self.agents:
            return False
        
        agent = self.agents[agent_id]
        for key, value in kwargs.items():
            if hasattr(agent, key):
                setattr(agent, key, value)
        
        agent.updated_at = datetime.now().isoformat()
        
        # Re-evaluate group assignments
        self.group_manager.auto_assign_agents([agent])
        
        logger.info(f"Updated agent: {agent_id}")
        return True
    
    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent"""
        if agent_id not in self.agents:
            return False
        
        # Clear agent memories
        self.memory_manager.clear_agent_memories(agent_id)
        
        # Remove from all groups
        for group in self.group_manager.groups.values():
            self.group_manager.remove_agent_from_group(group.id, agent_id)
        
        del self.agents[agent_id]
        logger.info(f"Deleted agent: {agent_id}")
        return True
    
    def delegate_task(self, task_description: str, agent_id: Optional[str] = None,
                     priority: TaskPriority = TaskPriority.MEDIUM) -> Task:
        """Delegate a task to an agent"""
        task_id = str(uuid.uuid4())
        
        # If no agent specified, select best available
        if not agent_id:
            agent_id = self._select_best_agent(task_description, priority)
        
        task = Task(
            id=task_id,
            description=task_description,
            agent_id=agent_id,
            priority=priority.value
        )
        
        self.tasks[task_id] = task
        self.task_queue.put((-priority.value, time.time(), task_id))
        
        if agent_id and agent_id in self.agents:
            self.agents[agent_id].status = AgentStatus.RUNNING.value
        
        logger.info(f"Delegated task {task_id} to agent {agent_id}")
        return task
    
    def _select_best_agent(self, task_description: str, 
                          priority: TaskPriority) -> Optional[str]:
        """Select best available agent for a task"""
        available_agents = [
            agent for agent in self.agents.values()
            if agent.status == AgentStatus.IDLE.value
        ]
        
        if not available_agents:
            return None
        
        # Simple selection: highest strictness first
        available_agents.sort(key=lambda x: x.strictness_level, reverse=True)
        return available_agents[0].id
    
    def get_agent_status(self, agent_id: str) -> Optional[Dict]:
        """Get detailed agent status"""
        if agent_id not in self.agents:
            return None
        
        agent = self.agents[agent_id]
        memories = self.memory_manager.get_memories(agent_id, limit=5)
        groups = self.group_manager.get_groups_for_agent(agent_id)
        avg_score = self.feedback_manager.get_agent_average_score(agent_id)
        
        return {
            'config': asdict(agent),
            'memories': memories,
            'groups': [asdict(g) for g in groups],
            'average_feedback_score': avg_score,
            'pending_tasks': self._count_pending_tasks(agent_id)
        }
    
    def _count_pending_tasks(self, agent_id: str) -> int:
        """Count pending tasks for an agent"""
        return sum(
            1 for task in self.tasks.values()
            if task.agent_id == agent_id and task.status == 'pending'
        )
    
    def run_task_execution_loop(self):
        """Run the main task execution loop"""
        self.running = True
        logger.info("Starting HERMES task execution loop")
        
        while self.running:
            try:
                if not self.task_queue.empty():
                    _, _, task_id = self.task_queue.get_nowait()
                    self._execute_task(task_id)
                else:
                    time.sleep(0.1)
            except queue.Empty:
                time.sleep(0.1)
            except KeyboardInterrupt:
                self.stop()
                break
    
    def _execute_task(self, task_id: str):
        """Execute a single task"""
        if task_id not in self.tasks:
            return
        
        task = self.tasks[task_id]
        agent_id = task.agent_id
        
        if not agent_id or agent_id not in self.agents:
            task.status = 'failed'
            task.result = 'No agent assigned'
            return
        
        agent = self.agents[agent_id]
        task.status = 'running'
        task.started_at = datetime.now().isoformat()
        
        try:
            # Check cache first
            cached_result = self.memory_manager.get_cached_response(task.description)
            if cached_result:
                task.result = cached_result
                task.status = 'completed'
                logger.info(f"Task {task_id} completed from cache")
            else:
                # Execute in sandbox if enabled
                if agent.sandbox_enabled:
                    result = self.sandbox.execute_code(
                        f"print('Executing: {task.description}')",
                        language='python'
                    )
                    task.result = result.get('output', result.get('error', ''))
                else:
                    task.result = f"Executed: {task.description}"
                
                # Cache the result
                self.memory_manager.store_cached_response(
                    task.description,
                    task.result,
                    tokens_used=100  # Estimate
                )
                
                task.status = 'completed'
                logger.info(f"Task {task_id} executed successfully")
            
            # Add to agent memory
            self.memory_manager.add_memory(
                agent_id,
                MemoryType.EPISODIC,
                f"Completed task: {task.description}",
                {'task_id': task_id, 'result': task.result}
            )
            
        except Exception as e:
            task.status = 'failed'
            task.result = str(e)
            logger.error(f"Task {task_id} failed: {e}")
        
        finally:
            task.completed_at = datetime.now().isoformat()
            agent.status = AgentStatus.IDLE.value
    
    def stop(self):
        """Stop the orchestrator"""
        self.running = False
        logger.info("HERMES orchestrator stopped")
    
    def get_dashboard_data(self) -> Dict:
        """Get comprehensive data for dashboard"""
        return {
            'agents': {
                aid: asdict(agent) for aid, agent in self.agents.items()
            },
            'tasks': {
                tid: asdict(task) for tid, task in self.tasks.items()
            },
            'groups': {
                gid: asdict(group) for gid, group in self.group_manager.groups.items()
            },
            'skills': self.skills_repo.discover_skills(),
            'feedback_stats': self.feedback_manager.get_feedback_statistics(),
            'system_status': {
                'running': self.running,
                'queue_size': self.task_queue.qsize(),
                'total_agents': len(self.agents),
                'active_agents': sum(
                    1 for a in self.agents.values() 
                    if a.status == AgentStatus.RUNNING.value
                )
            }
        }

# ============================================================================
# EXPERIENCE LAYER API (Flask-based Dashboard Backend)
# ============================================================================

def create_dashboard_app(orchestrator: HermesOrchestrator):
    """Create Flask dashboard application"""
    try:
        from flask import Flask, jsonify, request, render_template_string
        from flask_cors import CORS
    except ImportError:
        logger.warning("Flask not installed. Install with: pip install flask flask-cors")
        return None
    
    app = Flask(__name__)
    CORS(app)
    
    # HTML Template for Dashboard
    DASHBOARD_HTML = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>HERMES Experience Layer</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
            .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
            header { background: rgba(255,255,255,0.95); border-radius: 15px; padding: 20px; margin-bottom: 20px; box-shadow: 0 8px 32px rgba(0,0,0,0.1); }
            h1 { color: #667eea; font-size: 2.5em; margin-bottom: 10px; }
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 20px; }
            .stat-card { background: white; padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
            .stat-number { font-size: 2.5em; font-weight: bold; color: #667eea; }
            .stat-label { color: #666; margin-top: 5px; }
            .main-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            .panel { background: rgba(255,255,255,0.95); border-radius: 15px; padding: 20px; box-shadow: 0 8px 32px rgba(0,0,0,0.1); }
            .panel h2 { color: #667eea; margin-bottom: 15px; border-bottom: 2px solid #667eea; padding-bottom: 10px; }
            .agent-list { max-height: 400px; overflow-y: auto; }
            .agent-item { background: #f8f9fa; padding: 15px; margin-bottom: 10px; border-radius: 8px; border-left: 4px solid #667eea; }
            .agent-item.running { border-left-color: #28a745; animation: pulse 2s infinite; }
            .agent-item.idle { border-left-color: #ffc107; }
            .agent-item.stopped { border-left-color: #dc3545; }
            @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.7; } 100% { opacity: 1; } }
            .status-badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.85em; font-weight: bold; color: white; }
            .status-running { background: #28a745; }
            .status-idle { background: #ffc107; color: #333; }
            .status-stopped { background: #dc3545; }
            .btn { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin: 5px; }
            .btn:hover { background: #5568d3; }
            .btn-danger { background: #dc3545; }
            .form-group { margin-bottom: 15px; }
            .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
            .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
            .tabs { display: flex; border-bottom: 2px solid #ddd; margin-bottom: 20px; }
            .tab { padding: 10px 20px; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -2px; }
            .tab.active { border-bottom-color: #667eea; color: #667eea; font-weight: bold; }
            .feedback-stars { color: #ffc107; font-size: 1.5em; }
            .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; }
            .modal-content { background: white; max-width: 600px; margin: 50px auto; padding: 30px; border-radius: 15px; }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>🚀 HERMES Experience Layer</h1>
                <p>Hierarchical Executive Resource Management & Execution System</p>
                <div class="stats-grid" id="statsGrid"></div>
            </header>
            
            <div class="main-grid">
                <div class="panel">
                    <h2>🤖 Agent Management</h2>
                    <div class="tabs">
                        <div class="tab active" onclick="showTab('agents')">Agents</div>
                        <div class="tab" onclick="showTab('create')">Create/Edit</div>
                        <div class="tab" onclick="showTab('groups')">Groups</div>
                    </div>
                    
                    <div id="agentsTab">
                        <button class="btn" onclick="refreshData()">🔄 Refresh</button>
                        <div class="agent-list" id="agentList"></div>
                    </div>
                    
                    <div id="createTab" style="display:none;">
                        <form id="agentForm">
                            <input type="hidden" id="editAgentId">
                            <div class="form-group">
                                <label>Name</label>
                                <input type="text" id="agentName" required>
                            </div>
                            <div class="form-group">
                                <label>Task Type</label>
                                <select id="agentTaskType">
                                    <option value="data_analysis">Data Analysis</option>
                                    <option value="web_scraping">Web Scraping</option>
                                    <option value="text_processing">Text Processing</option>
                                    <option value="code_generation">Code Generation</option>
                                    <option value="api_integration">API Integration</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Strictness Level (1-5)</label>
                                <input type="number" id="agentStrictness" min="1" max="5" value="3">
                            </div>
                            <div class="form-group">
                                <label>Skills</label>
                                <select id="agentSkills" multiple>
                                    <option value="data_analysis">Data Analysis</option>
                                    <option value="web_scraping">Web Scraping</option>
                                    <option value="text_processing">Text Processing</option>
                                    <option value="image_recognition">Image Recognition</option>
                                    <option value="code_generation">Code Generation</option>
                                </select>
                            </div>
                            <button type="submit" class="btn">Save Agent</button>
                            <button type="button" class="btn btn-danger" onclick="clearForm()">Cancel</button>
                        </form>
                    </div>
                    
                    <div id="groupsTab" style="display:none;">
                        <div id="groupsList"></div>
                    </div>
                </div>
                
                <div class="panel">
                    <h2>📋 Task Delegation</h2>
                    <div class="form-group">
                        <label>Select Agent</label>
                        <select id="taskAgent">
                            <option value="">Auto-select</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Task Description</label>
                        <textarea id="taskDescription" rows="4" placeholder="Describe the task..."></textarea>
                    </div>
                    <div class="form-group">
                        <label>Priority</label>
                        <select id="taskPriority">
                            <option value="1">Low</option>
                            <option value="2" selected>Medium</option>
                            <option value="3">High</option>
                            <option value="4">Critical</option>
                        </select>
                    </div>
                    <button class="btn" onclick="delegateTask()">🚀 Delegate Task</button>
                    
                    <h3 style="margin-top: 30px;">Recent Tasks</h3>
                    <div id="taskList"></div>
                </div>
            </div>
            
            <!-- Feedback Modal -->
            <div id="feedbackModal" class="modal">
                <div class="modal-content">
                    <h2>Rate Agent Performance</h2>
                    <input type="hidden" id="feedbackAgentId">
                    <input type="hidden" id="feedbackTaskId">
                    <div class="form-group">
                        <label>Rating</label>
                        <div class="feedback-stars" id="starRating">
                            <span onclick="setRating(1)">★</span>
                            <span onclick="setRating(2)">★</span>
                            <span onclick="setRating(3)">★</span>
                            <span onclick="setRating(4)">★</span>
                            <span onclick="setRating(5)">★</span>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Comment (optional)</label>
                        <textarea id="feedbackComment" rows="3"></textarea>
                    </div>
                    <button class="btn" onclick="submitFeedback()">Submit</button>
                    <button class="btn btn-danger" onclick="closeModal()">Cancel</button>
                </div>
            </div>
        </div>
        
        <script>
            let currentRating = 0;
            
            async function refreshData() {
                const response = await fetch('/api/dashboard');
                const data = await response.json();
                
                // Update stats
                document.getElementById('statsGrid').innerHTML = `
                    <div class="stat-card">
                        <div class="stat-number">${data.system_status.total_agents}</div>
                        <div class="stat-label">Total Agents</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${data.system_status.active_agents}</div>
                        <div class="stat-label">Active Agents</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${Object.keys(data.tasks).length}</div>
                        <div class="stat-label">Total Tasks</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${data.system_status.queue_size}</div>
                        <div class="stat-label">Pending Tasks</div>
                    </div>
                `;
                
                // Update agent list
                const agentList = document.getElementById('agentList');
                agentList.innerHTML = '';
                const agentSelect = document.getElementById('taskAgent');
                agentSelect.innerHTML = '<option value="">Auto-select</option>';
                
                Object.values(data.agents).forEach(agent => {
                    agentList.innerHTML += `
                        <div class="agent-item ${agent.status}">
                            <strong>${agent.name}</strong> 
                            <span class="status-badge status-${agent.status}">${agent.status}</span>
                            <p>Type: ${agent.task_type} | Strictness: ${agent.strictness_level}</p>
                            <div style="margin-top: 10px;">
                                <button class="btn" onclick="editAgent('${agent.id}')">Edit</button>
                                <button class="btn" onclick="openFeedbackModal('${agent.id}', '')">Rate</button>
                                <button class="btn btn-danger" onclick="deleteAgent('${agent.id}')">Delete</button>
                            </div>
                        </div>
                    `;
                    
                    agentSelect.innerHTML += `<option value="${agent.id}">${agent.name}</option>`;
                });
                
                // Update task list
                const taskList = document.getElementById('taskList');
                taskList.innerHTML = '';
                Object.values(data.tasks).slice(-5).reverse().forEach(task => {
                    taskList.innerHTML += `
                        <div style="background: #f8f9fa; padding: 10px; margin-bottom: 5px; border-radius: 5px;">
                            <strong>${task.description.substring(0, 50)}...</strong>
                            <span class="status-badge" style="background: ${task.status === 'completed' ? '#28a745' : '#ffc107'}">${task.status}</span>
                            <button class="btn" style="font-size: 0.8em;" onclick="openFeedbackModal('${task.agent_id || ''}', '${task.id}')">Rate</button>
                        </div>
                    `;
                });
                
                // Update groups
                const groupsList = document.getElementById('groupsList');
                groupsList.innerHTML = '';
                Object.values(data.groups).forEach(group => {
                    groupsList.innerHTML += `
                        <div style="background: #f8f9fa; padding: 15px; margin-bottom: 10px; border-radius: 8px;">
                            <strong>${group.name}</strong>
                            <p>Criteria: ${group.criteria_type} = ${group.criteria_value}</p>
                            <p>Agents: ${group.agent_ids.length}</p>
                        </div>
                    `;
                });
            }
            
            function showTab(tabName) {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('[id$="Tab"]').forEach(t => t.style.display = 'none');
                
                event.target.classList.add('active');
                document.getElementById(tabName + 'Tab').style.display = 'block';
            }
            
            document.getElementById('agentForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const agentId = document.getElementById('editAgentId').value;
                const skills = Array.from(document.getElementById('agentSkills').selectedOptions).map(o => o.value);
                
                const data = {
                    name: document.getElementById('agentName').value,
                    task_type: document.getElementById('agentTaskType').value,
                    strictness_level: parseInt(document.getElementById('agentStrictness').value),
                    skills: skills
                };
                
                const url = agentId ? `/api/agents/${agentId}` : '/api/agents';
                const method = agentId ? 'PUT' : 'POST';
                
                await fetch(url, {
                    method: method,
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                
                clearForm();
                refreshData();
            });
            
            async function editAgent(agentId) {
                const response = await fetch(`/api/agents/${agentId}`);
                const agent = await response.json();
                
                document.getElementById('editAgentId').value = agent.id;
                document.getElementById('agentName').value = agent.name;
                document.getElementById('agentTaskType').value = agent.task_type;
                document.getElementById('agentStrictness').value = agent.strictness_level;
                
                Array.from(document.getElementById('agentSkills').options).forEach(opt => {
                    opt.selected = agent.skills.includes(opt.value);
                });
                
                showTab('create');
            }
            
            async function deleteAgent(agentId) {
                if (confirm('Delete this agent?')) {
                    await fetch(`/api/agents/${agentId}`, {method: 'DELETE'});
                    refreshData();
                }
            }
            
            function clearForm() {
                document.getElementById('editAgentId').value = '';
                document.getElementById('agentForm').reset();
                showTab('agents');
            }
            
            async function delegateTask() {
                const data = {
                    task_description: document.getElementById('taskDescription').value,
                    agent_id: document.getElementById('taskAgent').value || null,
                    priority: parseInt(document.getElementById('taskPriority').value)
                };
                
                await fetch('/api/tasks', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                
                document.getElementById('taskDescription').value = '';
                refreshData();
            }
            
            function openFeedbackModal(agentId, taskId) {
                document.getElementById('feedbackAgentId').value = agentId;
                document.getElementById('feedbackTaskId').value = taskId;
                document.getElementById('feedbackModal').style.display = 'block';
            }
            
            function closeModal() {
                document.getElementById('feedbackModal').style.display = 'none';
            }
            
            function setRating(rating) {
                currentRating = rating;
                document.getElementById('starRating').innerHTML = Array(5).fill(0).map((_, i) => 
                    `<span onclick="setRating(${i+1})" style="color: ${i < rating ? '#ffc107' : '#ddd'}">★</span>`
                ).join('');
            }
            
            async function submitFeedback() {
                const data = {
                    agent_id: document.getElementById('feedbackAgentId').value,
                    task_id: document.getElementById('feedbackTaskId').value,
                    score: currentRating,
                    comment: document.getElementById('feedbackComment').value
                };
                
                await fetch('/api/feedback', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                
                closeModal();
                currentRating = 0;
                document.getElementById('feedbackComment').value = '';
                refreshData();
            }
            
            // Initial load
            refreshData();
            setInterval(refreshData, 5000);
        </script>
    </body>
    </html>
    """
    
    @app.route('/')
    def dashboard():
        return render_template_string(DASHBOARD_HTML)
    
    @app.route('/api/dashboard')
    def get_dashboard():
        return jsonify(orchestrator.get_dashboard_data())
    
    @app.route('/api/agents', methods=['POST'])
    def create_agent():
        data = request.json
        agent = orchestrator.create_agent(
            name=data['name'],
            task_type=data['task_type'],
            strictness_level=data['strictness_level'],
            skills=data.get('skills', [])
        )
        return jsonify(asdict(agent))
    
    @app.route('/api/agents/<agent_id>', methods=['GET'])
    def get_agent(agent_id):
        status = orchestrator.get_agent_status(agent_id)
        if status:
            return jsonify(status['config'])
        return jsonify({'error': 'Agent not found'}), 404
    
    @app.route('/api/agents/<agent_id>', methods=['PUT'])
    def update_agent(agent_id):
        data = request.json
        success = orchestrator.update_agent(agent_id, **data)
        if success:
            return jsonify({'status': 'updated'})
        return jsonify({'error': 'Agent not found'}), 404
    
    @app.route('/api/agents/<agent_id>', methods=['DELETE'])
    def delete_agent(agent_id):
        success = orchestrator.delete_agent(agent_id)
        if success:
            return jsonify({'status': 'deleted'})
        return jsonify({'error': 'Agent not found'}), 404
    
    @app.route('/api/tasks', methods=['POST'])
    def create_task():
        data = request.json
        priority = TaskPriority(data.get('priority', 2))
        task = orchestrator.delegate_task(
            task_description=data['task_description'],
            agent_id=data.get('agent_id'),
            priority=priority
        )
        return jsonify(asdict(task))
    
    @app.route('/api/feedback', methods=['POST'])
    def submit_feedback():
        data = request.json
        feedback = orchestrator.feedback_manager.submit_feedback(
            agent_id=data['agent_id'],
            task_id=data['task_id'],
            score=data['score'],
            comment=data.get('comment')
        )
        return jsonify(asdict(feedback))
    
    return app

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point for HERMES system"""
    print("=" * 70)
    print("🚀 HERMES - Hierarchical Executive Resource Management System")
    print("   Quick Start Ready for OpenCLAW Integration")
    print("=" * 70)
    
    # Initialize orchestrator
    orchestrator = HermesOrchestrator()
    
    # Create sample agents
    print("\n📦 Initializing default agents...")
    orchestrator.create_agent("Data Analyst Pro", "data_analysis", 4, 
                             ["data_analysis", "text_processing"])
    orchestrator.create_agent("Web Scraper Elite", "web_scraping", 3,
                             ["web_scraping", "api_integration"])
    orchestrator.create_agent("Code Generator X", "code_generation", 5,
                             ["code_generation", "text_processing"])
    
    # Start dashboard
    print("\n🌐 Starting HERMES Experience Layer Dashboard...")
    app = create_dashboard_app(orchestrator)
    
    if app:
        print("\n✅ HERMES System Ready!")
        print("📊 Dashboard: http://localhost:8080")
        print("🔧 API Endpoints: http://localhost:8080/api/*")
        print("\nPress Ctrl+C to stop\n")
        
        # Run task executor in background thread
        executor_thread = threading.Thread(target=orchestrator.run_task_execution_loop)
        executor_thread.daemon = True
        executor_thread.start()
        
        app.run(host='0.0.0.0', port=8080, debug=False)
    else:
        print("\n⚠️  Flask not available. Running in CLI mode...")
        print("Install Flask: pip install flask flask-cors")
        
        # Demo CLI mode
        orchestrator.delegate_task("Analyze sales data from Q4", priority=TaskPriority.HIGH)
        orchestrator.delegate_task("Scrape competitor prices", priority=TaskPriority.MEDIUM)
        
        print("\nSample tasks delegated. Check logs for details.")
        print("Dashboard unavailable without Flask.")

if __name__ == "__main__":
    main()
