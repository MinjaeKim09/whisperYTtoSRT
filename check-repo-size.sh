#!/bin/bash

# Repository size monitoring script
echo "🔍 Repository Size Analysis"
echo "=========================="

# Check .git directory size
git_size=$(du -sh .git | cut -f1)
echo "📁 .git directory size: $git_size"

# Check total repository size
total_size=$(du -sh . | cut -f1)
echo "📁 Total repository size: $total_size"

echo ""
echo "🔍 Large files in working directory:"
echo "-----------------------------------"
find . -name ".git" -prune -o -type f -size +1M -print | head -10 | while read -r file; do
    size=$(du -sh "$file" | cut -f1)
    echo "  $size  $file"
done

echo ""
echo "🔍 Files that might grow large:"
echo "------------------------------"
find . -name "*.wav" -o -name "*.mp3" -o -name "*.mp4" -o -name "*.srt" -o -name "*.log" | head -5 | while read -r file; do
    if [ -f "$file" ]; then
        size=$(du -sh "$file" | cut -f1)
        echo "  $size  $file"
    fi
done

echo ""
echo "📊 Git repository statistics:"
echo "----------------------------"
echo "Commits: $(git rev-list --all --count)"
echo "Branches: $(git branch -a | wc -l | tr -d ' ')"
echo "Current branch: $(git branch --show-current)"

echo ""
echo "💡 Tips:"
echo "- Keep .git under 100MB for easy GitHub pushes"
echo "- Use .gitignore for temporary/large files"
echo "- Run this script regularly: ./check-repo-size.sh" 