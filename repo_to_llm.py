import os
import subprocess
from pathlib import Path
import shutil
import tempfile
import ast
import json
import re
from typing import Dict, List, Set, Tuple

class EfficientRepoToLLM:
    def __init__(self, repo_url: str):
        self.repo_url = repo_url
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir) / "repo"
        # Extract repo name from URL (e.g., "username/repo" from "https://github.com/username/repo")
        self.repo_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')
        
        # Configuration
        self.ignore_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.env', 'tests', 'test'}
        self.ignore_files = {'requirements.txt', 'package.json', 'package-lock.json'}
        self.code_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.h', '.jsx', '.tsx'}
        
        # Track dependencies between files
        self.dependencies: Dict[str, Set[str]] = {}
        
    def clone_repo(self):
        """Clone repository and get main branch name."""
        subprocess.run(['git', 'clone', '--depth', '1', self.repo_url, str(self.repo_path)], check=True)

    def should_process_file(self, path: Path) -> bool:
        """Enhanced file filtering."""
        if path.name in self.ignore_files:
            return False
            
        if any(ignore in str(path) for ignore in self.ignore_dirs):
            return False
            
        if path.suffix not in self.code_extensions:
            return False
            
        # Check if file is in a test directory
        if any(part.lower().startswith('test') for part in path.parts):
            return False
            
        return True

    def extract_python_info(self, content: str) -> dict:
        """Extract key information from Python files."""
        try:
            tree = ast.parse(content)
            classes = []
            functions = []
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = [f.name for f in node.body if isinstance(f, ast.FunctionDef)]
                    classes.append({
                        'name': node.name,
                        'methods': methods,
                        'docstring': ast.get_docstring(node) or ''
                    })
                elif isinstance(node, ast.FunctionDef) and node.name != '__init__':
                    functions.append({
                        'name': node.name,
                        'args': [arg.arg for arg in node.args.args],
                        'docstring': ast.get_docstring(node) or ''
                    })
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        imports.extend(n.name for n in node.names)
                    else:
                        module = node.module or ''
                        imports.extend(f"{module}.{n.name}" for n in node.names)
                        
            return {
                'classes': classes,
                'functions': functions,
                'imports': imports
            }
        except SyntaxError:
            return {'error': 'Could not parse Python file'}

    def extract_js_ts_info(self, content: str) -> dict:
        """Extract key information from JavaScript/TypeScript files."""
        # Simple regex-based extraction for demonstration
        # In production, you'd want to use a proper parser like esprima
        functions = re.findall(r'function\s+(\w+)\s*\([^)]*\)', content)
        classes = re.findall(r'class\s+(\w+)', content)
        imports = re.findall(r'import.*?from\s+[\'"](.+?)[\'"]', content)
        
        return {
            'classes': [{'name': c} for c in classes],
            'functions': [{'name': f} for f in functions],
            'imports': imports
        }

    def process_file(self, file_path: Path) -> dict:
        """Process a single file and extract its key information."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            relative_path = str(file_path.relative_to(self.repo_path))
            
            # Extract file information based on extension
            if file_path.suffix == '.py':
                file_info = self.extract_python_info(content)
            elif file_path.suffix in {'.js', '.ts', '.jsx', '.tsx'}:
                file_info = self.extract_js_ts_info(content)
            else:
                # For other files, just count functions and classes
                file_info = {
                    'functions': re.findall(r'function\s+(\w+)', content),
                    'classes': re.findall(r'class\s+(\w+)', content)
                }
            
            # Add basic file metadata
            file_info.update({
                'path': relative_path,
                'size': file_path.stat().st_size,
                'extension': file_path.suffix
            })
            
            # Track dependencies
            self.dependencies[relative_path] = set(file_info.get('imports', []))
            
            return file_info
            
        except Exception as e:
            return {
                'path': str(file_path.relative_to(self.repo_path)),
                'error': str(e)
            }

    def analyze_structure(self) -> dict:
        """Analyze repository structure and create a summary."""
        structure = {
            'files': [],
            'dependencies': {},
            'summary': {
                'total_files': 0,
                'total_size': 0,
                'language_distribution': {},
                'key_components': []
            }
        }
        
        # Process all files
        for path in self.repo_path.rglob('*'):
            if path.is_file() and self.should_process_file(path):
                file_info = self.process_file(path)
                structure['files'].append(file_info)
                
                # Update summary statistics
                structure['summary']['total_files'] += 1
                structure['summary']['total_size'] += file_info.get('size', 0)
                ext = file_info.get('extension', '')
                structure['summary']['language_distribution'][ext] = \
                    structure['summary']['language_distribution'].get(ext, 0) + 1
                
                # Track key components (files with many classes/functions)
                if len(file_info.get('classes', [])) + len(file_info.get('functions', [])) > 3:
                    structure['summary']['key_components'].append(file_info['path'])
        
        # Add dependency information
        structure['dependencies'] = {
            path: list(deps) for path, deps in self.dependencies.items()
        }
        
        return structure

    def convert(self) -> None:
        """Main conversion process."""
        try:
            self.clone_repo()
            structure = self.analyze_structure()
            
            # Save the structured output with repo name
            json_filename = f"{self.repo_name}_summary.json"
            md_filename = f"{self.repo_name}_summary.md"
            
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(structure, f, indent=2)
                
            # Create a markdown summary for easy reading
            with open(md_filename, 'w', encoding='utf-8') as f:
                f.write(f"# Repository Summary\n\n")
                f.write(f"## Overview\n")
                f.write(f"- Total Files: {structure['summary']['total_files']}\n")
                f.write(f"- Total Size: {structure['summary']['total_size'] / 1024:.2f} KB\n\n")
                
                f.write("## Language Distribution\n")
                for lang, count in structure['summary']['language_distribution'].items():
                    f.write(f"- {lang}: {count} files\n")
                
                f.write("\n## Key Components\n")
                for component in structure['summary']['key_components']:
                    f.write(f"- {component}\n")
                    
        finally:
            shutil.rmtree(self.temp_dir)

def main():
    repo_url = input("Enter GitHub repository URL: ")
    converter = EfficientRepoToLLM(repo_url)
    converter.convert()
    print(f"Conversion complete. Check {converter.repo_name}_summary.json and {converter.repo_name}_summary.md for results.")

if __name__ == "__main__":
    main()
