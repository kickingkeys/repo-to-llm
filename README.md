# Efficient Repo to LLM Converter

<div align="center">

![Version](https://img.shields.io/badge/version-2.0-blue)
![Python](https://img.shields.io/badge/python-3.7%2B-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

</div>

A Python tool that converts GitHub repositories into LLM-optimized summaries, extracting key structural information while minimizing token usage. Perfect for sharing codebases with AI assistants.

## ✨ Features

<table>
  <tr>
    <td>
      <h3>🧠 Smart Analysis</h3>
      <ul>
        <li>Function & class extraction</li>
        <li>Return type inference</li>
        <li>Python AST parsing</li>
        <li>JS/TS semantic analysis</li>
      </ul>
    </td>
    <td>
      <h3>🌳 Structure Mapping</h3>
      <ul>
        <li>Hierarchical file trees</li>
        <li>Dependency graphing</li>
        <li>Reference counting</li>
        <li>Component importance scoring</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td>
      <h3>💼 Token Optimization</h3>
      <ul>
        <li>Structural focus over raw code</li>
        <li>Pattern recognition</li>
        <li>Semantic grouping</li>
        <li>Redundancy elimination</li>
      </ul>
    </td>
    <td>
      <h3>🔧 Flexible Usage</h3>
      <ul>
        <li>GitHub repos or local directories</li>
        <li>Interactive guided mode</li>
        <li>Configurable analysis depth</li>
        <li>JSON & Markdown outputs</li>
      </ul>
    </td>
  </tr>
</table>

## 🚀 Usage

```bash
# Interactive mode (recommended)
python3 repo_to_llm.py

# Direct URL mode
python3 repo_to_llm.py https://github.com/username/repo

# Local directory mode
python3 repo_to_llm.py ./my-project --local
```

## 📊 Output Example

For a repository named "my-project", the tool generates:

### 1. `my-project_summary.json` (for LLMs)

<details>
<summary>Show JSON structure example</summary>

```json
{
  "files": [
    {
      "path": "src/main.py",
      "classes": [
        {
          "name": "DataProcessor",
          "methods": [
            {
              "name": "process",
              "return_type": "DataFrame"
            }
          ],
          "bases": ["BaseProcessor"],
          "docstring": "Handles data processing operations"
        }
      ],
      "functions": [
        {
          "name": "fetch_data",
          "args": [
            {"name": "source_url", "type": "str"},
            {"name": "timeout", "type": "int"}
          ],
          "return_type": "Dict[str, Any]"
        }
      ]
    }
  ],
  "file_tree": {
    "src": {
      "core": {},
      "utils": {"_files": ["helpers.py"]}
    }
  },
  "dependencies": {
    "src/main.py": {
      "internal": ["src/utils/helpers.py"],
      "external": ["pandas", "requests"]
    }
  },
  "semantic_units": {
    "classes": [...],
    "functions": [...]
  },
  "summary": {
    "total_files": 10,
    "language_distribution": {
      ".py": 6,
      ".js": 4
    },
    "key_components": [
      "src/main.py",
      "src/core/api.js"
    ]
  }
}
```
</details>

### 2. `my-project_summary.md` (for humans)

<details>
<summary>Show Markdown example</summary>

```markdown
# my-project Repository Summary

## Overview
- **Total Files:** 10
- **Total Size:** 48.83 KB

## Language Distribution
- .py: 6 files
- .js: 4 files

## File Tree
* 📁 src
  * 📁 core
    * 📄 api.js
    * 📄 models.py
  * 📁 utils
    * 📄 helpers.py
    * 📄 constants.py
  * 📄 main.py
  * 📄 app.js

## Key Components
- `src/main.py`
- `src/core/api.js`
- `src/utils/helpers.py`

## Core Classes
- `DataProcessor` - Handles data processing operations
- `ApiClient` - Manages external API communication

## Core Functions
- `fetch_data` → `Dict[str, Any]`
- `process_results` → `DataFrame`
- `authenticate` → `bool`

## External Dependencies
- `pandas` - Used in 3 files
- `requests` - Used in 2 files
```
</details>

## 💡 Benefits

- **90% Token Reduction**: Share repos with LLMs using a fraction of the tokens
- **Structural Understanding**: LLMs grasp architecture without reading all code
- **Relationship Mapping**: Dependencies and references clearly identified
- **Focus on Essentials**: Key components highlighted automatically
- **Type-Aware**: Function signatures and return types preserved

## 📋 Command Line Options

```
Usage: python3 repo_to_llm.py [source] [options]

Options:
  --local            Source is a local directory
  --max-depth N      Maximum depth for file tree (default: 4)
  --no-tree          Skip file tree generation
  --no-types         Skip return type extraction
  --no-deps          Skip dependency analysis
  --no-patterns      Skip code pattern detection
```

## 🔧 Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/repo-to-llm.git
cd repo-to-llm

# Run the tool (no additional dependencies required)
python3 repo_to_llm.py
```

## 📝 Requirements

- Python 3.7+
- Git
- Access to target repository (GitHub or local)

## 📜 License

[MIT License](LICENSE)

---


