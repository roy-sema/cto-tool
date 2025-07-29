import type { Tree } from "../helpers/api.d";

export function convertFilePathsToFlatTree(
  filePaths: string[],
  openedPaths: string[] = [],
  isFiltered: boolean = false,
): Tree {
  const tree: Tree = {};

  filePaths.forEach((filePath) => {
    const parts = filePath.split("/");
    let currentPath = "";
    parts.forEach((part) => {
      if (part !== "") {
        const part_path = currentPath ? `${currentPath}/${part}` : part;
        if (part_path in tree == false) {
          const file_path = `/${part_path}`;
          tree[part_path] = {
            text: part,
            children: [],
            state: { opened: openedPaths.includes(file_path) || isFiltered },
            root: currentPath.trim() === "",
            file_path: file_path,
          };
        }
        if (currentPath && !tree[currentPath].children.includes(part_path)) {
          tree[currentPath].children.push(part_path);
        }
        currentPath = part_path;
      }
    });
  });

  Object.keys(tree).forEach((key) => {
    // directories first, sort alphabetically
    const [directories, files] = partition(tree[key].children, (child) => tree[child].children.length > 0);
    directories.sort();
    files.sort();
    tree[key].children = [...directories, ...files];
  });
  return tree;
}

/**
 * Partitions an array into two arrays based on a provided filter function.
 *
 * @param {any[]} array - The array to be partitioned.
 * @param {(e: any) => boolean} filter - The filter function that determines whether an element should be included in the "pass" array or the "fail" array.
 * @return {[any[], any[]]} An array containing two arrays: the first array contains the elements that passed the filter, and the second array contains the elements that failed the filter.
 */
export function partition(array: any[], filter: (e: any) => boolean): [any[], any[]] {
  const pass: any[] = [];
  const fail: any[] = [];
  array.forEach((elem) => (filter(elem) ? pass : fail).push(elem));
  return [pass, fail];
}

export function valueFormatted(value: number): string {
  // format to 2 decimals if value is between 0 and 1, otherwise round to 0 decimals
  const precision = value < 1 && value > 0 ? 2 : 0;
  if (precision === 0) value = Math.round(value);
  return value.toFixed(precision);
}

export function round(value: number | string | undefined): number {
  // round number, string or undefined to nearest integer
  if (typeof value === "number") {
    return Math.round(value);
  } else if (typeof value === "string") {
    return Math.round(Number(value));
  } else {
    return 0;
  }
}
