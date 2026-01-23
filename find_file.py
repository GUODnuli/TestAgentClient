import os

# Try to find the file in different possible locations
possible_names = [
    "需求_20260123_134849.txt",
    "需求.txt",
    "需求_20260123_134849",
]

# Check current directory
print("Checking current directory:")
for name in possible_names:
    if os.path.exists(name):
        print(f"Found: {name}")
        with open(name, 'r', encoding='utf-8') as f:
            print("Content:")
            print(f.read())
        break
else:
    print("File not found in current directory")

# Check if there's a storage directory
if os.path.exists('storage'):
    print("\nChecking storage directory:")
    for root, dirs, files in os.walk('storage'):
        for name in possible_names:
            if name in files:
                filepath = os.path.join(root, name)
                print(f"Found: {filepath}")
                with open(filepath, 'r', encoding='utf-8') as f:
                    print("Content:")
                    print(f.read())
                break