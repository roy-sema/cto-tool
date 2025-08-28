import re

from django.db.models import Q
from textdistance import tversky
from thefuzz import fuzz

from mvp.models import Author, Organization


class CommiterDTO:
    """The class is a port of SCQP Java implementation.

    Leaving logic as close as possible to make it easier to fix bugs and add new features.
    Source: https://github.com/Semalab/backend-commitanalysis/blob/master/src/main/java/semalab/commitanalysis/runner/CommiterDTO.java
    """

    ALL_LETTERS = re.compile(r"[^a-zA-Z\s]")
    REMOVE = re.compile(r"^(git|github|me|mail|info|dev|hello)@")
    REMOVE_VAN_DER = re.compile(r"\s+(van|der)\s+")

    def __init__(self, id: int, name: str, email: str):
        self.id = id
        self.email = email
        self.name = name
        self.cleaned_email = self.REMOVE.sub("", email)
        self.cleaned_email = self.ALL_LETTERS.sub("", self.cleaned_email.split("@")[0].lower())

        if "\\" in name:
            name = name.split("\\")[1]

        indexof = name.find("@")
        if indexof > 0:
            name = name[:indexof]

        self.cleaned_name = self.ALL_LETTERS.sub("", name).lower()
        self.cleaned_name = self.REMOVE_VAN_DER.sub("", self.cleaned_name)

        self.name_score = self.name_score_calculation(self.name)
        self.group_included = False
        self.group_ids = []
        self.comparable_string = None

    def name_score_calculation(self, name: str) -> float:
        score = 0
        not_uppercase_score = 0
        special_char_score = 0
        whitespace_score = 0
        trimmed_name = name.strip()
        whitespace = True

        for char in trimmed_name:
            if whitespace:
                whitespace = False
                if not char.isupper():
                    not_uppercase_score += 1
            elif char.isspace():
                whitespace = True
                whitespace_score += 1

        special_char_score = len(trimmed_name) - len(self.cleaned_name)

        if whitespace_score >= 1:
            whitespace_score = 1
        if not_uppercase_score >= 2:
            not_uppercase_score = 2

        return whitespace_score - not_uppercase_score * 0.1 - special_char_score * 0.2

    def get_comparable_string(self):
        if self.comparable_string is None:
            self.comparable_string = []

        return self.comparable_string


class FuzzyMatcher:
    """The class is a port of SCQP Java implementation.

    Leaving logic as close as possible to make it easier to fix bugs and add new features.
    Source: https://github.com/Semalab/backend-commitanalysis/blob/master/src/main/java/semalab/commitanalysis/runner/FuzzyMatcher.java
    """

    @staticmethod
    def matching(first: CommiterDTO, second: CommiterDTO) -> bool:
        # checking how emails close
        if first.email is not None and second.email is not None:
            if first.email and second.email and first.email == second.email:
                return True

            # now working only with letters
            if first.cleaned_email and second.cleaned_email and first.cleaned_email == second.cleaned_email:
                return True

            # checking how emails close by probability 88 - close to only one symbol difference
            if (
                len(first.cleaned_email) > 6
                and len(second.cleaned_email) > 6
                and fuzz.ratio(first.cleaned_email, second.cleaned_email) >= 88
            ):
                return True

        if first.name is not None and second.name is not None and first.name == second.name:
            return True

        # create comparable parts from names (Ivan Ivanov -> i ivanov ivanov i ivani ivan etc.)
        comparable_strings_for_first_name = first.get_comparable_string()
        if first.cleaned_name and not comparable_strings_for_first_name:
            # everything but without spaces
            comparable_strings_for_first_name.append(re.sub(r"\s", "", first.cleaned_name))
            first_name = first.cleaned_name.strip()
            if " " in first_name:
                first_name = re.sub(r"\s+", " ", first_name)
                splits_by = first_name.split(" ")
                included_reverse = False
                for i in range(len(splits_by)):
                    for j in range(i, len(splits_by)):
                        if not included_reverse:
                            included_reverse = True
                            comparable_strings_for_first_name.append((splits_by[1] + splits_by[0]).replace(" ", ""))
                        if i != j:
                            comparable_strings_for_first_name.append(splits_by[i][0] + splits_by[j])
                            comparable_strings_for_first_name.append(splits_by[j] + splits_by[i][0])
                            comparable_strings_for_first_name.append(splits_by[j][0] + splits_by[i])
                            comparable_strings_for_first_name.append(splits_by[i] + splits_by[j][0])

        comparable_strings_for_second_name = second.get_comparable_string()
        if second.cleaned_name and not comparable_strings_for_second_name:
            comparable_strings_for_second_name.append(second.cleaned_name.replace(" ", ""))
            second_name = second.cleaned_name.strip()
            if " " in second_name:
                second_name = re.sub(r"\s+", " ", second_name)
                splits_by = second_name.split(" ")
                included_reverse = False
                for i in range(len(splits_by)):
                    for j in range(i, len(splits_by)):
                        if not included_reverse:
                            included_reverse = True
                            comparable_strings_for_second_name.append((splits_by[1] + splits_by[0]).replace(" ", ""))
                        if i != j:
                            comparable_strings_for_second_name.append(splits_by[i][0] + splits_by[j])
                            comparable_strings_for_second_name.append(splits_by[j] + splits_by[i][0])
                            comparable_strings_for_second_name.append(splits_by[j][0] + splits_by[i])
                            comparable_strings_for_second_name.append(splits_by[i] + splits_by[j][0])

        # if nothing to compare
        if (
            comparable_strings_for_first_name
            and comparable_strings_for_second_name
            and len(comparable_strings_for_first_name) > 1
            and len(comparable_strings_for_second_name) > 1
            and (len(comparable_strings_for_first_name[0]) < 1 or len(comparable_strings_for_second_name[0]) < 1)
        ):
            return False

        # compare generated names
        for first_name in comparable_strings_for_first_name:
            for second_name in comparable_strings_for_second_name:
                if first_name == second.cleaned_email or second_name == first.cleaned_email:
                    return True

        if comparable_strings_for_first_name and comparable_strings_for_second_name:
            for i in range(1):
                for j in range(1):
                    if comparable_strings_for_second_name[i] == comparable_strings_for_first_name[j]:
                        return True

        if comparable_strings_for_first_name and comparable_strings_for_second_name:
            for i in range(1):
                for j in range(1):
                    if (
                        tversky.normalized_similarity(
                            comparable_strings_for_second_name[i],
                            comparable_strings_for_first_name[j],
                        )
                        > 0.7
                    ):
                        return True

        return (
            first.cleaned_email
            and second.cleaned_email
            and tversky.normalized_similarity(second.cleaned_email, first.cleaned_email) > 0.81
        )


class FuzzyMatchingService:
    """The class is a PARTIAL port of SCQP Java implementation.

    Source: https://github.com/Semalab/backend-commitanalysis/blob/f7fa42fe092c46fa303f07d092d01f023c73357c/src/main/java/semalab/commitanalysis/runner/CommitAnalysisRunner.java#L468
    """

    @classmethod
    def set_organization_linked_authors(cls, organization: Organization):
        commiter_dtos = cls.get_organization_commiters(organization)
        id_to_score = {}

        if commiter_dtos:
            for i, first in enumerate(commiter_dtos):
                for j, second in enumerate(commiter_dtos):
                    if i != j and FuzzyMatcher.matching(first, second):
                        first.group_ids.append(second)
                        second.group_ids.append(first)
                        id_to_score.setdefault(second.id, second.name_score)
                        id_to_score.setdefault(first.id, first.name_score)

        groups = []

        stack = []
        for commiter in commiter_dtos:
            if commiter.group_ids:
                stack.append(commiter)
                group = set()
                while stack:
                    current = stack.pop()
                    if not current.group_included:
                        group.add(current.id)
                        group.update(c.id for c in current.group_ids)
                        stack.extend(current.group_ids)
                    current.group_included = True
                if group:
                    groups.append(group)

        new_group_list = [list(group) for group in groups]

        for group in new_group_list:
            parent_id = cls.calculate_parent_id(group, id_to_score)
            group.append(parent_id)

        cls.save_linked_authors(organization, new_group_list)

    @classmethod
    def calculate_parent_id(cls, group: list[int], id_to_score: dict[int, float]) -> int:
        parent_id = group[0]
        current_max_score = id_to_score[parent_id]

        for current_id in group:
            if id_to_score[current_id] > current_max_score:
                parent_id = current_id

        return parent_id

    @classmethod
    def get_organization_commiters(cls, organization: Organization) -> list[CommiterDTO]:
        authors = Author.objects.filter(organization=organization).values("pk", "external_id", "name", "email")
        commiters = []
        for author in authors:
            email = author["email"]
            if not email:
                if "@" in author["external_id"]:
                    email = author["external_id"]
                else:
                    continue

            commiters.append(CommiterDTO(author["pk"], author["name"], email))

        return commiters

    @classmethod
    def save_linked_authors(cls, organization: Organization, groups: list[list[int]]):
        parent_authors = Author.objects.filter(organization=organization, linked_author__isnull=True).values_list(
            "pk", flat=True
        )

        manually_linked_authors = Author.objects.filter(
            Q(organization=organization, linked_author__isnull=False) | Q(organization=organization, split=True)
        ).values_list("pk", flat=True)

        for author_ids in groups:
            # Prevent overriding manually merged/split authors
            not_linked_authors = [author_id for author_id in author_ids if author_id not in manually_linked_authors]
            if len(not_linked_authors) < 2:
                continue

            # Use existing parent if any
            parent_id = next(id for id in parent_authors if id in not_linked_authors)
            if parent_id:
                not_linked_authors.remove(parent_id)
            else:
                parent_id = not_linked_authors.pop()

            Author.objects.filter(pk__in=not_linked_authors).exclude(
                # Avoid self link
                pk=parent_id
            ).update(
                linked_author_id=parent_id,
                # groups should only contain main authors
                # Bulk update does not trigger Author.save()
                group=None,
            )
