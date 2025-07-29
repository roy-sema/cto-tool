#!/bin/bash

if [ -z "$1" ]; then
  echo "Usage: $0 <analysis_folder>"
  exit 1
fi

ANALYSIS_FOLDER="$1"
total_lines=0

for subfolder in "$ANALYSIS_FOLDER"/*/; do
  GIT_DATA_FILE=$(find "$subfolder" -name "*git_data_count.json" -print -quit)
  if [ -z "$GIT_DATA_FILE" ]; then
    # echo "No git data file found in $subfolder"
    continue
  fi
  digit_sum=$(jq 'paths(scalars) as $p | getpath($p) | select(type == "number")' "$GIT_DATA_FILE" | jq -s 'add')
  echo "Number of commits in $(basename "$subfolder"): $digit_sum"
  total_lines=$((total_lines + digit_sum))

  for file in "$subfolder"/*; do
    if [ -f "$file" ]; then
      file_creation_time=$(stat -c %Y "$file")
      if [ -z "$earliest_time" ] || [ "$file_creation_time" -lt "$earliest_time" ]; then
        earliest_time=$file_creation_time
      fi
      if [ -z "$latest_time" ] || [ "$file_creation_time" -gt "$latest_time" ]; then
        latest_time=$file_creation_time
      fi
    fi
  done
  
done

# This is total lines - it approximates the total number of commits
# Some CSV have 0 commits but a few lines
echo "Total commits: $total_lines"
elapsed_time=$((latest_time - earliest_time))
hours=$((elapsed_time / 3600))
minutes=$(((elapsed_time % 3600) / 60))
echo "Elapsed time: ${hours} hours and ${minutes} minutes"
