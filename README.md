# Repo to LLM Converter

A Python script that converts GitHub repositories into an LLM-optimized format for efficient token usage and easier comprehension by large language models.

## Features

- Converts repository structure to compact CSV format
- Strips unnecessary formatting and whitespace
- Creates clear file delimiters
- Focuses on code and text files
- Optimizes token usage for LLM interactions

## Usage

```bash
python repo_to_llm.py
# Enter GitHub repository URL when prompted
```

## Output Format

```
METADATA
path,size_bytes,extension
[file information]
ENDMETADATA

FILE:[filename]
[file content]
ENDFILE
```

## Benefits

- Reduces token consumption when sharing repositories with LLMs
- Improves LLM understanding of codebase structure
- Maintains essential information while removing redundant data

## Installation

1. Clone repository
2. Run script
3. Provide repository URL

## Requirements

- Python 3.x
- Git

## License

MIT License