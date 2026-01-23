import os
import sys

print("Current working directory:", os.getcwd())
print("Python path:", sys.path)

# List all files in current directory and subdirectories
print("\nAll files in current directory and subdirectories:")
for root, dirs, files in os.walk('.'):
    level = root.replace('.', '').count(os.sep)
    indent = ' ' * 2 * level
    print(f"{indent}{os.path.basename(root)}/")
    subindent = ' ' * 2 * (level + 1)
    for file in files:
        print(f"{subindent}{file}")

# Try to find any file with similar name
print("\nLooking for files containing '需求' or '20260123':")
for root, dirs, files in os.walk('.'):
    for file in files:
        if '需求' in file or '20260123' in file:
            print(f"Found: {os.path.join(root, file)}")