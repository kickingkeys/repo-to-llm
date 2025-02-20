import os
import sys
import subprocess
import argparse
from pathlib import Path
import shutil
import tempfile
import ast
import json
import re
from typing import Dict, List, Set, Tuple, Optional, Union, Any
from collections import defaultdict, Counter

class EnhancedRepoToLLM:
    def __init__(self, repo_source: str, is_local: bool = False, max_depth: int = 4,
                 include_tree: bool = True, include_types: bool = True,
                 include_dependencies: bool = True, include_patterns: bool = True):
        self.repo_source = repo_source
        self.is_local = is_local
        self.max_depth = max_depth
        self.include_tree = include_tree
        self.include_types = include_types
        self.include_dependencies = include_dependencies
        self.include_patterns = include_patterns
        
        # Extract repo name
        if is_local:
            self.repo_name = os.path.basename(os.path.abspath(repo_source))
            self.repo_path = Path(repo_source)
        else:
            self.repo_name = repo_source.rstrip('/').split('/')[-1].replace('.git', '')
            self.temp_dir = tempfile.mkdtemp()
            self.repo_path = Path(self.temp_dir) / "repo"
        
        # Configuration
        self.ignore_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.env', 'tests', 'test'}
        self.ignore_files = {'requirements.txt', 'package.json', 'package-lock.json'}
        self.code_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.h', '.jsx', '.tsx', '.rb', '.php', '.go'}
        
        # Analysis tracking
        self.dependencies: Dict[str, Set[str]] = {}
        self.reference_counts: Dict[str, int] = defaultdict(int)
        self.patterns: Dict[str, List[str]] = {}
        self.semantic_units: Dict[str, List[Dict]] = defaultdict(list)
        self.file_tree: Dict = {}
        
    def setup_repo(self):
        """Set up repository for analysis - either clone or verify local path."""
        if self.is_local:
            if not os.path.isdir(self.repo_path):
                raise ValueError(f"Local directory '{self.repo_path}' does not exist")
        else:
            self.clone_repo()
            
    def clone_repo(self):
        """Clone repository with minimal depth."""
        subprocess.run(['git', 'clone', '--depth', '1', self.repo_source, str(self.repo_path)], check=True)

    def should_process_file(self, path: Path) -> bool:
        """Enhanced file filtering with improved logic."""
        if path.name in self.ignore_files:
            return False
            
        if any(ignore in str(path) for ignore in self.ignore_dirs):
            return False
            
        if path.suffix not in self.code_extensions:
            return False
            
        # Skip test files unless they're the main focus
        if (any(part.lower().startswith('test') for part in path.parts) and
            not all(part.lower().startswith('test') for part in self.repo_path.parts)):
            return False
            
        return True

    def extract_python_info(self, content: str, path: str) -> dict:
        """Extract comprehensive information from Python files including return types."""
        try:
            tree = ast.parse(content)
            classes = []
            functions = []
            imports = []
            configs = {}
            
            # Track names for reference counting
            defined_names = set()
            referenced_names = set()
            
            for node in ast.walk(tree):
                # Extract classes
                if isinstance(node, ast.ClassDef):
                    methods = []
                    for f in node.body:
                        if isinstance(f, ast.FunctionDef):
                            return_type = self._extract_py_return_type(f)
                            methods.append({
                                'name': f.name,
                                'return_type': return_type
                            })
                    bases = [self._extract_py_name(b) for b in node.bases]
                    classes.append({
                        'name': node.name,
                        'methods': methods,
                        'bases': bases,
                        'docstring': ast.get_docstring(node) or ''
                    })
                    defined_names.add(node.name)
                
                # Extract functions
                elif isinstance(node, ast.FunctionDef) and node.name != '__init__':
                    return_type = self._extract_py_return_type(node)
                    functions.append({
                        'name': node.name,
                        'args': [self._extract_py_arg(arg) for arg in node.args.args],
                        'return_type': return_type,
                        'docstring': ast.get_docstring(node) or ''
                    })
                    defined_names.add(node.name)
                
                # Extract imports
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        for n in node.names:
                            imports.append(n.name)
                            if n.asname:
                                referenced_names.add(n.asname)
                            else:
                                referenced_names.add(n.name.split('.')[0])
                    else:
                        module = node.module or ''
                        for n in node.names:
                            import_name = f"{module}.{n.name}" if module else n.name
                            imports.append(import_name)
                            if n.asname:
                                referenced_names.add(n.asname)
                            else:
                                referenced_names.add(n.name)
                
                # Extract name references
                elif isinstance(node, ast.Name):
                    if isinstance(node.ctx, ast.Load):
                        referenced_names.add(node.id)
                
                # Extract config variables
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            name = target.id
                            if name.isupper() or name.startswith('CONFIG_'):
                                if isinstance(node.value, (ast.Str, ast.Num, ast.NameConstant)):
                                    configs[name] = ast.literal_eval(node.value)
                                elif isinstance(node.value, ast.Dict):
                                    try:
                                        config_dict = {}
                                        for i, key in enumerate(node.value.keys):
                                            if isinstance(key, ast.Str):
                                                key_str = key.s
                                                value = node.value.values[i]
                                                if isinstance(value, (ast.Str, ast.Num, ast.NameConstant)):
                                                    config_dict[key_str] = ast.literal_eval(value)
                                        configs[name] = config_dict
                                    except:
                                        pass
            
            # Update reference counts
            for name in referenced_names:
                if name in defined_names:
                    self.reference_counts[f"{path}:{name}"] += 1
            
            return {
                'classes': classes,
                'functions': functions,
                'imports': imports,
                'configs': configs,
                'defined_names': list(defined_names),
                'referenced_names': list(referenced_names)
            }
        except SyntaxError:
            return {'error': 'Could not parse Python file'}

    def _extract_py_return_type(self, func_node: ast.FunctionDef) -> str:
        """Extract return type from Python function."""
        # Try to get from type annotation
        if func_node.returns:
            return self._extract_py_name(func_node.returns)
        
        # Try to get from docstring
        docstring = ast.get_docstring(func_node) or ''
        if 'return' in docstring.lower() or 'returns' in docstring.lower():
            # Simple regex to find return type in docstring
            match = re.search(r'returns?:?\s*([A-Za-z0-9_\[\], ]+)', docstring, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Look for return statements
        return_values = []
        for node in ast.walk(func_node):
            if isinstance(node, ast.Return) and node.value:
                if isinstance(node.value, ast.Name):
                    return_values.append(node.value.id)
                elif isinstance(node.value, ast.Constant):
                    return_values.append(type(node.value.value).__name__)
                elif isinstance(node.value, ast.List):
                    return_values.append('list')
                elif isinstance(node.value, ast.Dict):
                    return_values.append('dict')
                elif isinstance(node.value, ast.Call):
                    if isinstance(node.value.func, ast.Name):
                        return_values.append(node.value.func.id)
        
        if return_values:
            if len(set(return_values)) == 1:
                return return_values[0]
            else:
                return f"Union[{', '.join(set(return_values))}]"
                
        return 'Any'

    def _extract_py_arg(self, arg: ast.arg) -> dict:
        """Extract argument information."""
        arg_info = {'name': arg.arg}
        if hasattr(arg, 'annotation') and arg.annotation:
            arg_info['type'] = self._extract_py_name(arg.annotation)
        return arg_info

    def _extract_py_name(self, node: ast.AST) -> str:
        """Extract name from various AST nodes."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._extract_py_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Subscript):
            return f"{self._extract_py_name(node.value)}[{self._extract_py_name(node.slice)}]"
        elif isinstance(node, ast.Index):
            return self._extract_py_name(node.value)
        elif isinstance(node, ast.Str):
            return node.s
        elif isinstance(node, ast.Num):
            return str(node.n)
        elif hasattr(node, 'value'):
            return str(node.value)
        return "unknown"

    def extract_js_ts_info(self, content: str, path: str) -> dict:
        """Extract key information from JavaScript/TypeScript files with improved type analysis."""
        # Simple regex-based extraction
        functions = []
        function_matches = re.finditer(r'(?:function|const|let|var)\s+(\w+)\s*(?:\([^)]*\)|\s*=\s*(?:\([^)]*\)|\([^)]*\)\s*=>))\s*(?::\s*([A-Za-z<>\[\]|, ]+))?\s*{', content)
        for match in function_matches:
            func_name = match.group(1)
            return_type = match.group(2) if match.group(2) else self._infer_js_return_type(content, func_name)
            functions.append({
                'name': func_name,
                'return_type': return_type
            })
        
        # Extract classes
        classes = []
        class_matches = re.finditer(r'class\s+(\w+)(?:\s+extends\s+(\w+))?\s*{', content)
        for match in class_matches:
            class_name = match.group(1)
            parent = match.group(2) if match.group(2) else None
            
            # Find methods in class
            class_start = match.end()
            brace_count = 1
            class_content = ""
            for i in range(class_start, len(content)):
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        class_content = content[class_start:i]
                        break
            
            methods = []
            method_matches = re.finditer(r'(?:async\s+)?(\w+)\s*\([^)]*\)(?:\s*:\s*([A-Za-z<>\[\]|, ]+))?\s*{', class_content)
            for m_match in method_matches:
                methods.append({
                    'name': m_match.group(1),
                    'return_type': m_match.group(2) if m_match.group(2) else 'any'
                })
                
            classes.append({
                'name': class_name,
                'methods': methods,
                'parent': parent
            })
        
        # Extract imports
        imports = []
        import_matches = re.finditer(r'import\s+(?:{[^}]+}|[^{]+)\s+from\s+[\'"](.+?)[\'"]', content)
        for match in import_matches:
            imports.append(match.group(1))
            
        # Extract configs
        configs = {}
        config_matches = re.finditer(r'(?:const|let|var)\s+(CONFIG_\w+|[A-Z_]+)\s*=\s*({[^;]+}|[^;]+);', content)
        for match in config_matches:
            try:
                name = match.group(1)
                # Simple extraction for basic values and JSON-like objects
                value_str = match.group(2)
                if value_str.startswith('{') and value_str.endswith('}'):
                    # Attempt to clean up and parse
                    json_like = re.sub(r'(\w+):', r'"\1":', value_str)
                    json_like = re.sub(r'\'', '"', json_like)
                    try:
                        configs[name] = json.loads(json_like)
                    except:
                        configs[name] = "object"
                else:
                    # Handle primitive values
                    value_str = value_str.strip()
                    if value_str in ('true', 'false'):
                        configs[name] = value_str == 'true'
                    elif value_str.isdigit():
                        configs[name] = int(value_str)
                    elif value_str.startswith("'") or value_str.startswith('"'):
                        configs[name] = value_str[1:-1]
                    else:
                        configs[name] = value_str
            except:
                pass
                
        return {
            'classes': classes,
            'functions': functions,
            'imports': imports,
            'configs': configs
        }

    def _infer_js_return_type(self, content: str, func_name: str) -> str:
        """Infer JavaScript/TypeScript function return type."""
        # Find the function
        func_match = re.search(rf'(?:function|const|let|var)\s+{func_name}\s*\([^)]*\)', content)
        if not func_match:
            return 'any'
            
        func_start = func_match.end()
        # Find the function body
        brace_count = 0
        func_body = ""
        in_func = False
        for i in range(func_start, len(content)):
            if content[i] == '{':
                brace_count += 1
                if not in_func:
                    in_func = True
                    continue
            elif content[i] == '}':
                brace_count -= 1
                if in_func and brace_count == 0:
                    func_body = content[func_start:i]
                    break
        
        if not func_body:
            return 'any'
            
        # Check return statements
        return_matches = re.finditer(r'return\s+([^;]+);', func_body)
        return_types = []
        
        for match in return_matches:
            value = match.group(1).strip()
            if value == 'null' or value == 'undefined':
                return_types.append('null')
            elif value == 'true' or value == 'false':
                return_types.append('boolean')
            elif value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                return_types.append('number')
            elif value.startswith('"') or value.startswith("'"):
                return_types.append('string')
            elif value.startswith('['):
                return_types.append('array')
            elif value.startswith('{'):
                return_types.append('object')
            elif value.startswith('new '):
                class_name = value[4:].split('(')[0].strip()
                return_types.append(class_name)
            else:
                return_types.append('any')
                
        if not return_types:
            return 'void'
        elif len(set(return_types)) == 1:
            return return_types[0]
        else:
            return f"Union<{', '.join(set(return_types))}>"

    def process_file(self, file_path: Path) -> dict:
        """Process a single file and extract its key information."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            relative_path = str(file_path.relative_to(self.repo_path))
            
            # Extract file information based on extension
            file_info = {
                'path': relative_path,
                'size': file_path.stat().st_size,
                'extension': file_path.suffix
            }
            
            if file_path.suffix == '.py':
                python_info = self.extract_python_info(content, relative_path)
                file_info.update(python_info)
                
                # Add to semantic units
                if 'classes' in python_info:
                    for cls in python_info['classes']:
                        self.semantic_units['classes'].append({
                            'name': cls['name'],
                            'file': relative_path,
                            'docstring': cls.get('docstring', '')[:100]  # First 100 chars of docstring
                        })
                if 'functions' in python_info:
                    for func in python_info['functions']:
                        self.semantic_units['functions'].append({
                            'name': func['name'],
                            'file': relative_path,
                            'return_type': func.get('return_type', 'Any'),
                            'docstring': func.get('docstring', '')[:100]
                        })
                        
            elif file_path.suffix in {'.js', '.ts', '.jsx', '.tsx'}:
                js_info = self.extract_js_ts_info(content, relative_path)
                file_info.update(js_info)
                
                # Add to semantic units
                if 'classes' in js_info:
                    for cls in js_info['classes']:
                        self.semantic_units['classes'].append({
                            'name': cls['name'],
                            'file': relative_path
                        })
                if 'functions' in js_info:
                    for func in js_info['functions']:
                        self.semantic_units['functions'].append({
                            'name': func['name'],
                            'file': relative_path,
                            'return_type': func.get('return_type', 'any')
                        })
            else:
                # Basic extraction for other languages
                simple_info = self._extract_generic_info(content)
                file_info.update(simple_info)
            
            # Track dependencies
            if 'imports' in file_info:
                self.dependencies[relative_path] = set(file_info.get('imports', []))
            
            # Extract code patterns if enabled
            if self.include_patterns:
                self._extract_patterns(content, relative_path, file_path.suffix)
                
            return file_info
            
        except Exception as e:
            return {
                'path': str(file_path.relative_to(self.repo_path)),
                'error': str(e)
            }

    def _extract_generic_info(self, content: str) -> dict:
        """Extract basic information from non-Python/JS files."""
        functions = re.findall(r'(?:function|def|func|void|int|string|bool)\s+(\w+)\s*\([^)]*\)', content)
        classes = re.findall(r'(?:class|struct|interface)\s+(\w+)', content)
        imports = []
        
        # Try to find imports in various formats
        import_patterns = [
            r'(?:import|include|require)\s+[\'"<](.+?)[\'">]',  # C++, Go, etc.
            r'(?:import|from)\s+(\S+)',  # Various languages
            r'(?:use|using)\s+(\S+);'    # PHP, C#, etc.
        ]
        
        for pattern in import_patterns:
            imports.extend(re.findall(pattern, content))
        
        return {
            'functions': [{'name': f} for f in functions],
            'classes': [{'name': c} for c in classes],
            'imports': imports
        }

    def _extract_patterns(self, content: str, file_path: str, extension: str) -> None:
        """Extract recurring code patterns from files."""
        if extension == '.py':
            # Find common Python patterns
            patterns = [
                (r'if\s+__name__\s*==\s*[\'"]__main__[\'"]:.*?(?=\n\S)', 'main_guard'),
                (r'try:\s*.*?except.*?:\s*.*?(?=\n\S)', 'try_except'),
                (r'with\s+.*?as\s+.*?:\s*.*?(?=\n\S)', 'with_context'),
                (r'@.*?\ndef\s+.*?(?=\n\S)', 'decorated_function'),
                (r'for\s+.*?\s+in\s+.*?:\s*.*?(?=\n\S)', 'for_loop')
            ]
        elif extension in {'.js', '.ts'}:
            # Find common JS patterns
            patterns = [
                (r'const\s+.*?\s*=\s*\(\)\s*=>\s*{.*?};', 'arrow_function'),
                (r'useEffect\(\(\)\s*=>\s*{.*?}\s*,\s*\[.*?\]\);', 'react_use_effect'),
                (r'useState\(.*?\);', 'react_use_state'),
                (r'async\s+function.*?{.*?}', 'async_function'),
                (r'try\s*{.*?}\s*catch.*?{.*?}', 'try_catch')
            ]
        else:
            return
            
        for pattern, name in patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            if matches:
                if name not in self.patterns:
                    self.patterns[name] = []
                self.patterns[name].append(file_path)

    def build_file_tree(self) -> dict:
        """Build hierarchical file tree structure."""
        tree = {}
        
        for path in self.repo_path.rglob('*'):
            if not path.is_file() or not self.should_process_file(path):
                continue
                
            relative_path = str(path.relative_to(self.repo_path))
            parts = relative_path.split('/')
            
            # Limit depth
            if len(parts) > self.max_depth:
                parts = parts[:self.max_depth] + ['...']
                
            current = tree
            for i, part in enumerate(parts):
                if i == len(parts) - 1:  # File
                    if '_files' not in current:
                        current['_files'] = []
                    current['_files'].append(part)
                else:  # Directory
                    if part not in current:
                        current[part] = {}
                    current = current[part]
        
        # Compress tree by combining small directories
        self._optimize_tree(tree)
        return tree
        
    def _optimize_tree(self, tree: dict) -> None:
        """Optimize tree by condensing small directories."""
        # Bottom-up reduction
        for key, value in list(tree.items()):
            if isinstance(value, dict) and key != '_files':
                self._optimize_tree(value)
                # If directory has only one subdirectory, combine them
                if len(value) == 1 and '_files' not in value:
                    subdir = list(value.keys())[0]
                    new_key = f"{key}/{subdir}"
                    tree[new_key] = value[subdir]
                    del tree[key]

    def analyze_dependencies(self) -> dict:
        """Build dependency graph and find key relationships."""
        internal_modules = set()
        for path in self.dependencies.keys():
            module_name = path.split('.')[0].replace('/', '.')
            internal_modules.add(module_name)
        
        # Categorize dependencies
        dependency_graph = {}
        for source, targets in self.dependencies.items():
            internal_deps = []
            external_deps = []
            
            for target in targets:
                is_internal = False
                for module in internal_modules:
                    if target.startswith(module) or target.replace('/', '.').startswith(module):
                        is_internal = True
                        internal_deps.append(target)
                        break
                        
                if not is_internal:
                    external_deps.append(target)
                    
            dependency_graph[source] = {
                'internal': internal_deps,
                'external': external_deps
            }
            
        return dependency_graph

    def identify_key_components(self) -> List[str]:
        """Identify key components based on reference counts and dependencies."""
        component_scores = {}
        
        # Calculate scores based on references and dependency counts
        for component, refs in self.reference_counts.items():
            file_path = component.split(':')[0]
            component_scores[file_path] = component_scores.get(file_path, 0) + refs
            
        # Add scores for being imported
        for source, deps in self.dependencies.items():
            for dep in deps:
                # Try to map dependency to file path
                for file_path in self.dependencies.keys():
                    module_name = file_path.split('.')[0].replace('/', '.')
                    if dep.startswith(module_name):
                        component_scores[file_path] = component_scores.get(file_path, 0) + 2
                        break
        
        # Sort by score
        key_components = sorted(component_scores.items(), key=lambda x: x[1], reverse=True)
        return [k for k, v in key_components[:min(10, len(key_components))]]

    def analyze_structure(self) -> dict:
        """Analyze repository structure with enhanced metrics."""
        structure = {
            'files': [],
            'summary': {
                'total_files': 0,
                'total_size': 0,
                'language_distribution': {},
                'key_components': []
            }
        }
        
        # Build file tree if enabled
        if self.include_tree:
            self.file_tree = self.build_file_tree()
            structure['file_tree'] = self.file_tree
        
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
        
        # Add dependency information if enabled
        if self.include_dependencies:
            structure['dependencies'] = self.analyze_dependencies()
            
        # Add code patterns if enabled
        if self.include_patterns:
            structure['patterns'] = self.patterns
            
        # Add semantic units
        structure['semantic_units'] = self.semantic_units
        
        # Identify key components
        structure['summary']['key_components'] = self.identify_key_components()
        
        return structure

    def generate_tree_markdown(self, tree: dict, indent: int = 0) -> str:
        """Generate Markdown representation of file tree."""
        result = []
        
        # Process directories
        for key, value in sorted(tree.items()):
            if key == '_files':
                continue
                
            result.append(f"{' ' * indent}* 📁 {key}")
            if isinstance(value, dict):
                result.append(self.generate_tree_markdown(value, indent + 2))
                
        # Process files in current directory
        if '_files' in tree:
            files = sorted(tree['_files'])
            # Group by extension for cleaner display
            by_ext = defaultdict(list)
            for file in files:
                ext = os.path.splitext(file)[1] or 'no_ext'
                by_ext[ext].append(file)
                
            if len(files) > 10:
                # Too many files, summarize
                for ext, files_list in by_ext.items():
                    emoji = self._get_file_emoji(ext)
                    result.append(f"{' ' * indent}* {emoji} {len(files_list)} {ext} files")
            else:
                # Show all files
                for file in files:
                    ext = os.path.splitext(file)[1]
                    emoji = self._get_file_emoji(ext)
                    result.append(f"{' ' * indent}* {emoji} {file}")
                    
        return '\n'.join(result)
        
    def _get_file_emoji(self, extension: str) -> str:
        """Get emoji for file based on extension."""
        emoji_map = {
            '.py': '🐍',
            '.js': '📜',
            '.ts': '📘',
            '.jsx': '⚛️',
            '.tsx': '⚛️',
            '.html': '🌐',
            '.css': '🎨',
            '.json': '📋',
            '.md': '📝',
            '.java': '☕',
            '.cpp': '⚙️',
            '.h': '🔧',
            '.go': '🏃',
            '.rb': '💎',
            '.php': '🐘'
        }
        return emoji_map.get(extension, '📄')

    def convert(self) -> None:
        """Main conversion process with enhanced output."""
        try:
            self.setup_repo()
            structure = self.analyze_structure()
            
            # Generate output filenames
            json_filename = f"{self.repo_name}_summary.json"
            md_filename = f"{self.repo_name}_summary.md"
            
            # Save the structured JSON output
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(structure, f, indent=2)
                
            # Create a markdown summary for human readability
            with open(md_filename, 'w', encoding='utf-8') as f:
                f.write(f"# {self.repo_name} Repository Summary\n\n")
                
                # Overview section
                f.write(f"## Overview\n")
                f.write(f"- **Total Files:** {structure['summary']['total_files']}\n")
                f.write(f"- **Total Size:** {structure['summary']['total_size'] / 1024:.2f} KB\n\n")
                
                # Language distribution
                f.write("## Language Distribution\n")
                for lang, count in structure['summary']['language_distribution'].items():
                    f.write(f"- {lang or 'no extension'}: {count} files\n")
                f.write("\n")
                
                # File tree if available
                if self.include_tree and 'file_tree' in structure:
                    f.write("## File Tree\n")
                    f.write(self.generate_tree_markdown(structure['file_tree']))
                    f.write("\n\n")
                
                # Key components
                f.write("## Key Components\n")
                f.write("These files appear to be central to the codebase:\n")
                for component in structure['summary']['key_components']:
                    f.write(f"- `{component}`\n")
                f.write("\n")
                
                # Semantic units - classes and functions
                f.write("## Core Classes\n")
                if structure['semantic_units'].get('classes'):
                    classes = sorted(structure['semantic_units']['classes'],
                                   key=lambda x: x.get('name', ''))[:10]  # Top 10 classes
                    for cls in classes:
                        doc = cls.get('docstring', '').replace('\n', ' ')
                        if len(doc) > 60:
                            doc = doc[:57] + '...'
                        f.write(f"- `{cls['name']}` - {doc}\n")
                else:
                    f.write("No major classes identified\n")
                f.write("\n")
                
                f.write("## Core Functions\n")
                if structure['semantic_units'].get('functions'):
                    # Sort by return type for better organization
                    funcs = sorted(structure['semantic_units']['functions'],
                                 key=lambda x: (x.get('return_type', 'Any'), x.get('name', '')))[:15]  # Top 15 functions
                    for func in funcs:
                        ret_type = func.get('return_type', 'Any')
                        f.write(f"- `{func['name']}` → `{ret_type}`\n")
                else:
                    f.write("No major functions identified\n")
                f.write("\n")
                
                # Code patterns if available
                if self.include_patterns and structure.get('patterns'):
                    f.write("## Common Code Patterns\n")
                    for pattern, files in structure['patterns'].items():
                        f.write(f"- **{pattern}** - Used in {len(files)} files\n")
                    f.write("\n")
                
                # Dependencies if available
                if self.include_dependencies and structure.get('dependencies'):
                    f.write("## External Dependencies\n")
                    # Count and sort external dependencies
                    ext_deps = Counter()
                    for file_deps in structure['dependencies'].values():
                        ext_deps.update(file_deps.get('external', []))
                    
                    for dep, count in ext_deps.most_common(10):  # Top 10 external dependencies
                        f.write(f"- `{dep}` - Used in {count} files\n")
                    f.write("\n")
                    
            print(f"Conversion complete. Check {json_filename} and {md_filename} for results.")
                
        finally:
            # Clean up temp directory if not local
            if not self.is_local and hasattr(self, 'temp_dir'):
                shutil.rmtree(self.temp_dir)

def main():
    parser = argparse.ArgumentParser(description='Convert repository to LLM-optimized summary')
    parser.add_argument('source', nargs='?', help='GitHub repository URL or local path (optional - will prompt if not provided)')
    parser.add_argument('--local', action='store_true', help='Source is a local directory')
    parser.add_argument('--max-depth', type=int, default=4, help='Maximum depth for file tree')
    parser.add_argument('--no-tree', action='store_true', help='Skip file tree generation')
    parser.add_argument('--no-types', action='store_true', help='Skip return type extraction')
    parser.add_argument('--no-deps', action='store_true', help='Skip dependency analysis')
    parser.add_argument('--no-patterns', action='store_true', help='Skip code pattern detection')
    
    args = parser.parse_args()
    
    # If source is not provided, prompt for it
    source = args.source
    if not source:
        source = input("Enter GitHub repository URL or local path: ")
        if not source:
            print("Error: Repository source is required")
            sys.exit(1)
    
    # Ask if it's a local directory if not specified
    is_local = args.local
    if not args.local and os.path.exists(source) and os.path.isdir(source):
        confirm = input(f"'{source}' exists locally. Analyze as local directory? (y/n): ")
        is_local = confirm.lower() in ('y', 'yes')
    
    converter = EnhancedRepoToLLM(
        repo_source=source,
        is_local=is_local,
        max_depth=args.max_depth,
        include_tree=not args.no_tree,
        include_types=not args.no_types,
        include_dependencies=not args.no_deps,
        include_patterns=not args.no_patterns
    )
    
    converter.convert()

if __name__ == "__main__":
    main()
