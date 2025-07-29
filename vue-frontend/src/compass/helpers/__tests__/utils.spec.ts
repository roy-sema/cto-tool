import { describe, expect, it } from "vitest";

import { avatarTitle, toHumanReadableDate } from "@/compass/helpers/utils";

describe("avatarTitle", () => {
  it("Gets the letters of a first last name", () => {
    const value = "John Doe";
    const expected_output = "JD";
    expect(avatarTitle(value)).toEqual(expected_output);
  });

  it("Gets the letters of a full name", () => {
    const value = "John Ash Doe";
    const expected_output = "JD";
    expect(avatarTitle(value)).toEqual(expected_output);
  });

  it("Gets the letters of a single name", () => {
    const value = "John";
    const expected_output = "J";
    expect(avatarTitle(value)).toEqual(expected_output);
  });

  it("Ensure that the first letter is always uppercase", () => {
    const value = "john";
    const expected_output = "J";
    expect(avatarTitle(value)).toEqual(expected_output);
  });

  it("Ensure that the first letter is always uppercase single name", () => {
    const value = "john doe";
    const expected_output = "JD";
    expect(avatarTitle(value)).toEqual(expected_output);
  });

  it("Handle names with multiple spaces", () => {
    const value = "  John    Doe ";
    const expected_output = "JD";
    expect(avatarTitle(value)).toEqual(expected_output);
  });
});

describe("to human readable date", () => {
  it("Converts a date to a human readable date", () => {
    const value = 1679014400;
    const expected_output = "Friday, March 17, 2023 at 3:53 AM";
    expect(toHumanReadableDate(value, "Asia/Kuwait")).toEqual(expected_output);
  });

  it("Converts a date to a human readable date", () => {
    const value = 1739790084;
    const expected_output = "Monday, February 17, 2025 at 6:01 AM";
    expect(toHumanReadableDate(value, "America/New_York")).toEqual(expected_output);
  });

  describe("to human readable date", () => {
    it("Handles undefined", () => {
      const value = undefined;
      const expected_output = "No data";
      expect(toHumanReadableDate(value)).toEqual(expected_output);
    });
  });
});
