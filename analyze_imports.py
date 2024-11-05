import os
import sys
import pkg_resources
import importlib.util
from datetime import datetime

def get_package_info():
    installed_packages = []
    for dist in pkg_resources.working_set:
        try:
            package = {
                'name': dist.key,
                'version': dist.version,
                'location': dist.location,
                'requires': [str(r) for r in dist.requires()]
            }
            installed_packages.append(package)
        except Exception as e:
            print(f"Error processing {dist}: {e}")
    return installed_packages

def analyze_imports():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(os.getcwd(), f'dependency_analysis_{timestamp}.txt')
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=== Whisper Client Dependency Analysis ===\n\n")
            
            # Environment Info
            f.write("Python Environment:\n")
            f.write(f"Python Version: {sys.version}\n")
            f.write(f"Python Path: {sys.executable}\n")
            f.write(f"Working Directory: {os.getcwd()}\n\n")
            
            # Virtual Environment Detection
            f.write("Virtual Environment:\n")
            if hasattr(sys, 'real_prefix') or sys.base_prefix != sys.prefix:
                f.write(f"Active venv: {sys.prefix}\n")
            else:
                f.write("No active virtual environment detected\n")
            f.write("\n")
            
            # Installed Packages
            f.write("Installed Packages:\n")
            f.write("-" * 80 + "\n")
            packages = get_package_info()
            for pkg in sorted(packages, key=lambda x: x['name'].lower()):
                f.write(f"\nPackage: {pkg['name']}\n")
                f.write(f"Version: {pkg['version']}\n")
                f.write(f"Location: {pkg['location']}\n")
                if pkg['requires']:
                    f.write("Dependencies:\n")
                    for dep in pkg['requires']:
                        f.write(f"  - {dep}\n")
                f.write("-" * 40 + "\n")
            
            # Essential packages for our application
            essential_packages = [
                'torch',
                'whisperx',
                'sounddevice',
                'keyboard',
                'customtkinter',
                'websockets'
            ]
            
            f.write("\n\nEssential Package Details:\n")
            f.write("-" * 80 + "\n")
            for package in essential_packages:
                try:
                    spec = importlib.util.find_spec(package)
                    if spec is not None:
                        f.write(f"\nPackage: {package}\n")
                        f.write(f"Location: {spec.origin}\n")
                        if spec.submodule_search_locations:
                            f.write(f"Package path: {spec.submodule_search_locations}\n")
                    else:
                        f.write(f"\nPackage {package} not found\n")
                except Exception as e:
                    f.write(f"\nError analyzing {package}: {e}\n")
                f.write("-" * 40 + "\n")
            
        print(f"Analysis written to: {output_file}")
        
    except Exception as e:
        print(f"Error writing analysis: {e}")

if __name__ == '__main__':
    analyze_imports()