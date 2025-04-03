#!/bin/bash

# combine_python.sh - Combines all Python files into a single file with separators

# Default output file name with timestamp
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
OUTPUT_FILE="combined_python_${TIMESTAMP}.py"
SOURCE_DIR="."

# Function to display usage
usage() {
    echo "Usage: $0 [-d source_directory] [-o output_file]"
    echo "  -d: Source directory (default: current directory)"
    echo "  -o: Output file name (default: combined_python_YYYYMMDD_HHMMSS.py)"
    exit 1
}

# Parse command line options
while getopts "d:o:h" opt; do
    case $opt in
        d) SOURCE_DIR="$OPTARG";;
        o) OUTPUT_FILE="$OPTARG";;
        h) usage;;
        ?) usage;;
    esac
done

# Check if source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Error: Source directory '$SOURCE_DIR' does not exist"
    exit 1
fi

# Convert to absolute path
SOURCE_DIR=$(realpath "$SOURCE_DIR")
OUTPUT_FILE=$(realpath "$OUTPUT_FILE")

# Initialize variables
FILE_COUNT=0
SEPARATOR=$(printf '#%.0s' {1..80})

# Write header
echo "# Combined Python Files" > "$OUTPUT_FILE"
echo "# Generated on: $(date '+%Y-%m-%d %H:%M:%S')" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# Find and process Python files
find "$SOURCE_DIR" -type f -name "*.py" | sort | while read -r file; do
    # Calculate relative path
    rel_path="${file#$SOURCE_DIR/}"
    
    # Write separator and file info
    echo "" >> "$OUTPUT_FILE"
    echo "$SEPARATOR" >> "$OUTPUT_FILE"
    echo "# File: $rel_path" >> "$OUTPUT_FILE"
    echo "# Path: $file" >> "$OUTPUT_FILE"
    echo "$SEPARATOR" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    
    # Append file contents
    if cat "$file" >> "$OUTPUT_FILE" 2>/dev/null; then
        echo "" >> "$OUTPUT_FILE"
        ((FILE_COUNT++))
    else
        echo "# ERROR: Could not read file" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
    fi
done

# Write footer
echo "" >> "$OUTPUT_FILE"
echo "$SEPARATOR" >> "$OUTPUT_FILE"
echo "# Total files combined: $FILE_COUNT" >> "$OUTPUT_FILE"
echo "$SEPARATOR" >> "$OUTPUT_FILE"

echo "Combined $FILE_COUNT Python files into '$OUTPUT_FILE'"
