import { defineStore } from "pinia";

import type { RepositoryFile } from "@/aicm/helpers/api.d";

// Define the state interface
interface RepositoryFilesState {
  repositories: Record<string, RepositoryFile[]>;
}

export const useRepositoryFilesStore = defineStore("repositories", {
  state: (): RepositoryFilesState => ({ repositories: {} }),

  actions: {
    addRepositoryFiles(
      repositoryPkEncoded: string,
      commit_sha: string,
      files: RepositoryFile[],
      reset: boolean = false,
    ) {
      const key = `${repositoryPkEncoded}-${commit_sha}`;
      if (!reset && this.repositories[key]) {
        this.repositories[key].push(...files);
      } else {
        this.repositories[key] = files;
      }
    },

    updateRepositoryFile(repositoryPkEncoded: string, commit_sha: string, newFile: RepositoryFile) {
      const repository = this.repositories[`${repositoryPkEncoded}-${commit_sha}`];
      const oldFile = repository?.find((file) => file.public_id === newFile.public_id);
      if (oldFile) Object.assign(oldFile, newFile);
      else {
        // this should never happen
        throw new Error(`File {${newFile.public_id}} not found in repository ${repositoryPkEncoded}`);
      }
    },

    clearChunkAffectedFiles(code_hash: string, openedFile: RepositoryFile | null = null) {
      // find any file that has the same chunk and clear the chunks so it'd get re-fetched, openedFile is excluded to avoid flashing the UI
      Object.values(this.repositories).forEach((repository) => {
        repository.forEach((file) => {
          if (file.chunks?.find((chunk) => chunk.code_hash === code_hash) && file.public_id !== openedFile?.public_id)
            Object.assign(file, { chunks: [] });
        });
      });
    },
  },
});
