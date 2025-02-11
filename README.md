# Efficient Repo to LLM Converter

A Python script that converts GitHub repositories into an LLM-optimized format, extracting key structural information while minimizing token usage. The tool creates comprehensive summaries that help LLMs understand codebases efficiently.

## Features

* Code parsing and analysis
* Extracts classes, functions, and dependencies
* Generates both JSON and Markdown summaries
* Ignores non-essential files (tests, cache, etc.)
* Focuses on repository structure and relationships
* Language-specific parsing (Python AST, JS/TS analysis)
* Repository statistics and metrics

## Usage

```bash
python3 repo_to_llm.py
# Enter GitHub repository URL when prompted
```

## Output Format

The script generates two files per repository (example for a repo named "my-project"):

### 1. my-project_summary.json
```json
{
  "files": [
    {
      "path": "src/main.py",
      "classes": [
        {
          "name": "MyClass",
          "methods": ["method1", "method2"],
          "docstring": "Class description"
        }
      ],
      "functions": [
        {
          "name": "my_function",
          "args": ["arg1", "arg2"],
          "docstring": "Function description"
        }
      ],
      "imports": ["module1", "module2"]
    }
  ],
  "dependencies": {
    "src/main.py": ["module1", "module2"]
  },
  "summary": {
    "total_files": 10,
    "total_size": 50000,
    "language_distribution": {
      ".py": 5,
      ".js": 3,
      ".ts": 2
    },
    "key_components": [
      "src/main.py",
      "src/core/engine.js"
    ]
  }
}
```

### 2. my-project_summary.md
A human-readable summary of the repository structure, including:
* Overview statistics
* Language distribution
* Key components
* Important files and their relationships

## Benefits

* Dramatically reduces token usage compared to raw code sharing
* Provides structured understanding of codebases
* Maintains important relationships and dependencies
* Language-aware parsing and analysis
* Automatic identification of key components
* Clean separation of metadata and content

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/repo-to-llm.git
cd repo-to-llm
```

2. Ensure you have the required dependencies:
```bash
# No additional dependencies required beyond Python standard library
```

3. Run the script:
```bash
python3 repo_to_llm.py
```

## Requirements

* Python 3.7+
* Git
* Access to target repository

## License

MIT License
