import os
import sys
import importlib
import inspect
from pathlib import Path
import site
import pkg_resources
import ast

class ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports = set()
        
    def visit_Import(self, node):
        for name in node.names:
            self.imports.add(name.name.split('.')[0])
            
    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.add(node.module.split('.')[0])

def get_package_dependencies(package_name):
    """Get all dependencies of a package"""
    try:
        dist = pkg_resources.working_set.by_key.get(package_name)
        if dist:
            deps = {req.key for req in dist.requires()}
            return deps
        return set()
    except:
        return set()

def analyze_module(module_path: str):
    """Analyze a module and its imports recursively"""
    imports = set()
    required_files = set()
    version_files = set()
    
    def process_file(file_path: str):
        if not os.path.exists(file_path):
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
                visitor = ImportVisitor()
                visitor.visit(tree)
                imports.update(visitor.imports)
        except:
            pass

    def process_dir(dir_path: str):
        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.endswith('.py'):
                    process_file(os.path.join(root, file))

    # Start with the main module
    process_file(module_path)
    
    # Process src directory
    src_dir = os.path.join(os.path.dirname(module_path), 'src')
    process_dir(src_dir)

    # Add known required packages
    required_packages = {
        'torch',
        'whisperx',
        'sounddevice',
        'keyboard',
        'customtkinter',
        'websockets',
        'numpy',
        'dotenv',
        'pytorch_lightning',
        'pyannote.audio',
        'faster_whisper',
    }
    imports.update(required_packages)

    # Get dependencies of all imports
    all_deps = set()
    for imp in imports:
        deps = get_package_dependencies(imp)
        all_deps.update(deps)
    imports.update(all_deps)

    # Get package info for found imports
    site_packages = site.getsitepackages()[0]
    for imp in imports:
        try:
            spec = importlib.util.find_spec(imp)
            if spec is not None and spec.has_location:
                pkg_path = os.path.dirname(spec.origin)
                if 'site-packages' in pkg_path:
                    # Look for version files
                    for file in ['version.info', 'VERSION', '__version__.py']:
                        version_file = os.path.join(pkg_path, file)
                        if os.path.exists(version_file):
                            version_files.add((imp, version_file))
                    
                    # Look for package data
                    for root, _, files in os.walk(pkg_path):
                        for file in files:
                            if file.endswith(('.json', '.dll', '.pyd', '.so', '.txt', '.bin')):
                                required_files.add((imp, os.path.join(root, file)))
                                
                    # Special handling for some packages
                    if imp in ['pytorch_lightning', 'lightning', 'lightning_fabric']:
                        version_file = os.path.join(pkg_path, 'version.info')
                        # Create version file if it doesn't exist
                        if not os.path.exists(version_file):
                            with open(version_file, 'w') as f:
                                f.write('0.0.0')
                            version_files.add((imp, version_file))
        except:
            pass

    return imports, required_files, version_files

def write_report(module_path: str, output_file: str = 'dependency_analysis.txt'):
    imports, files, version_files = analyze_module(module_path)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=== Dependency Analysis Report ===\n\n")
        
        f.write("Required Packages:\n")
        for imp in sorted(imports):
            f.write(f"  - {imp}\n")
        f.write("\n")

        f.write("Version Files Needed:\n")
        for pkg, file in sorted(version_files):
            f.write(f"  - {pkg}: {file}\n")
        f.write("\n")

        f.write("Package Data Files:\n")
        for pkg, file in sorted(files):
            f.write(f"  - {pkg}: {file}\n")
        f.write("\n")

        f.write("=== PyInstaller Configuration ===\n\n")
        
        # Generate PyInstaller arguments
        f.write("# Add these to your PyInstaller command:\n\n")
        
        # Hidden imports
        for imp in sorted(imports):
            if not imp.startswith('_'):  # Skip internal modules
                f.write(f"'--hidden-import={imp}',\n")
        f.write("\n")
        
        # Data files
        site_packages = Path(site.getsitepackages()[0])
        for pkg, file in sorted(version_files):
            try:
                rel_path = Path(file).relative_to(site_packages)
                f.write(f"'--add-data={file};{os.path.dirname(rel_path)}',\n")
            except ValueError:
                f.write(f"'--add-data={file};.',\n")
                
        for pkg, file in sorted(files):
            try:
                rel_path = Path(file).relative_to(site_packages)
                f.write(f"'--add-data={file};{os.path.dirname(rel_path)}',\n")
            except ValueError:
                f.write(f"'--add-data={file};.',\n")
        f.write("\n")
        
        # Collect all
        for imp in sorted(imports):
            if not imp.startswith('_'):  # Skip internal modules
                f.write(f"'--collect-all={imp}',\n")

if __name__ == '__main__':
    write_report('src/main.py')