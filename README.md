# ModuleDependency

Usage: python Analyzer.py <directory> [--no-recursive] [--no-stats] [--exclude dir1,dir2,...]

Options:
  --no-recursive    Don't search subdirectories
  --no-stats        Don't show statistics
  --exclude         Comma-separated list of directories to exclude (relative to root)

Example:
  python Analyzer.py /path/to/project --exclude build,test,vendor
