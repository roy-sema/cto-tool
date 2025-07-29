#!/bin/bash

if [ -z "$1" ]; then
  echo "Usage: $0 <analysis_folder>"
  exit 1
fi

ANALYSIS_FOLDER="$1"

CSV_FILE="$ANALYSIS_FOLDER/all_results.csv"
echo "group;output" > "$CSV_FILE"

# Loop through each subfolder in the source folder
for SUBFOLDER in "$ANALYSIS_FOLDER"/*; do
  if [ -d "$SUBFOLDER" ]; then
    # Get the subfolder name
    SUBFOLDER_NAME=$(basename "$SUBFOLDER")    
    
    for JSON_FILE in "$SUBFOLDER"/*final.json; do # Only one json file per subfolder (the final one)
      if [ -f "$JSON_FILE" ]; then
        # Check if the final analysis was produced        
        LINE_COUNT=$(wc -l < "$JSON_FILE")
        if [ "$LINE_COUNT" -gt 5 ]; then
          JSON_CONTENT=$(jq . "$JSON_FILE" | sed 's/"/""/g') # Format JSON and escape double quotes
          echo "$SUBFOLDER_NAME;\"$JSON_CONTENT\"" >> "$CSV_FILE"
        else
          echo "$SUBFOLDER_NAME;analyses not produced" >> "$CSV_FILE"
        fi
      else
        # Check if there are commits in this time range
        GIT_DATA_FILE=$(find "$SUBFOLDER" -name "*git_data.csv" -print -quit)
        LINE_COUNT=$(wc -l < "$GIT_DATA_FILE")
        if [ "$LINE_COUNT" -lt 3 ]; then
          echo "$SUBFOLDER_NAME;no commits in this time range" >> "$CSV_FILE"          
        else
          echo "$SUBFOLDER_NAME;analyses not produced" >> "$CSV_FILE"
        fi
      fi
    done
  fi
done
