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

def analyze_directory(directory, recursive=True, exclude_dirs=None):
    """Analyze C/C++ files in directory and return dependencies."""
    root_dir = Path(directory).resolve()
    dependencies = defaultdict(set)
    all_files = set()
    
    # Prepare exclude paths (convert to absolute paths)
    exclude_paths = set()
    if exclude_dirs:
        for exclude_dir in exclude_dirs:
            exclude_path = (root_dir / exclude_dir).resolve()
            exclude_paths.add(exclude_path)
    
    # Scan for C/C++ files
    extensions = {'.c', '.h', '.cpp', '.hpp', '.cc', '.hh', '.cxx', '.hxx'}
    
    if recursive:
        for ext in extensions:
            for file_path in root_dir.rglob(f'*{ext}'):
                # Check if file is in excluded directory
                file_absolute = file_path.resolve()
                is_excluded = any(
                    exclude_path in file_absolute.parents or file_absolute == exclude_path
                    for exclude_path in exclude_paths
                )
                if not is_excluded:
                    all_files.add(file_path)
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

def analyze_cycle_breaking_points(dependencies, cycle):
    """
    Analyze a circular dependency group and suggest breaking points.
    Returns analysis of how to break the cycle.
    """
    cycle_set = set(cycle)
    
    # 1. Calculate metrics for each module in the cycle
    module_metrics = {}
    
    for module in cycle:
        # Internal connections (within cycle)
        internal_out = len([t for t in dependencies.get(module, set()) if t in cycle_set])
        internal_in = sum(1 for m in cycle if module in dependencies.get(m, set()))
        
        # External connections (outside cycle)
        external_out = len([t for t in dependencies.get(module, set()) if t not in cycle_set])
        external_in = sum(1 for m in dependencies if m not in cycle_set and module in dependencies.get(m, set()))
        
        # Calculate coupling score (higher = more central to cycle)
        coupling_score = internal_out + internal_in
        
        # Calculate interface score (higher = more external dependencies)
        interface_score = external_out + external_in
        
        module_metrics[module] = {
            'internal_out': internal_out,
            'internal_in': internal_in,
            'external_out': external_out,
            'external_in': external_in,
            'coupling': coupling_score,
            'interface': interface_score,
            'total_deps': internal_out + external_out
        }
    
    # 2. Identify bridge modules (candidates to extract)
    # Bridge: low internal coupling, high external interface
    bridges = []
    for module, metrics in module_metrics.items():
        if metrics['coupling'] > 0:  # Has some connections
            bridge_score = metrics['interface'] / (metrics['coupling'] + 1)
            bridges.append((module, bridge_score, metrics))
    
    bridges.sort(key=lambda x: -x[1])  # Sort by bridge score (descending)
    
    # 3. Identify core modules (central to the cycle)
    core_modules = sorted(
        module_metrics.items(),
        key=lambda x: (-x[1]['coupling'], -x[1]['interface'])
    )
    
    # 4. Identify leaf modules (easy to extract)
    leaves = []
    for module, metrics in module_metrics.items():
        if metrics['internal_out'] <= 1 or metrics['internal_in'] <= 1:
            leaf_score = metrics['external_out'] + metrics['external_in']
            leaves.append((module, leaf_score, metrics))
    
    leaves.sort(key=lambda x: -x[1])
    
    # 5. Analyze edge removal (which dependencies to break)
    edge_impact = []
    for module in cycle:
        if module in dependencies:
            for target in dependencies[module]:
                if target in cycle_set:
                    # Calculate impact of removing this edge
                    source_metrics = module_metrics[module]
                    target_metrics = module_metrics[target]
                    
                    # Lower impact = better to remove
                    impact = (source_metrics['coupling'] + target_metrics['coupling']) / 2
                    edge_impact.append((module, target, impact))
    
    edge_impact.sort(key=lambda x: x[2])  # Sort by impact (ascending)
    
    return {
        'module_metrics': module_metrics,
        'bridges': bridges[:3],  # Top 3 bridge candidates
        'core_modules': core_modules[:5],  # Top 5 core modules
        'leaves': leaves[:3],  # Top 3 leaf candidates
        'edge_impact': edge_impact[:5]  # Top 5 edges to consider breaking
    }

def find_circular_dependencies(dependencies):
    """Find all circular dependencies using Tarjan's SCC algorithm."""
    
    def strongconnect(node):
        """Tarjan's strongly connected components algorithm."""
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        
        if node in dependencies:
            for neighbor in dependencies[node]:
                if neighbor not in indices:
                    strongconnect(neighbor)
                    lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
                elif neighbor in on_stack:
                    lowlinks[node] = min(lowlinks[node], indices[neighbor])
        
        # If node is a root node, pop the stack and generate an SCC
        if lowlinks[node] == indices[node]:
            component = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                component.append(w)
                if w == node:
                    break
            
            # Only consider components with more than one node (cycles)
            if len(component) > 1:
                sccs.append(component)
    
    # Initialize
    indices = {}
    lowlinks = {}
    stack = []
    on_stack = set()
    sccs = []
    index = 0
    
    # Get all nodes
    all_nodes = set(dependencies.keys())
    for targets in dependencies.values():
        all_nodes.update(targets)
    
    # Run algorithm on all nodes
    for node in all_nodes:
        if node not in indices:
            strongconnect(node)
    
    # Normalize cycles (start from smallest element for consistent output)
    normalized_cycles = []
    for scc in sccs:
        if len(scc) > 1:
            # Sort for consistent ordering
            sorted_scc = sorted(scc)
            normalized_cycles.append(sorted_scc)
    
    # Sort cycles by size (largest first) then alphabetically
    normalized_cycles.sort(key=lambda x: (-len(x), x[0]))
    
    return normalized_cycles

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
    
    # Find circular dependencies
    circular_deps = find_circular_dependencies(dependencies)
    
    return most_referenced, most_referencing, circular_deps

def print_statistics(most_referenced, most_referencing, circular_deps, dependencies):
    """Print reference statistics in a formatted way."""
    # Calculate maximum module name length for formatting
    all_modules = set()
    for module, _ in most_referenced:
        all_modules.add(module)
    for module, _ in most_referencing:
        all_modules.add(module)
    
    max_module_len = max(len(module) for module in all_modules) if all_modules else 10
    max_module_len = max(max_module_len, len("Module"))  # At least as wide as header
    
    # Calculate total width
    total_width = max(60, 50 + max_module_len)
    
    print("\n" + "=" * total_width)
    print("DEPENDENCY ANALYSIS RESULTS")
    print("=" * total_width)
    
    # Most referenced modules
    print("\n[>>] MOST REFERENCED MODULES (다른 모듈들이 가장 많이 참조하는 모듈)")
    print("-" * total_width)
    print(f"{'Rank':<6} {'Module':<{max_module_len}} {'Referenced By':<15} {'Visual'}")
    print("-" * total_width)
    
    max_refs = max([count for _, count in most_referenced]) if most_referenced else 1
    for i, (module, count) in enumerate(most_referenced, 1):
        bar_length = int((count / max_refs) * 30) if max_refs > 0 else 0
        bar = "#" * bar_length + "-" * (30 - bar_length)
        print(f"{i:<6} {module:<{max_module_len}} {count:<15} {bar}")
    
    # Most referencing modules
    print("\n[<<] MOST REFERENCING MODULES (가장 많은 모듈을 참조하는 모듈)")
    print("-" * total_width)
    print(f"{'Rank':<6} {'Module':<{max_module_len}} {'References':<15} {'Visual'}")
    print("-" * total_width)
    
    max_refs = max([count for _, count in most_referencing]) if most_referencing else 1
    for i, (module, count) in enumerate(most_referencing, 1):
        bar_length = int((count / max_refs) * 30) if max_refs > 0 else 0
        bar = "#" * bar_length + "-" * (30 - bar_length)
        print(f"{i:<6} {module:<{max_module_len}} {count:<15} {bar}")
    
    # Circular dependencies (SCC groups)
    print("\n[@] CIRCULAR DEPENDENCIES (순환 참조 - Strongly Connected Components)")
    print("-" * total_width)
    
    if circular_deps:
        total_modules_in_cycles = sum(len(cycle) for cycle in circular_deps)
        print(f"[!] Found {len(circular_deps)} circular dependency group(s)")
        print(f"[!] Total {total_modules_in_cycles} modules involved in cycles\n")
        
        for i, cycle in enumerate(circular_deps, 1):
            print(f"{i}. SCC Group (Size: {len(cycle)} modules)")
            print("   " + "-" * 70)
            
            # Show first 5 modules in the cycle
            if len(cycle) <= 10:
                cycle_str = " <-> ".join(cycle)
                print(f"   Modules: {cycle_str}")
            else:
                # Show first 5 and last 2 for large cycles
                first_part = " <-> ".join(cycle[:5])
                last_part = " <-> ".join(cycle[-2:])
                print(f"   Modules: {first_part} <-> ... <-> {last_part}")
                print(f"   (Showing 7 of {len(cycle)} modules)")
            
            # Analyze breaking points for cycles with 3+ modules
            if len(cycle) >= 3:
                print()
                analysis = analyze_cycle_breaking_points(dependencies, cycle)
                
                # Show how to break this cycle
                print("   [BREAKING STRATEGY]")
                print()
                
                # Strategy 1: Extract bridge modules
                if analysis['bridges']:
                    print("   Strategy 1: Extract Bridge Modules (모듈 추출)")
                    print("   - These modules connect to external systems")
                    for j, (module, score, metrics) in enumerate(analysis['bridges'], 1):
                        print(f"     {j}. {module}")
                        print(f"        Internal: ←{metrics['internal_in']} (in)  {metrics['internal_out']}→ (out) | "
                              f"External: ←{metrics['external_in']} (in)  {metrics['external_out']}→ (out)")
                        print(f"        Bridge Score: {score:.2f} (higher = better candidate)")
                    print()
                
                # Strategy 2: Break weak edges
                if analysis['edge_impact']:
                    print("   Strategy 2: Break Weak Dependencies (의존성 제거)")
                    print("   - Remove these dependencies to break the cycle")
                    for j, (source, target, impact) in enumerate(analysis['edge_impact'], 1):
                        print(f"     {j}. {source} --> {target} (impact: {impact:.2f})")
                    print()
                
                # Strategy 3: Extract leaf modules
                if analysis['leaves']:
                    print("   Strategy 3: Extract Leaf Modules (약한 결합 모듈)")
                    print("   - These modules have fewer internal connections")
                    for j, (module, score, metrics) in enumerate(analysis['leaves'], 1):
                        print(f"     {j}. {module} (internal: {metrics['coupling']}, external: {metrics['interface']})")
                    print()
                
                # Show core modules (hardest to extract)
                print("   [CORE MODULES] - Keep these together")
                print("   - These are most central to the cycle")
                for j, (module, metrics) in enumerate(analysis['core_modules'][:3], 1):
                    print(f"     {j}. {module} (coupling: {metrics['coupling']})")
                print()
            
            # Add warning for large cycles
            if len(cycle) > 10:
                print(f"   [WARNING] Large circular dependency group detected!")
                print(f"   Consider major refactoring or layered architecture.")
            
            print()
    else:
        print("[OK] No circular dependencies found!")
        print()
    
    print("=" * total_width)

def main():
    if len(sys.argv) < 2:
        print("Usage: python Analyzer.py <directory> [--no-recursive] [--no-stats] [--exclude dir1,dir2,...]")
        print("\nOptions:")
        print("  --no-recursive    Don't search subdirectories")
        print("  --no-stats        Don't show statistics")
        print("  --exclude         Comma-separated list of directories to exclude (relative to root)")
        print("\nExample:")
        print("  python Analyzer.py /path/to/project --exclude build,test,vendor")
        sys.exit(1)
    
    directory = sys.argv[1]
    recursive = "--no-recursive" not in sys.argv
    show_stats = "--no-stats" not in sys.argv
    
    # Parse exclude directories
    exclude_dirs = []
    for i, arg in enumerate(sys.argv):
        if arg == "--exclude" and i + 1 < len(sys.argv):
            exclude_dirs = [d.strip() for d in sys.argv[i + 1].split(',')]
            break
    
    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a valid directory")
        sys.exit(1)
    
    # Print configuration
    if exclude_dirs:
        print(f"Excluding directories: {', '.join(exclude_dirs)}")
        print()
    
    # Analyze dependencies
    dependencies = analyze_directory(directory, recursive, exclude_dirs)
    
    # Generate and print Mermaid diagram
    mermaid = generate_mermaid(dependencies)
    print(mermaid)
    
    # Print statistics if requested
    if show_stats and dependencies:
        most_referenced, most_referencing, circular_deps = analyze_references(dependencies)
        print_statistics(most_referenced, most_referencing, circular_deps, dependencies)

if __name__ == '__main__':
    main()
