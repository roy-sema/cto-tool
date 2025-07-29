#!/bin/bash

# Define the folder containing subfolders and the target folder
SOURCE_FOLDER="/home/simone/tests/TB-Sentry-analyses-all"
TARGET_FOLDER="/home/simone/tests/TB-Sentry-analyses-individual-repo"
ANALYSIS_FOLDER="/home/simone/tests/TB-Sentry-analyses-individual-repo-analyses"

# Loop through each subfolder in the source folder
for SUBFOLDER in "$SOURCE_FOLDER"/*; do
  if [ -d "$SUBFOLDER" ]; then
    # Get the subfolder name
    SUBFOLDER_NAME=$(basename "$SUBFOLDER")
    
    # Move the subfolder to the target folder
    sudo mv "$SUBFOLDER" "$TARGET_FOLDER"
    
    python main.py --git-folder-path "$TARGET_FOLDER" --start-date 2024-10-24T00:00:00 --end-date 2024-11-24T23:59:59

    # Copy analysis results to a new folder
    mkdir "$ANALYSIS_FOLDER"/git_dataset_"$SUBFOLDER_NAME"
    mv "$TARGET_FOLDER"/git_dataset "$ANALYSIS_FOLDER"/git_dataset_"$SUBFOLDER_NAME"
    
    # Move the subfolder back to the source folder
    sudo mv "$TARGET_FOLDER/$SUBFOLDER_NAME" "$SOURCE_FOLDER"
  fi

  # # Break for debugging
  # break
done
