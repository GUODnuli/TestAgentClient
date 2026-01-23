import os

# List all files in the current directory
print("Files in current directory:")
try:
    files = os.listdir('.')
    for file in files:
        print(f"- {file}")
except Exception as e:
    print(f"Error listing directory: {e}")

# Try to read the file with the exact name from context
filename = "需求_20260123_134849.txt"
print(f"\nTrying to access: {filename}")
if os.path.exists(filename):
    print("File exists!")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
            print("File content:")
            print(content)
    except Exception as e:
        print(f"Error reading file: {e}")
else:
    print("File does not exist in current directory")