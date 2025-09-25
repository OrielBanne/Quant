"""
Fix Import Issues for All QuantConnect Projects
This script adds the necessary import fixes to all projects
"""

import os
import glob
import shutil

def fix_project_imports(project_dir):
    """Add import fix to a project directory"""
    main_py_path = os.path.join(project_dir, "main.py")
    
    if not os.path.exists(main_py_path):
        return False
    
    # Read the current main.py
    with open(main_py_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if the fix is already applied
    if "import local_test_setup" in content:
        return False
    
    # Add the import fix at the beginning
    fix_import = """# Local testing fix - add this for local development
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import local_test_setup
except ImportError:
    pass  # This will be ignored in QuantConnect environment

"""
    
    # Insert the fix after the imports region
    if "# region imports" in content:
        # Find the end of imports region
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.strip() == "# endregion" and i > 0 and "# region imports" in lines[i-1]:
                # Insert the fix after the endregion
                lines.insert(i + 1, fix_import)
                break
        else:
            # If no imports region found, add at the beginning
            lines.insert(0, fix_import)
    else:
        # Add at the beginning if no imports region
        lines = [fix_import] + content.split('\n')
    
    # Write back the fixed content
    with open(main_py_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    return True

def main():
    """Fix imports for all projects"""
    print("🔧 Fixing import issues for all QuantConnect projects...")
    
    # Get all project directories
    project_dirs = [d for d in os.listdir('.') if os.path.isdir(d) and not d.startswith('.')]
    
    fixed_count = 0
    total_count = 0
    
    for project_dir in project_dirs:
        if project_dir in ['Library', '__pycache__']:
            continue
            
        total_count += 1
        print(f"Processing: {project_dir}")
        
        if fix_project_imports(project_dir):
            print(f"  ✅ Fixed imports for {project_dir}")
            fixed_count += 1
        else:
            print(f"  ⏭️  Skipped {project_dir} (already fixed or no main.py)")
    
    print(f"\n🎉 Import fixes completed!")
    print(f"Fixed: {fixed_count}/{total_count} projects")
    print(f"\nTo test any project locally:")
    print(f"1. cd 'Project Name'")
    print(f"2. python main.py")
    print(f"\nOr use the test script:")
    print(f"python test_algorithm_imports.py")

if __name__ == "__main__":
    main() 