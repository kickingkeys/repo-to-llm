import os
import subprocess
from pathlib import Path
import shutil
import tempfile

class RepoToLLM:
    def __init__(self, repo_url):
        self.repo_url = repo_url
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir) / "repo"
        self.ignore_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.env'}
        self.code_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.h', '.css', '.html', '.sql'}

    def clone_repo(self):
        subprocess.run(['git', 'clone', self.repo_url, str(self.repo_path)], check=True)

    def should_process_file(self, path):
        return (path.suffix in self.code_extensions and
                not any(ignore in str(path) for ignore in self.ignore_dirs))

    def process_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            relative_path = file_path.relative_to(self.repo_path)
            return f"FILE:{relative_path}\n{content}\nENDFILE\n"
        except:
            return ""

    def generate_csv_metadata(self):
        metadata = ["path,size_bytes,extension"]
        for path in self.repo_path.rglob('*'):
            if path.is_file() and self.should_process_file(path):
                metadata.append(f"{path.relative_to(self.repo_path)},{path.stat().st_size},{path.suffix}")
        return "\n".join(metadata)

    def convert(self):
        try:
            self.clone_repo()
            with open('repo_llm.txt', 'w', encoding='utf-8') as f:
                f.write("METADATA\n")
                f.write(self.generate_csv_metadata())
                f.write("\nENDMETADATA\n\n")
                
                for path in self.repo_path.rglob('*'):
                    if path.is_file() and self.should_process_file(path):
                        content = self.process_file(path)
                        if content:
                            f.write(content)
        finally:
            shutil.rmtree(self.temp_dir)

def main():
    repo_url = input("Enter GitHub repository URL: ")
    converter = RepoToLLM(repo_url)
    converter.convert()
    print("Conversion complete. Output saved to repo_llm.txt")

if __name__ == "__main__":
    main()
