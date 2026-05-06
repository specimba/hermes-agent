"""
Policy Loader - Loads and validates OpenShell policy YAML files
"""

from typing import Dict, Any, Optional
from pathlib import Path
import yaml
import sys


class PolicyLoader:
    """
    Loads OpenShell policy YAML files from the policies directory.
    Validates policy structure and provides policy lookup.
    """
    
    def __init__(self, policies_dir: Optional[Path] = None):
        """
        Initialize policy loader.
        
        Args:
            policies_dir: Path to policies directory. If None, uses default.
        """
        if policies_dir is None:
            # Default to policies directory relative to this file
            self.policies_dir = Path(__file__).parent.parent / "policies"
        else:
            self.policies_dir = policies_dir
        
        self._policies: Dict[str, Dict[str, Any]] = {}
        self._loaded = False
    
    def load_all(self) -> bool:
        """
        Load all policy files from the policies directory.
        
        Returns:
            True if at least one policy was loaded successfully
        """
        if self._loaded:
            return True
        
        if not self.policies_dir.exists():
            print(f"Policies directory not found: {self.policies_dir}")
            return False
        
        yaml_files = list(self.policies_dir.glob("*.yaml")) + list(self.policies_dir.glob("*.yml"))
        
        if not yaml_files:
            print(f"No YAML files found in {self.policies_dir}")
            return False
        
        loaded_count = 0
        for yaml_file in yaml_files:
            if self._load_file(yaml_file):
                loaded_count += 1
        
        self._loaded = True
        print(f"Loaded {loaded_count}/{len(yaml_files)} policy files")
        return loaded_count > 0
    
    def _load_file(self, file_path: Path) -> bool:
        """
        Load a single policy file.
        
        Args:
            file_path: Path to YAML policy file
            
        Returns:
            True if loaded successfully
        """
        try:
            with open(file_path, 'r') as f:
                policy = yaml.safe_load(f)
            
            # Validate basic structure
            if not isinstance(policy, dict):
                print(f"Invalid policy format in {file_path.name}: not a dict")
                return False
            
            if 'metadata' not in policy or 'name' not in policy.get('metadata', {}):
                print(f"Invalid policy in {file_path.name}: missing metadata.name")
                return False
            
            policy_name = policy['metadata']['name']
            self._policies[policy_name] = policy
            return True
            
        except yaml.YAMLEror as e:
            print(f"YAML parse error in {file_path.name}: {e}")
            return False
        except Exception as e:
            print(f"Error loading {file_path.name}: {e}")
            return False
    
    def get_policy(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a policy by name.
        
        Args:
            name: Policy name (from metadata.name)
            
        Returns:
            Policy dict or None if not found
        """
        if not self._loaded:
            self.load_all()
        
        return self._policies.get(name)
    
    def get_policy_for_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """
        Get policy by profile name (alias for get_policy).
        
        Args:
            profile_name: Policy profile name
            
        Returns:
            Policy dict or None if not found
        """
        return self.get_policy(profile_name)
    
    def list_policies(self) -> list[str]:
        """
        List all loaded policy names.
        
        Returns:
            List of policy names
        """
        if not self._loaded:
            self.load_all()
        
        return list(self._policies.keys())
    
    def validate_policy(self, policy: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate a policy structure.
        
        Args:
            policy: Policy dictionary
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        required_fields = ['apiVersion', 'kind', 'metadata', 'spec']
        
        for field in required_fields:
            if field not in policy:
                return False, f"Missing required field: {field}"
        
        # Check metadata
        metadata = policy.get('metadata', {})
        if 'name' not in metadata:
            return False, "Missing metadata.name"
        
        # Check spec
        spec = policy.get('spec', {})
        required_spec_fields = ['isolation', 'security', 'auditing']
        
        for field in required_spec_fields:
            if field not in spec:
                return False, f"Missing spec.{field}"
        
        # Check auditing format
        auditing = spec.get('auditing', {})
        if auditing.get('enabled') and auditing.get('format') == 'ocsf':
            # OCSF format is specified but we need to verify OCSF formatter is available
            try:
                from runtimes.ocsf_audit import OCSFAuditFormatter
                # OCSF formatter is available
            except ImportError:
                return False, "OCSF format specified but OCSF formatter not available"
        
        return True, "Policy is valid"


# Global policy loader instance
_policy_loader: Optional[PolicyLoader] = None


def get_policy_loader() -> PolicyLoader:
    """Get global policy loader instance"""
    global _policy_loader
    if _policy_loader is None:
        _policy_loader = PolicyLoader()
    return _policy_loader


def load_policy(policy_name: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to load a policy by name.
    
    Args:
        policy_name: Name of the policy
        
    Returns:
        Policy dict or None
    """
    loader = get_policy_loader()
    return loader.get_policy(policy_name)
