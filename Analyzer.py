#!/usr/bin/env python3
"""
C to Mermaid - Simple C dependency to Mermaid state diagram converter
"""

import os
import re
import sys
from pathlib import Path
from collections import defaultdict

def get_base_name(filename):
    """Get base name without extension."""
    return os.path.splitext(os.path.basename(filename))[0]

def parse_includes(file_path):
    """Parse a file and extract user-defined includes."""
    includes = set()
    user_include_pattern = re.compile(r'^\s*#include\s+"([^"]+)"', re.MULTILINE)
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        matches = user_include_pattern.findall(content)
        for match in matches:
            included_file = os.path.basename(match)
            base_name = get_base_name(included_file)
            includes.add(base_name)
    except:
        pass
    
    return includes

def analyze_directory(directory, recursive=True):
    """Analyze C/C++ files in directory and return dependencies."""
    root_dir = Path(directory)
    dependencies = defaultdict(set)
    all_files = set()
    
    # Scan for C/C++ files
    extensions = {'.c', '.h', '.cpp', '.hpp', '.cc', '.hh', '.cxx', '.hxx'}
    
    if recursive:
        for ext in extensions:
            all_files.update(root_dir.rglob(f'*{ext}'))
    else:
        for ext in extensions:
            all_files.update(root_dir.glob(f'*{ext}'))
    
    # Parse each file
    for file_path in all_files:
        base_name = get_base_name(file_path.name)
        includes = parse_includes(file_path)
        includes.discard(base_name)  # Remove self-references
        dependencies[base_name].update(includes)
    
    # Filter out dependencies to non-existent files
    all_base_names = {get_base_name(f.name) for f in all_files}
    filtered_dependencies = {}
    
    for file_base, includes in dependencies.items():
        valid_includes = includes.intersection(all_base_names)
        if valid_includes or file_base in all_base_names:
            filtered_dependencies[file_base] = valid_includes
    
    return filtered_dependencies

def generate_mermaid(dependencies):
    """Generate Mermaid state diagram from dependencies."""
    lines = ["stateDiagram-v2"]
    
    # Create edges
    edges_added = False
    for source, targets in dependencies.items():
        for target in targets:
            lines.append(f"    {source} --> {target}")
            edges_added = True
    
    # If no edges, add isolated nodes
    if not edges_added and dependencies:
        for node in dependencies.keys():
            lines.append(f"    {node}")
    
    return "\n".join(lines)

def analyze_references(dependencies):
    """Analyze reference statistics from dependencies."""
    # Count incoming references (how many modules reference this module)
    incoming_refs = defaultdict(int)
    # Count outgoing references (how many modules this module references)
    outgoing_refs = defaultdict(int)
    
    # Build statistics
    all_modules = set(dependencies.keys())
    for source, targets in dependencies.items():
        outgoing_refs[source] = len(targets)
        for target in targets:
            incoming_refs[target] += 1
            all_modules.add(target)
    
    # Ensure all modules are in both dictionaries (with 0 if no references)
    for module in all_modules:
        if module not in incoming_refs:
            incoming_refs[module] = 0
        if module not in outgoing_refs:
            outgoing_refs[module] = 0
    
    # Sort by incoming references (most referenced modules)
    most_referenced = sorted(incoming_refs.items(), key=lambda x: (-x[1], x[0]))
    
    # Sort by outgoing references (modules that reference the most others)
    most_referencing = sorted(outgoing_refs.items(), key=lambda x: (-x[1], x[0]))
    
    return most_referenced, most_referencing

def print_statistics(most_referenced, most_referencing):
    """Print reference statistics in a formatted way."""
    print("\n" + "="*60)
    print("DEPENDENCY ANALYSIS RESULTS")
    print("="*60)
    
    # Most referenced modules
    print("\n📥 MOST REFERENCED MODULES (다른 모듈들이 가장 많이 참조하는 모듈)")
    print("-" * 60)
    print(f"{'Rank':<6} {'Module':<20} {'Referenced By':<15} {'Visual'}")
    print("-" * 60)
    
    max_refs = max([count for _, count in most_referenced]) if most_referenced else 1
    for i, (module, count) in enumerate(most_referenced, 1):
        bar_length = int((count / max_refs) * 30) if max_refs > 0 else 0
        bar = "█" * bar_length + "░" * (30 - bar_length)
        print(f"{i:<6} {module:<20} {count:<15} {bar}")
    
    # Most referencing modules
    print("\n📤 MOST REFERENCING MODULES (가장 많은 모듈을 참조하는 모듈)")
    print("-" * 60)
    print(f"{'Rank':<6} {'Module':<20} {'References':<15} {'Visual'}")
    print("-" * 60)
    
    max_refs = max([count for _, count in most_referencing]) if most_referencing else 1
    for i, (module, count) in enumerate(most_referencing, 1):
        bar_length = int((count / max_refs) * 30) if max_refs > 0 else 0
        bar = "█" * bar_length + "░" * (30 - bar_length)
        print(f"{i:<6} {module:<20} {count:<15} {bar}")
    
    print("\n" + "="*60)

def main():
    if len(sys.argv) < 2:
        print("Usage: python c_to_mermaid.py <directory> [--no-recursive] [--no-stats]")
        sys.exit(1)
    
    directory = sys.argv[1]
    recursive = "--no-recursive" not in sys.argv
    show_stats = "--no-stats" not in sys.argv
    
    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a valid directory")
        sys.exit(1)
    
    # Analyze dependencies
    dependencies = analyze_directory(directory, recursive)
    
    # Generate and print Mermaid diagram
    mermaid = generate_mermaid(dependencies)
    print(mermaid)
    
    # Print statistics if requested
    if show_stats and dependencies:
        most_referenced, most_referencing = analyze_references(dependencies)
        print_statistics(most_referenced, most_referencing)

if __name__ == '__main__':
    main()
