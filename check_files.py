import os
import glob

# List all files in the current directory
print("Current directory contents:")
for file in os.listdir('.'):
    print(f"- {file}")

# Try to find any file with '需求' in the name
print("\nFiles matching '需求':")
for file in glob.glob('*需求*'):
    print(f"- {file}")

# Try to find any .txt files
print("\nAll .txt files:")
for file in glob.glob('*.txt'):
    print(f"- {file}")