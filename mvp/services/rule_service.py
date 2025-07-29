from mvp.models import (
    AITypeChoices,
    Rule,
    RuleConditionCodeTypeChoices,
    RuleConditionModeChoices,
    RuleConditionOperatorChoices,
    RuleRiskChoices,
)


class RuleService:
    RULE_NO_STRENGTH = "no_strength"

    RISK_COLOR_MAP = {
        RuleRiskChoices.HIGH: "red",
        RuleRiskChoices.MEDIUM: "orange",
        RuleRiskChoices.LOW: "yellow",
        RuleRiskChoices.STRENGTH: "green",
        RULE_NO_STRENGTH: "white",
        None: "green",
    }

    RISK_LEVEL_MAP = {
        RuleRiskChoices.HIGH: 4,
        RuleRiskChoices.MEDIUM: 3,
        RuleRiskChoices.LOW: 2,
        RuleRiskChoices.STRENGTH: 1,
        RULE_NO_STRENGTH: 0,
        None: 0,
    }

    @staticmethod
    def validate_rule_conditions(rule, ai_percentages):
        mode_all = rule.condition_mode == RuleConditionModeChoices.ALL
        mode_any = rule.condition_mode == RuleConditionModeChoices.ANY
        mode_none = rule.condition_mode == RuleConditionModeChoices.NONE
        conditions = rule.conditions.all()

        match_conditions = 0
        for condition in conditions:
            ai_type = RuleService.get_condition_ai_type(condition)
            percent = ai_percentages[ai_type]
            is_human = RuleService.get_condition_code_type_is_human(condition)
            if is_human:
                percent = 100 - percent

            match = RuleService.validate_rule_condition(condition, percent)
            if match and mode_any:
                return True

            if not match and mode_all:
                return False

            match_conditions += 1

        if not match_conditions and mode_none:
            return True

        if len(conditions) == match_conditions and mode_all:
            return True

        return False

    @staticmethod
    def get_condition_ai_type(condition):
        if condition.code_type == RuleConditionCodeTypeChoices.AI_BLENDED:
            return AITypeChoices.BLENDED
        elif condition.code_type == RuleConditionCodeTypeChoices.AI_PURE:
            return AITypeChoices.PURE

        # we display Human rules under Overall
        return AITypeChoices.OVERALL

    @staticmethod
    def get_condition_code_type_is_human(condition):
        return condition.code_type == RuleConditionCodeTypeChoices.HUMAN

    @staticmethod
    def validate_rule_condition(condition, percent):
        if condition.operator == RuleConditionOperatorChoices.GREATER_THAN:
            return percent > condition.percentage
        elif condition.operator == RuleConditionOperatorChoices.GREATER_THAN_OR_EQUAL:
            return percent >= condition.percentage
        elif condition.operator == RuleConditionOperatorChoices.EQUAL:
            return percent == condition.percentage
        elif condition.operator == RuleConditionOperatorChoices.LESS_THAN_OR_EQUAL:
            return percent <= condition.percentage
        elif condition.operator == RuleConditionOperatorChoices.LESS_THAN:
            return percent < condition.percentage

    @staticmethod
    def get_rule_risk_color(risk):
        return RuleService.RISK_COLOR_MAP[risk]

    @staticmethod
    def get_rule_risk(rule, ai_percentages):
        conditions_met = RuleService.validate_rule_conditions(rule, ai_percentages)

        if rule.risk == RuleRiskChoices.STRENGTH:
            return rule.risk if conditions_met else RuleService.RULE_NO_STRENGTH

        return rule.risk if conditions_met else None

    @staticmethod
    def get_instance_rules_with_risk(instance, rules):
        rules = sorted(rules, key=lambda r: r.name)
        ai_percentages = RuleService.get_instance_ai_percentage(instance)
        return [(rule, RuleService.get_rule_risk(rule, ai_percentages)) for rule in rules]

    @staticmethod
    def get_rules_by_ai_type(rules, ai_percentages):
        rules = sorted(rules, key=lambda r: r.name)

        by_ai_type = {ai_type: {"list": [], "risk": None} for ai_type in ai_percentages.keys()}

        for rule in rules:
            risk = RuleService.get_rule_risk(rule, ai_percentages)
            color = RuleService.get_rule_risk_color(risk)

            for condition in rule.conditions.all():
                ai_type_key = RuleService.get_condition_ai_type(condition)
                ai_type = by_ai_type[ai_type_key]

                if RuleService.RISK_LEVEL_MAP[risk] > RuleService.RISK_LEVEL_MAP[ai_type["risk"]]:
                    ai_type["risk"] = risk

                if (rule, color) not in ai_type["list"]:
                    ai_type["list"].append((rule, color))
        return by_ai_type

    @staticmethod
    def get_instance_rules_list(instance, rules):
        ai_percentages = RuleService.get_instance_ai_percentage(instance)
        rules_by_type = RuleService.get_rules_by_ai_type(rules, ai_percentages)
        rule_list = {item for rule in rules_by_type.values() for item in rule["list"]}
        return rule_list

    @staticmethod
    def get_instance_ai_percentage(instance):
        return {
            AITypeChoices.OVERALL: instance.percentage_ai_overall(),
            AITypeChoices.PURE: instance.percentage_ai_pure(),
            AITypeChoices.BLENDED: instance.percentage_ai_blended(),
        }

    @staticmethod
    def get_organization_rules(organization):
        return Rule.objects.filter(organization=organization, apply_organization=True).prefetch_related("conditions")

    @staticmethod
    def format_ai_percentage_rules(percentages, rule_list, is_pull_request=False):
        rules = RuleService.get_rules_by_ai_type(
            rule_list,
            {label: percentage["value"] for label, percentage in percentages.items()},
        )

        return [
            {
                "label": AITypeChoices.OVERALL.label,
                "title": f"{AITypeChoices.OVERALL.label} ({AITypeChoices.PURE.label} + {AITypeChoices.BLENDED.label})",
                "desc": "Total percentage of GenAI in the " + ("pull request" if is_pull_request else "codebase"),
                **percentages[AITypeChoices.OVERALL],
                "rules": rules[AITypeChoices.OVERALL]["list"],
                "color": RuleService.get_rule_risk_color(rules[AITypeChoices.OVERALL]["risk"]),
            },
            {
                "label": AITypeChoices.PURE.label,
                "title": AITypeChoices.PURE.label,
                "desc": "Percentage of chunk of code labeled as GenAI, where the whole chunk belongs to single commit",
                **percentages[AITypeChoices.PURE],
                "rules": rules[AITypeChoices.PURE]["list"],
                "color": RuleService.get_rule_risk_color(rules[AITypeChoices.PURE]["risk"]),
            },
            {
                "label": AITypeChoices.BLENDED.label,
                "title": AITypeChoices.BLENDED.label,
                "desc": "Percentage of chunk of code labeled as GenAI, where the chunk belongs to multiple commits",
                **percentages[AITypeChoices.BLENDED],
                "rules": rules[AITypeChoices.BLENDED]["list"],
                "color": RuleService.get_rule_risk_color(rules[AITypeChoices.BLENDED]["risk"]),
            },
        ]

    @classmethod
    def get_stats_rules_list(cls, stats: dict, rules: list[Rule]):
        """
        Generate a list of applicable rules based on author or author group stats.

        Unlike models using the CodeAIPercentageFieldsModel mixin, stats for
        authors and author groups are stored in the AuthorStat model. As a result,
        retrieving the `rules_list` for these models involves an additional step.

        This method should be used after obtaining and serializing the stats
        through `AuthorStat` and `AggregatedAuthorStatSerializer`.

        Example:
            stats = AuthorStat.get_aggregated_group_stats(group.id)
            aggregated_stats = AggregatedAuthorStatSerializer(stats).data
            rules = RuleService.get_stats_rules_list(
                aggregated_stats,
                all_rules,
            )

        Args:
            stats (dict): Serialized stats data for the author or author group.
            rules (list[Rule]): List of rules to evaluate against the stats.

        Returns:
            set: A set of applicable rules extracted from the stats.
        """
        ai_percentages = cls.get_stats_ai_percentage(stats)
        rules_by_type = cls.get_rules_by_ai_type(rules, ai_percentages)
        rule_list = {item for rule in rules_by_type.values() for item in rule["list"]}
        return rule_list

    @staticmethod
    def get_stats_ai_percentage(stats: dict):
        return {
            AITypeChoices.OVERALL: stats["percentage_ai_overall"],
            AITypeChoices.PURE: stats["percentage_ai_pure"],
            AITypeChoices.BLENDED: stats["percentage_ai_blended"],
        }

    @classmethod
    def get_stats_rules_with_risk(cls, stats: dict, rules: list[Rule]):
        """
        Retrieve a list of rules along with their associated risk levels based on
        author or author group stats.

        Stats for authors and author groups are stored in the `AuthorStat` model,
        rather than using the `CodeAIPercentageFieldsModel` mixin. As a result,
        determining `rules_with_risk` for these models requires fetching stats
        through `AuthorStat` methods and then passing them to this method.

        Example:
            stats = AuthorStat.get_aggregated_group_stats(group.id)
            aggregated_stats = AggregatedAuthorStatSerializer(stats).data
            rules_with_risk = RuleService.get_stats_rules_with_risk(
                aggregated_stats,
                all_rules,
            )

        Args:
            stats (dict): Serialized stats data for the author or author group.
            rules (list[Rule]): List of rules to evaluate and calculate risk levels.

        Returns:
            list: A list of tuples where each tuple contains:
                - A `Rule` object.
                - The calculated risk level for the rule.
        """
        rules = sorted(rules, key=lambda r: r.name)
        ai_percentages = cls.get_stats_ai_percentage(stats)
        return [(rule, cls.get_rule_risk(rule, ai_percentages)) for rule in rules]
