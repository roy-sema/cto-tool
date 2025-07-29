import { describe, expect, it } from "vitest";

import { convertFilePathsToFlatTree, valueFormatted } from "@/aicm/helpers/utils";

describe("convertFilePathsToFlatTree", () => {
  it("converts file paths to tree", () => {
    const file_paths = [
      "/base_file.py",
      "/folder_1/inner.py",
      "/folder_1/folder_1_1/inner_inner.py",
      "/folder_1/folder_1_1/inner_inner_2.py",
      "/folder_2/inner_2.py",
    ];

    const expected_output = {
      "base_file.py": {
        text: "base_file.py",
        children: [],
        state: { opened: false },
        root: true,
        file_path: "/base_file.py",
      },
      "folder_1": {
        text: "folder_1",
        children: ["folder_1/folder_1_1", "folder_1/inner.py"],
        state: { opened: true },
        root: true,
        file_path: "/folder_1",
      },
      "folder_1/folder_1_1": {
        text: "folder_1_1",
        children: ["folder_1/folder_1_1/inner_inner.py", "folder_1/folder_1_1/inner_inner_2.py"],
        state: { opened: false },
        root: false,
        file_path: "/folder_1/folder_1_1",
      },
      "folder_1/inner.py": {
        text: "inner.py",
        children: [],
        state: { opened: false },
        root: false,
        file_path: "/folder_1/inner.py",
      },
      "folder_2": {
        text: "folder_2",
        children: ["folder_2/inner_2.py"],
        state: { opened: false },
        root: true,
        file_path: "/folder_2",
      },
      "folder_2/inner_2.py": {
        text: "inner_2.py",
        children: [],
        state: { opened: false },
        root: false,
        file_path: "/folder_2/inner_2.py",
      },
      "folder_1/folder_1_1/inner_inner.py": {
        text: "inner_inner.py",
        children: [],
        state: { opened: false },
        root: false,
        file_path: "/folder_1/folder_1_1/inner_inner.py",
      },
      "folder_1/folder_1_1/inner_inner_2.py": {
        text: "inner_inner_2.py",
        children: [],
        state: { opened: false },
        root: false,
        file_path: "/folder_1/folder_1_1/inner_inner_2.py",
      },
    };

    const openedPaths = ["/folder_1"];

    const output = convertFilePathsToFlatTree(file_paths, openedPaths);
    expect(output).toEqual(expected_output);
  });
});

describe("valueFormatted", () => {
  it("formats value to 2 decimals if value is between 0 and 1", () => {
    const value = 0.123456789;
    const expected_output = "0.12";
    expect(valueFormatted(value)).toEqual(expected_output);
  });

  it("formats value to 2 decimals if value is between 0 and 1 and has 1 decimal", () => {
    const value = 0.4;
    const expected_output = "0.40";
    expect(valueFormatted(value)).toEqual(expected_output);
  });

  it("formats value to 0 decimals and round if value is larger than 1, round down", () => {
    const value = 1.123;
    const expected_output = "1";
    expect(valueFormatted(value)).toEqual(expected_output);
  });

  it("formats value to 0 decimals and round if value is larger than 1, round up", () => {
    const value = 1.5;
    const expected_output = "2";
    expect(valueFormatted(value)).toEqual(expected_output);
  });

  it("formats value to 0 decimal if value is negative", () => {
    const value = -1.13;
    const expected_output = "-1";
    expect(valueFormatted(value)).toEqual(expected_output);
  });
});
