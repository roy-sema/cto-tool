pin_initiatives_template = """
Below is a list of pre-approved Initiatives (L1) and their corresponding Epics (L2) that were previously generated from similar data:

{initiatives}

Using the provided Git summary data, identify and infer the relevant Initiatives (L1) and their corresponding Epics (L2).

If any inferred Initiatives (L1s) or Epics (L2s) are functionally or conceptually similar to the approved ones listed above, reuse their exact names and descriptions to ensure consistency with user-facing terminology.

It's expected that the percentages or distribution may change based on differences in the input data, especially when new Initiatives or Epics are introduced.
"""
