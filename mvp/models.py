import os
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Self

from auditlog.registry import auditlog
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import AbstractUser, BaseUserManager, Group
from django.core import exceptions
from django.core.cache import cache
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Case, F, Min, Prefetch, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone as django_timezone
from django.utils.translation import gettext_lazy as _
from django_softdelete.models import SoftDeleteModel
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill
from timescale.db.models.models import TimescaleModel
from treebeard.mp_tree import MP_Node

from cto_tool.storages import get_s3_storage
from mvp.mixins import DecodePublicIdMixin, PublicIdMixin
from mvp.utils import normalize_end_date, normalize_start_date, round_half_up


class OrgRole:
    DEVELOPER = "Developer"
    ENGINEERING_LEADER = "EngineeringLeader"
    COMPLIANCE_LEADER = "ComplianceLeader"
    SETTINGS_EDITOR = "SettingsEditor"
    OWNER = "Owner"
    USER = "User"


class RepositoryCommitStatusChoices(models.TextChoices):
    PENDING = "pending", "Pending"
    ANALYZED = "analyzed", "Analyzed"
    FAILURE = "failure", "Failure"


class RepositoryGroupCategoryChoices(models.TextChoices):
    PRODUCTION = "production", "Production"
    PRODUCTION_LEGACY = "production_legacy", "Production - Legacy"
    INTERNAL_TOOLS = "internal_tools", "Internal Tools"
    DEVELOPMENT = "development", "Development"
    NOT_IN_USE = "not_in_use", "Not in use"

    @staticmethod
    def get_as_detailed_list():
        return [
            {
                "id": RepositoryGroupCategoryChoices.PRODUCTION,
                "label": "Production",
                "description": "Code is In Production and Used",
            },
            {
                "id": RepositoryGroupCategoryChoices.PRODUCTION_LEGACY,
                "label": "Production-Legacy",
                "description": "Code is In Production and Used but is an older version and may be sunset in the future.",
            },
            {
                "id": RepositoryGroupCategoryChoices.INTERNAL_TOOLS,
                "label": "Internal Tools",
                "description": "Tools, infrastructure, QA etc. that support production.",
            },
            {
                "id": RepositoryGroupCategoryChoices.DEVELOPMENT,
                "label": "Development",
                "description": "Code still under development and not yet in production.",
            },
            {
                "id": RepositoryGroupCategoryChoices.NOT_IN_USE,
                "label": "Not in use",
                "description": "Internal and external users no longer use the code.",
            },
        ]


class AITypeChoices(models.TextChoices):
    BLENDED = "blended", "Blended"
    OVERALL = "overall", "Overall"
    PURE = "pure", "Pure"


class AITypeChoicesField(models.JSONField):
    description = _("List of AI type choices")

    def validate(self, value, model_instance):
        super().validate(value, model_instance)
        for item in value:
            if item not in dict(AITypeChoices.choices):
                raise exceptions.ValidationError(
                    _("%(value)s is not a valid choice."),
                    params={"value": item},
                )


class AppComponentChoices(models.TextChoices):
    SEMA_SCORE = "sema_score", "Sema Score"


class CodeGenerationLabelChoices(models.TextChoices):
    AI = "ai", "PureAI"
    BLENDED = "blended", "Blended"
    HUMAN = "human", "NotGenAI"
    NOT_EVALUATED = "not_evaluated", "NotEvaluated"


class ComplianceStandardStatusChoices(models.TextChoices):
    CONTEMPLATED = "contemplated", "1-Contemplated"
    PROPOSED = "proposed", "2-Proposed"
    CLOSE_TO_IMPLEMENTATION = "close_to_implementation", "3-Close to implementation"
    PARTIALLY_IN_EFFECT = "partially_in_effect", "4-Partially in effect"
    FULLY_IMPLEMENTED = "fully_implemented", "5-Fully implemented"
    TO_BE_DETERMINED = "to_be_determined", "6-To Be Determined"


class ComplianceStandardRiskLevelChoices(models.TextChoices):
    CRITICAL = "critical", "1-Critical"
    HIGH = "high", "2-High"
    MEDIUM = "medium", "3-Medium"
    LOW = "low", "4-Low"
    TO_BE_DETERMINED = "to_be_determined", "5-To be determined"


class ComplianceStandardSourceChoices(models.TextChoices):
    INTERNAL = "internal", "1-Internal"
    GOVERNMENT = "government", "2-Government"
    OTHER_STAKEHOLDERS = "other_stakeholders", "3-Other stakeholders"


class ComplianceStandardRiskTypeChoices(models.TextChoices):
    STRATEGIC = "strategic", "1-Strategic"
    OPERATIONAL = "operational", "2-Operational"


class ComplianceStandardOrganizationSizeChoices(models.TextChoices):
    ANY_SIZE = "any_size", "1-Firms of Any size"
    SME = "sme", "2-SMEs (10-249 Employees)"
    LARGE = "large", "3-Large Firms (250 Employees)"
    MULTINATIONAL = "multinational", "4-Multinational Enterprises"


class LicenseCategoryChoices(models.TextChoices):
    COMMERCIAL = "Commercial", "Commercial"
    COPYLEFT = "Copyleft", "Copyleft"
    COPYLEFT_LIMITED = "Copyleft Limited", "Copyleft Limited"
    FREE_RESTRICTED = "Free Restricted", "Free Restricted"
    PERMISSIVE = "Permissive", "Permissive"
    PROPRIETARY_FREE = "Proprietary Free", "Proprietary Free"
    PUBLIC_DOMAIN = "Public Domain", "Public Domain"
    SOURCE_AVAILABLE = "Source-available", "Source-available"
    UNSTATED_LICENSE = "Unstated License", "Unstated License"
    GRAND_TOTAL = "Grand Total", "Grand Total"


class MetricsChoices(models.TextChoices):
    ACTIVE_DEVELOPER = "active_developer", "active_developer"
    AVERAGE_DEVELOPER_ACTIVITY = (
        "average_developer_activity",
        "average_developer_activity",
    )
    AVERAGE_DEVELOPER_ACTIVITY_EVALUATION = (
        "average_developer_activity_evaluation",
        "average_developer_activity_evaluation",
    )
    BYTE_COUNT = "byte_count", "byte_count"
    COMMIT_ANALYSIS_EVALUATION = (
        "commit_analysis_evaluation",
        "commit_analysis_evaluation",
    )
    CYBER_SECURITY_DARK_WEB_BOTNET_EVALUATION = (
        "cyber_security_dark_web_botnet_evaluation",
        "cyber_security_dark_web_botnet_evaluation",
    )
    CYBER_SECURITY_EMAIL_RISK_EVALUATION = (
        "cyber_security_email_risk_evaluation",
        "cyber_security_email_risk_evaluation",
    )
    CYBER_SECURITY_EVALUATION = "cyber_security_evaluation", "cyber_security_evaluation"
    CYBER_SECURITY_LEAKED_CREDENTIALS_EVALUATION = (
        "cyber_security_leaked_credentials_evaluation",
        "cyber_security_leaked_credentials_evaluation",
    )
    CYBER_SECURITY_WEB_OR_CRED_EVALUATION = (
        "cyber_security_web_or_cred_evaluation",
        "cyber_security_web_or_cred_evaluation",
    )
    DEVELOPERS_AND_DEVELOPMENT_ACTIVITY_EVALUATION = (
        "developers_and_development_activity_evaluation",
        "developers_and_development_activity_evaluation",
    )
    DEVELOPERS_RETENTION_RATIO = (
        "developers_retention_ratio",
        "developers_retention_ratio",
    )
    GROUPS_PERCENTAGE_WITH_HIGH_RETENTION = (
        "groups_percentage_with_high_retention",
        "groups_percentage_with_high_retention",
    )
    HIGH_RISK_CVES = "high_risk_cves", "high_risk_cves"
    HIGH_RISK_IN_FILE = "high_risk_in_file", "high_risk_in_file"
    IN_FILE_HIGH_RISK_COUNT = "in_file_high_risk_count", "in_file_high_risk_count"
    IN_FILE_MEDIUM_HIGH_RISK_COUNT = (
        "in_file_medium_high_risk_count",
        "in_file_medium_high_risk_count",
    )
    IN_FILE_RISK_COUNT = "in_file_risk_count", "in_file_risk_count"
    IN_HOUSE_CURRENT_TEST_RATIO = (
        "in_house_current_test_ratio",
        "in_house_current_test_ratio",
    )
    IN_REFERENCE_RISK_COUNT = "in_reference_risk_count", "in_reference_risk_count"
    INFILE_TO_CVES_RATIO = "infile_to_cves_ratio", "infile_to_cves_ratio"
    INFILE_TO_REFERENCE_RATIO = "infile_to_reference_ratio", "infile_to_reference_ratio"
    LINES_OF_CODE = "lines_of_code", "lines_of_code"
    ORGANIZATION_COUNT = "organization_count", "organization_count"
    ORGANIZATION_COUNT_WITH_CYBER_SECURITY_EVAL = (
        "organization_count_with_cyber_security_eval",
        "organization_count_with_cyber_security_eval",
    )
    PACKAGE_MANAGER_HIGH_RISK_COUNT = (
        "package_manager_high_risk_count",
        "package_manager_high_risk_count",
    )
    PACKAGE_MANAGER_MEDIUM_HIGH_RISK_COUNT = (
        "package_manager_medium_high_risk_count",
        "package_manager_medium_high_risk_count",
    )
    PERCENTAGE_WITH_HIGH_RETENTION = (
        "percentage_with_high_retention",
        "percentage_with_high_retention",
    )
    REPOS_PERCENTAGE_WITH_HIGH_RETENTION = (
        "repos_percentage_with_high_retention",
        "repos_percentage_with_high_retention",
    )
    THIRD_PARTY_RISK_COUNT = "third_party_risk_count", "third_party_risk_count"
    TOTAL_COMMITS = "total_commits", "total_commits"
    TOTAL_REPOSITORIES = "total_repositories", "total_repositories"
    TOTAL_COMMITERS = "total_commiters", "total_commiters"


class ModuleChoices(models.TextChoices):
    # Product
    CODE_QUALITY = "Code Quality", "Code Quality"
    PROCESS = "Process", "Process"
    TEAM = "Team", "Team"
    # Compliance
    OPEN_SOURCE = "Open Source", "Open Source"
    CODE_SECURITY = "Code Security", "Code Security"
    CYBER_SECURITY = "Cyber Security", "Cyber Security"


class ModuleChoicesField(models.JSONField):
    description = _("List of module choices")

    def validate(self, value, model_instance):
        super().validate(value, model_instance)
        for item in value:
            if item not in dict(ModuleChoices.choices):
                raise exceptions.ValidationError(
                    _("%(value)s is not a valid choice."),
                    params={"value": item},
                )


class RuleConditionCodeTypeChoices(models.TextChoices):
    AI = "ai", "GenAI"
    AI_PURE = "pure", "GenAI Pure"
    AI_BLENDED = "blended", "GenAI Blended"
    HUMAN = "human", "NotGenAI"


class RepositoryFileLanguageChoices(models.TextChoices):
    ABAP = "abap", "ABAP"
    ADA = "ada", "Ada"
    ARDUINO = "arduino", "Arduino"
    ASSEMBLY = "assembly", "Assembly"
    BASH = "bash", "Bash"
    BASIC = "basic", "Basic"
    C = "c", "C"
    CPLUSPLUS = "cpp", "C++"
    CSHARP = "c_sharp", "C#"
    CLOJURE = "clojure", "Clojure"
    COBOL = "cobol", "Cobol"
    COFFEESCRIPT = "coffeeScript", "CoffeeScript"
    CSS = "css", "CSS"
    CUDA = "cuda", "Cuda"
    D = "d", "D"
    DART = "dart", "Dart"
    DELPHI = "delphi", "Delphi"
    EIFFEL = "eiffel", "Eiffel"
    ELIXIR = "elixir", "Elixir"
    ELM = "elm", "Elm"
    ERLANG = "erlang", "Erlang"
    FSHARP = "fsharp", "F#"
    FORTH = "forth", "Forth"
    FORTRAN = "fortran", "Fortran"
    GO = "go", "Go"
    GROOVY = "groovy", "Groovy"
    HASKELL = "haskell", "Haskell"
    HTML = "html", "HTML"
    JAVA = "java", "Java"
    JAVASCRIPT = "javascript", "JavaScript"
    J = "j", "J"
    JULIA = "julia", "Julia"
    JUPYTER_NOTEBOOK = "jupyter", "Jupyter Notebook"
    KOTLIN = "kotlin", "Kotlin"
    LABVIEW = "labview", "LabView"
    LISP = "lisp", "Lisp"
    LOGIC = "logic", "Logic"
    LUA = "lua", "Lua"
    MATHEMATICA = "mathematica", "Mathematica"
    MATLAB = "matlab", "Matlab"
    OCAML = "ocaml", "OCaml"
    PERL = "perl", "Perl"
    PHP = "php", "PHP"
    PROLOG = "prolog", "Prolog"
    PYTHON = "python", "Python"
    RAKU = "raku", "Raku"
    R = "r", "R"
    RUBY = "ruby", "Ruby"
    RUST = "rust", "Rust"
    SAS = "sas", "SAS"
    SCALA = "scala", "Scala"
    SCHEME = "scheme", "Scheme"
    SQL = "sql", "SQL"
    SWIFT = "swift", "Swift"
    TCL = "tcl", "TCL"
    TERRAFORM = "terraform", "Terraform"
    TSX = "tsx", "TypeScript"
    TYPESCRIPT = "typescript", "TypeScript"
    UNKNOWN = "unknown", "Unknown"
    VHDL = "vhdl", "VHDL"
    VERILOG = "verilog", "Verilog"
    WEBASSEMBLY = "asm", "WebAssembly"


class RuleConditionModeChoices(models.TextChoices):
    ALL = "all", "All"
    ANY = "any", "Any"
    NONE = "none", "None"


class RuleConditionOperatorChoices(models.TextChoices):
    GREATER_THAN = ">", "Greater than"
    GREATER_THAN_OR_EQUAL = ">=", "Greater than or Equal to"
    EQUAL = "=", "Equal to"
    LESS_THAN_OR_EQUAL = "<=", "Less than or Equal to"
    LESS_THAN = "<", "Less than"


class RuleRiskChoices(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    STRENGTH = "strength", "Strength"


class SegmentChoices(models.TextChoices):
    ENTERPRISE_LEVEL = "Enterprise-level", "Enterprise-level"
    GIANTS = "Giants", "Giants"
    GROWTH = "Growth", "Growth"
    MATURE = "Mature", "Mature"
    MID_SIZED = "Mid-sized", "Mid-sized"
    SMALL_ESTABLISHED = "Small Established", "Small Established"
    YOUNG_BIG_CODEBASE = "Young with big codebase", "Young with big codebase"
    YOUNG_SMALL_CODEBASE = "Young with small codebase", "Young with small codebase"


class ProductivityImprovementChoices(models.TextChoices):
    UNSELECTED = "unselected", "Unset"
    NEW_CODEBASE = "new_codebase", "New Codebase"
    EXISTING_CODEBASE_NEW_FEATURES = (
        "existing_codebase_new_features",
        "Existing Codebase - Primarily New Features and Functionality",
    )
    EXISTING_CODEBASE_TECH_DEBT = (
        "existing_codebase_tech_debt",
        "Existing Codebase - Primarily Tech Debt Reduction",
    )
    EXISTING_CODEBASE_BUG_FIXES = (
        "existing_codebase_bug_fixes",
        "Existing Codebase - Primarily Bug Fixes",
    )
    EXISTING_CODEBASE_PROTOTYPING = (
        "existing_codebase_prototyping",
        "Existing Codebase - Primarily Prototyping",
    )

    @classmethod
    def get_defaults(cls):
        return {
            cls.NEW_CODEBASE: 60,
            cls.EXISTING_CODEBASE_NEW_FEATURES: 50,
            cls.EXISTING_CODEBASE_TECH_DEBT: 40,
            cls.EXISTING_CODEBASE_BUG_FIXES: 30,
            cls.EXISTING_CODEBASE_PROTOTYPING: 60,
        }


class MeasureGenAIReasonChoices(models.TextChoices):
    INCREASE_ROI = (
        "increase_roi",
        "Increase the Return on Investment (ROI) of using GenAI coding tools",
    )
    LEGAL_COMPLIANCE = (
        "legal_compliance",
        "Meet Legal and/or Compliance requirements",
    )
    BOARD_INVESTOR_REQUIREMENTS = (
        "board_investor_requirements",
        "Meet Board of Director and/or future Investor/Acquirer requirements",
    )
    OTHER = "other", "Other"


class MessageIntegrationServiceChoices(models.TextChoices):
    MS_TEAMS = "teams", "Microsoft Teams"


class ReasonForMeasuringGenAIChoicesField(models.JSONField):
    description = _("List of reason for measuring Gen AI")

    def validate(self, value, model_instance):
        super().validate(value, model_instance)
        invalid_items = [item for item in value if item not in dict(MeasureGenAIReasonChoices.choices)]

        if invalid_items:
            raise exceptions.ValidationError(
                _("%(value)s are not a valid choices."),
                params={"value": invalid_items},
            )


class AttestedTimestampFieldsModel(models.Model):
    last_attested_at = models.DateTimeField(default=None, blank=True, null=True)
    last_recalculated_at = models.DateTimeField(default=None, blank=True, null=True)

    class Meta:
        abstract = True

    @property
    def needs_composition_recalculation(self):
        return self.last_attested_at and (
            not self.last_recalculated_at or self.last_recalculated_at < self.last_attested_at
        )


class CodeAICountFieldsModel(models.Model):
    code_num_lines = models.PositiveIntegerField(default=0)
    code_ai_num_lines = models.PositiveIntegerField(default=0)
    code_ai_blended_num_lines = models.PositiveIntegerField(default=0)
    code_ai_pure_num_lines = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True

    def reset_ai_fields(self):
        self.code_num_lines = 0
        self.code_ai_num_lines = 0
        self.code_ai_blended_num_lines = 0
        self.code_ai_pure_num_lines = 0


class CodeAIPercentageFieldsModel(CodeAICountFieldsModel):
    code_ai_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    code_ai_blended_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    code_ai_pure_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        abstract = True

    def reset_ai_fields(self):
        super().reset_ai_fields()
        self.code_ai_percentage = 0
        self.code_ai_blended_percentage = 0
        self.code_ai_pure_percentage = 0

    def percentage_human(self, decimals=0):
        return 100 - self.percentage_ai_overall(decimals)

    def percentage_ai_overall(self, decimals=0):
        value = round_half_up(self.code_ai_percentage, decimals)
        return int(value) if not decimals else value

    def percentage_ai_blended(self, decimals=0):
        value = round_half_up(self.code_ai_blended_percentage, decimals)
        return int(value) if not decimals else value

    def percentage_ai_pure(self, decimals=0):
        """To avoid rounding issues, ignore data on pure and force it by calculating:

        Pure = Overall - Blended
        """
        value = round_half_up(self.code_ai_percentage - self.code_ai_blended_percentage, decimals)
        return int(value) if not decimals else value


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class LanguageListFieldsModel(models.Model):
    languages = models.JSONField(default=None, blank=True, null=True)

    class Meta:
        abstract = True

    def language_list(self):
        if not self.languages:
            return []

        lang_dict = dict(RepositoryFileLanguageChoices.choices)
        languages = sorted(self.languages.items(), key=lambda x: x[1], reverse=True)

        unknown_lang = None
        sorted_languages = []
        for lang, value in languages:
            if lang == RepositoryFileLanguageChoices.UNKNOWN:
                unknown_lang = f"{lang_dict.get(lang, RepositoryFileLanguageChoices.UNKNOWN.label)}: {value}"
            else:
                sorted_languages.append(f"{lang_dict.get(lang, RepositoryFileLanguageChoices.UNKNOWN.label)}: {value}")

        if unknown_lang:
            sorted_languages.append(unknown_lang)

        return sorted_languages

    def language_list_str(self, separator=" · ", suffix=" files"):
        languages = self.language_list()
        if not languages:
            return ""

        return f"{suffix}{separator}".join(languages) + suffix


class AppComponentVersion(TimestampedModel):
    component = models.CharField(max_length=50, choices=AppComponentChoices.choices)
    version = models.PositiveIntegerField()

    class Meta:
        unique_together = ["component", "version"]


class Geography(PublicIdMixin, MP_Node, TimestampedModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=100)

    class Meta:
        verbose_name_plural = "geographies"

    def __str__(self):
        return self.name

    def get_full_path(self):
        if self.get_parent() is None:
            return self.code
        return f"{self.get_parent().get_full_path()}/{self.code}"

    @classmethod
    def get_sorted_geographies(cls):
        return (
            cls.objects.filter(depth=2)
            .annotate(
                custom_order=Case(
                    When(name="Global", then=Value(0)),
                    When(name="United States", then=Value(1)),
                    When(name="Canada", then=Value(2)),
                    When(name="European Union", then=Value(3)),
                    default=Value(4),
                    output_field=models.IntegerField(),
                )
            )
            .order_by("custom_order", "name")
        )


class Industry(PublicIdMixin, TimestampedModel):
    # Label to display for not set industry
    LABEL_NONE = "Other (we’ll follow up with you)"  # noqa: RUF001

    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "industries"

    def num_organizations(self):
        return self.organization_set.count()

    def __str__(self):
        return self.name


class Organization(PublicIdMixin, SoftDeleteModel, TimestampedModel):
    created_by = models.ForeignKey(
        "CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_organizations",
    )
    name = models.CharField(max_length=100)
    industry = models.ForeignKey(Industry, on_delete=models.SET_NULL, default=None, blank=True, null=True)
    avg_developer_cost = models.PositiveIntegerField(
        verbose_name="Average developer yearly cost (including benefits), in $US",
        default=100000,
    )
    num_developers = models.PositiveIntegerField(verbose_name="Number of current developers", default=10)
    all_time_developers = models.PositiveIntegerField(verbose_name="Number of all time developers", default=10)
    num_code_lines = models.PositiveIntegerField(
        verbose_name="Number of lines of code", default=1000, blank=True, null=True
    )
    first_commit_date = models.DateField(
        verbose_name="Date of the first commit",
        default=datetime.strptime("2020-01-01", "%Y-%m-%d").date(),
    )
    geographies = models.ManyToManyField(Geography)
    first_analysis_done = models.BooleanField(default=False)
    first_email_sent = models.BooleanField(default=False, help_text="first analysis started email sent")
    connection_issued_by = models.ForeignKey(
        "CustomUser", default=None, blank=True, null=True, on_delete=models.SET_NULL
    )
    analysis_max_scans = models.PositiveIntegerField(default=None, blank=True, null=True)
    analysis_max_repositories = models.PositiveIntegerField(default=None, blank=True, null=True)
    analysis_max_lines_per_repository = models.PositiveIntegerField(default=None, blank=True, null=True)
    analysis_historic_enabled = models.BooleanField(default=True, help_text="Download commits before connection date")
    status_check_enabled = models.BooleanField(
        default=False,
        help_text="Enables status check in PRs feature",
    )
    status_check_mark_as_failed = models.BooleanField(
        default=False,
        help_text="Mark status check as failed if the GenAI rules are not met",
    )
    is_software_company = models.BooleanField(
        default=False,
        help_text="Is your organization a software company?",
    )
    reasons_for_measuring_genai = ReasonForMeasuringGenAIChoicesField(default=list, blank=True, null=True)
    avg_dev_annual_work_hours = models.PositiveIntegerField(
        default=1500, help_text="Average hours worked by a developer annually"
    )
    require_mfa = models.BooleanField(default=False, help_text="Require MFA for all users in this organization")

    tools_genai_monthly_cost = models.PositiveIntegerField(
        default=None,
        blank=True,
        null=True,
        verbose_name="Monthly Cost of GenAI Tool(s) per Developer",
    )

    onboarding_completed = models.BooleanField(default=False)
    contextualization_enabled = models.BooleanField(
        default=False,
        help_text=("Indicates if the contextualization script is to be run for this organization"),
    )

    marked_for_deletion = models.BooleanField(
        default=False,
        help_text="Marks the organization for deletion before the nightly scan",
    )

    @property
    def industry_name(self):
        return Industry.LABEL_NONE if not self.industry else str(self.industry)

    def all_industries(self):
        return not self.industry

    def compliance_standards(self):
        query = ComplianceStandard.objects.all()
        if not self.all_industries():
            query = query.filter(Q(industries=self.industry) | Q(industries=None))
        if self.geographies and not self.geographies.filter(name="All").exists():
            query = query.filter(Q(geographies__in=self.geographies.all()) | Q(geographies__name="All"))

        return query.distinct()

    def all_repos_analyzed(self):
        for repository in self.repository_set.all():
            try:
                last_commit = RepositoryCommit.objects.get(repository=repository, sha=repository.last_commit_sha)
                if last_commit.status != RepositoryCommitStatusChoices.ANALYZED:
                    return False
            except RepositoryCommit.DoesNotExist:
                return False

        return True

    def is_all_geographies(self):
        return self.geographies.filter(name="All").exists() or not self.geographies.exists()

    def rule_set_non_global(self):
        return self.rule_set.filter(apply_organization=False).order_by("name")

    def set_default_flags(self):
        self.status_check_enabled = settings.DEFAULT_FLAG_STATUS_CHECK_ENABLED
        self.contextualization_enabled = settings.DEFAULT_FLAG_CONTEXTUALIZATION_ENABLED

    def set_default_limits(self):
        self.analysis_max_scans = settings.DEFAULT_LIMIT_SCANS
        self.analysis_max_repositories = settings.DEFAULT_LIMIT_REPOSITORIES
        self.analysis_max_lines_per_repository = settings.DEFAULT_LIMIT_LINES_PER_REPOSITORY

    def copy_preset_rules(self):
        preset_rules = Rule.objects.filter(is_preset=True).prefetch_related("conditions")
        for rule in preset_rules:
            new_rule = rule
            new_rule.pk = None
            new_rule.is_preset = False
            new_rule.organization = self
            new_rule.save()

            for condition in rule.conditions.all():
                new_condition = condition
                new_condition.pk = None
                new_condition.rule = new_rule
                new_condition.save()

    def analysis_limits(self):
        limits = {}
        fields = [
            "analysis_max_scans",
            "analysis_max_repositories",
            "analysis_max_lines_per_repository",
        ]
        for field in fields:
            limit = getattr(self, field)
            if limit:
                key = field.replace("analysis_max_", "")
                limits[key] = limit

        return limits

    def get_download_directory(self, is_pull_request=False):
        base_dir = settings.AI_CODE_PR_DIRECTORY if is_pull_request else settings.AI_CODE_REPOSITORY_DIRECTORY
        return os.path.abspath(os.path.join(base_dir, self.public_id()))

    def get_first_commit_date(self, force_update_cache=False) -> datetime | None:
        cache_key = f"org_first_commit_date_{self.pk}"

        if not force_update_cache:
            first_commit_date = cache.get(cache_key)
            if first_commit_date:
                return first_commit_date

        first_commit_date = RepositoryCommit.objects.filter(
            repository__organization=self,
            status=RepositoryCommitStatusChoices.ANALYZED,
            pull_requests__isnull=True,
        ).aggregate(Min("date_time"))["date_time__min"]

        if first_commit_date:
            first_commit_date = first_commit_date.date()
            cache.set(cache_key, first_commit_date, timeout=60 * 60 * 24 * 30)

        return first_commit_date

    def get_last_commit_timestamp(self) -> int | None:
        last_commit = (
            RepositoryCommit.objects.filter(
                repository__organization=self,
                status=RepositoryCommitStatusChoices.ANALYZED,
                pull_requests__isnull=True,
            )
            .order_by("-date_time")
            .values("date_time")
            .first()
        )

        return int(last_commit["date_time"].timestamp()) if last_commit else None

    def get_connection_list(self):
        # TODO: reset after changing connections
        cache_key = f"org_connection_list_{self.pk}"

        return cache.get_or_set(
            cache_key,
            lambda: list(
                DataProviderConnection.objects.filter(organization=self, data__isnull=False)
                .prefetch_related("provider")
                .values_list("provider__name", flat=True)
                .all()
            ),
            60 * 60 * 24,
        )

    def get_reasons_for_measuring_genai(self):
        if not self.reasons_for_measuring_genai:
            return []

        reasons_for_measuring_genai_dict = dict(MeasureGenAIReasonChoices.choices)
        return [reasons_for_measuring_genai_dict[module] for module in self.reasons_for_measuring_genai]

    def get_attested_num_lines(self):
        last_commit_shas = self.repository_set.values_list("last_commit_sha", flat=True)
        return sum(
            RepositoryFileChunk.objects.filter(file__commit__sha__in=last_commit_shas, attestation__isnull=False)
            .distinct()
            .values_list("code_num_lines", flat=True)
        )

    def get_code_num_lines(self):
        return sum(self.repository_set.values_list("code_num_lines", flat=True))

    def __str__(self):
        return self.name


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The email is empty")

        user = self.model(email=self.normalize_email(email), **extra_fields)

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(email, password, **extra_fields)


class PasswordHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    password = models.CharField(max_length=128)
    timestamp = models.DateTimeField(auto_now_add=True)


class CustomUser(TimestampedModel, PublicIdMixin, AbstractUser):
    username = None
    email = models.EmailField(unique=True)

    initials = models.CharField(max_length=3, blank=True, null=True)

    profile_image = models.ImageField(
        upload_to="profile_images",
        storage=get_s3_storage,
        blank=True,
        null=True,
    )
    profile_image_thumbnail = ProcessedImageField(
        processors=[ResizeToFill(150, 150)],
        options={"quality": 60},
        upload_to="profile_images",
        storage=get_s3_storage,
        blank=True,
        null=True,
    )

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    organizations = models.ManyToManyField(Organization, blank=True)

    company_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text=(
            "Collected at sign up. If None then user signed up before this field was added or the user was invited."
        ),
    )
    company_number_of_developers = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Collected at sign up. If None then user signed up before this field was added or the user was invited."
        ),
    )

    # Due to SOC2 compliance, this must be false by default
    consent_marketing_notifications = models.BooleanField(
        default=False,
        help_text="Whether or not the user consented to receive marketing notifications. This is necessary for SOC2 compliance. Do not change this without the user's consent.",
    )

    compass_anomaly_insights_notifications = models.BooleanField(
        default=False,
        help_text=("Indicates if the user has opted in to receive anomaly insights notifications from Compass."),
    )
    compass_summary_insights_notifications = models.BooleanField(
        default=False,
        help_text=("Indicates if the user has opted in to receive summary insights notifications from Compass."),
    )
    hide_environment_banner = models.BooleanField(default=False)

    @staticmethod
    def generate_initials_from_names(first_name, last_name):
        """By default, use the first letter of the first name and last name.

        If the last name contains multiple words, use the first letter
        of the first two words, producing either 2 or 3 letters total.
        """
        last_name_parts = last_name.split()

        if len(last_name_parts) == 1:
            return f"{first_name[:1]}{last_name[:1]}".upper()
        last_initials = "".join(word[0] for word in last_name_parts[:2])
        return f"{first_name[:1]}{last_initials}".upper()

    def role(self):
        # make sure we make use of prefetched data
        groups = self.groups.all()
        return groups[0] if groups else None

    def is_owner(self):
        return self.role().name == OrgRole.OWNER

    def set_password(self, raw_password):
        if self.pk and self.check_password_history(raw_password):
            raise ValueError("You cannot reuse a previous password.")

        super().set_password(raw_password)

    def check_password_history(self, raw_password):
        password_history = PasswordHistory.objects.filter(user=self).values_list("password", flat=True)
        return any(check_password(raw_password, password) for password in password_history)

    def has_organizations(self):
        return self.organizations.exists()

    @transaction.atomic
    def remove_from_organization(self, organization):
        self.organizations.remove(organization)
        if self.is_active and not self.has_organizations():
            self.is_active = False
            self.save()

    @transaction.atomic
    def save(self, *args, **kwargs):
        # If the user is new, or password has changed, save the password history
        save_password = not self.pk or self.password != CustomUser.objects.get(pk=self.pk).password

        if self.email:
            self.email = self.email.lower()

        super().save(*args, **kwargs)
        if save_password:
            self.save_password_history()

    def save_password_history(self):
        PasswordHistory.objects.create(user=self, password=self.password)

        password_history = PasswordHistory.objects.filter(user=self).order_by("-timestamp")
        if password_history.count() > settings.PASSWORD_HISTORY_MAX_COUNT:
            ids_to_delete = password_history[settings.PASSWORD_HISTORY_MAX_COUNT :].values_list("id", flat=True)

            PasswordHistory.objects.filter(id__in=ids_to_delete).delete()


class UserInvitation(SoftDeleteModel, PublicIdMixin, TimestampedModel):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    role = models.ForeignKey(Group, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    sent_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    resent_at = models.DateTimeField(default=None, blank=True, null=True)

    # display all objects in admin
    # source: https://github.com/san4ezy/django_softdelete/issues/8
    global_objects = models.Manager()

    @admin.display(boolean=True)
    def is_expired(self):
        # TODO: expire invitations after X days
        return False

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)


class Rule(PublicIdMixin, TimestampedModel):
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=100, default=None, blank=True, null=True)
    condition_mode = models.CharField(max_length=100, choices=RuleConditionModeChoices.choices)
    risk = models.CharField(max_length=100, choices=RuleRiskChoices.choices)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, default=None, blank=True, null=True)
    apply_organization = models.BooleanField(
        default=False,
        verbose_name="Apply at organization level",
        help_text="This rule will apply to the whole organization, including all repository groups and developer groups.",
    )
    is_preset = models.BooleanField(
        default=False,
        help_text="Preset rule by Sema. This rule will be copied to new organizations when created.",
    )

    class Meta:
        unique_together = ["name", "organization"]

    def clean(self):
        if self.is_preset and self.is_custom():
            raise exceptions.ValidationError("Preset rules can't belong to any organization.")
        if self.is_preset and self.apply_organization:
            raise exceptions.ValidationError("Preset rules can't apply to an organization.")
        if self.apply_organization and not self.is_custom():
            raise exceptions.ValidationError(
                "A rule can't apply to an organization if it doesn't belong to an organization."
            )

    def save(self, *args, **kwargs):
        # rules that apply to the whole organization can't be related to groups
        # preset rules can't be related to groups (that may happen if someone changes a non-preset rule to preset)
        if self.pk and (self.apply_organization or self.is_preset):
            self.authorgroup_set.clear()
            self.repositorygroup_set.clear()

        super().save(*args, **kwargs)

    @admin.display(boolean=True)
    def is_custom(self):
        return self.organization_id is not None

    def rule_str(self):
        condition_mode = self.get_condition_mode_display()
        risk = self.get_risk_display()
        if self.risk != RuleRiskChoices.STRENGTH:
            risk += " Risk"
        return f"IF {condition_mode} condition(s) apply THEN {risk}"

    def author_group_list(self):
        # Use pre-fetched data, avoid N+1 queries
        groups = self.authorgroup_set.all()
        return sorted(groups, key=lambda r: r.name)

    def repository_group_list(self):
        # Use pre-fetched data, avoid N+1 queries
        groups = self.repositorygroup_set.all()
        return sorted(groups, key=lambda r: r.name)

    def used_in_groups(self):
        # Use pre-fetched data, avoid N+1 queries
        return self.authorgroup_set.all() or self.repositorygroup_set.all()

    def __str__(self):
        return self.name + (" (Preset)" if self.is_preset else "")


class RuleCondition(PublicIdMixin, TimestampedModel):
    rule = models.ForeignKey(Rule, on_delete=models.CASCADE, related_name="conditions")
    code_type = models.CharField(max_length=100, choices=RuleConditionCodeTypeChoices.choices)
    operator = models.CharField(max_length=100, choices=RuleConditionOperatorChoices.choices)
    percentage = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])

    def __str__(self):
        code_type = self.get_code_type_display()
        return f"{code_type} {self.operator} {self.percentage}%"


class ComplianceStandardAIUsage(TimestampedModel):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class ComplianceStandard(TimestampedModel):
    external_id = models.CharField(max_length=100, help_text="Unique ID", blank=True, null=True)
    name = models.TextField()
    risk_level = models.CharField(max_length=30, choices=ComplianceStandardRiskLevelChoices.choices)
    geographies = models.ManyToManyField(Geography)
    ai_usage = models.ManyToManyField(ComplianceStandardAIUsage, blank=True)
    industries = models.ManyToManyField(Industry)
    remediation_mitigation = models.TextField(verbose_name="Remediation/Mitigation", blank=True, null=True)
    status = models.CharField(max_length=30, choices=ComplianceStandardStatusChoices.choices)
    source = models.CharField(max_length=30, choices=ComplianceStandardSourceChoices.choices)
    risk_type = models.CharField(max_length=30, choices=ComplianceStandardRiskTypeChoices.choices)
    sema_source = models.CharField(max_length=100)
    third_party_source_unique_id = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    policy_instrument_type_oecd = models.CharField(max_length=100, blank=True, null=True)
    organization_size_oecd = models.CharField(
        max_length=100,
        choices=ComplianceStandardOrganizationSizeChoices.choices,
        blank=True,
        null=True,
    )
    is_excluded = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class ComplianceStandardReference(TimestampedModel):
    standard = models.ForeignKey(ComplianceStandard, on_delete=models.CASCADE, related_name="references")
    text = models.CharField(max_length=100, null=True, blank=True, default=None)
    url = models.URLField(null=True, blank=True, default=None)

    def __str__(self):
        return self.text or self.url

    class Meta:
        constraints = [
            # constraint to ensure either text or url is set
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_text_or_url",
                check=(models.Q(url__isnull=False) | models.Q(text__isnull=False)),
            )
        ]


class ComplianceStandardComponent(TimestampedModel):
    standard = models.ForeignKey(ComplianceStandard, on_delete=models.CASCADE, related_name="components")
    name = models.CharField(max_length=100)
    description = models.TextField()
    ai_types = AITypeChoicesField(default=list)

    rules = models.ManyToManyField(
        Rule,
        related_name="compliance_standard_rules",
        blank=True,
    )

    class Meta:
        unique_together = ["standard", "name"]

    def get_ai_types_list(self):
        ai_type_dict = dict(AITypeChoices.choices)
        return [ai_type_dict[ai_type] for ai_type in self.ai_types]

    def __str__(self):
        return f"{self.name}: {self.description}"


class DataProvider(TimestampedModel):
    name = models.CharField(max_length=100, unique=True)
    modules = ModuleChoicesField(default=list)

    def get_modules_list(self):
        module_dict = dict(ModuleChoices.choices)
        return [module_dict[module] for module in self.modules]

    def __str__(self):
        return self.name


class DataProviderConnection(TimestampedModel):
    provider = models.ForeignKey(DataProvider, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    data = models.JSONField(default=None, blank=True, null=True)
    last_fetched_at = models.DateTimeField(default=None, blank=True, null=True)
    connected_by = models.ForeignKey(CustomUser, default=None, blank=True, null=True, on_delete=models.SET_NULL)
    connected_at = models.DateTimeField(default=None, blank=True, null=True)

    class Meta:
        unique_together = ["organization", "provider"]

    @admin.display(boolean=True)
    def is_connected(self):
        # Importing here to avoid circular imports
        from mvp.services import ConnectedIntegrationsService

        return ConnectedIntegrationsService.is_connection_connected(self)


class DataProviderField(TimestampedModel):
    provider = models.ForeignKey(DataProvider, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    description = models.TextField(max_length=500, default=None, blank=True, null=True)

    def __str__(self):
        return self.name


class DataProviderProject(TimestampedModel):
    provider = models.ForeignKey(DataProvider, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    external_id = models.CharField(max_length=100)
    meta = models.JSONField(default=None, blank=True, null=True)

    class Meta:
        unique_together = ["organization", "provider", "external_id"]

    def __str__(self):
        return self.name


class DataProviderRecord(TimestampedModel):
    project = models.ForeignKey(DataProviderProject, on_delete=models.CASCADE)
    field = models.ForeignKey(DataProviderField, on_delete=models.CASCADE)
    value = models.IntegerField()  # TODO: should we use Decimal?
    date_time = models.DateTimeField()

    def __str__(self):
        return str(f"{self.field}: {self.value} - {self.date_time}")


class DataProviderMember(TimestampedModel):
    provider = models.ForeignKey(DataProvider, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    external_id = models.CharField(max_length=100)
    meta = models.JSONField(default=None, blank=True, null=True)

    class Meta:
        unique_together = ["organization", "provider", "external_id"]

    def __str__(self):
        return self.name


class DataProviderMemberProjectRecord(TimestampedModel):
    member = models.ForeignKey(DataProviderMember, on_delete=models.CASCADE)
    project = models.ForeignKey(DataProviderProject, on_delete=models.CASCADE)
    field = models.ForeignKey(DataProviderField, on_delete=models.CASCADE)
    value = models.IntegerField()  # TODO: should we use Decimal?
    date_time = models.DateTimeField()

    def __str__(self):
        return str(f"{self.field}: {self.value} - {self.date_time}")


class License(TimestampedModel):
    slug = models.CharField(max_length=100, unique=True)
    short_name = models.CharField(max_length=100, unique=True)
    spdx = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=30, choices=LicenseCategoryChoices.choices)


class ReferenceMetric(models.Model):
    metric = models.CharField(max_length=100, choices=MetricsChoices.choices)
    percentile = models.PositiveIntegerField(default=None, blank=True, null=True)
    segment = models.CharField(max_length=30, choices=SegmentChoices.choices)
    value = models.DecimalField(
        max_digits=24,
        decimal_places=12,
        default=Decimal("0.00"),
    )

    class Meta:
        unique_together = ["metric", "percentile", "segment"]

    def __str__(self):
        percentile = f"{self.percentile}th" if self.percentile is not None else "no"
        return f"{self.metric} ({percentile} percentile) - {self.segment}: {self.value}"


class ReferenceRecord(TimestampedModel):
    org_id = models.PositiveIntegerField(unique=True)
    org_name = models.CharField(max_length=100)
    segment = models.CharField(max_length=30, choices=SegmentChoices.choices)
    code_low_risk = models.PositiveIntegerField(default=0)
    code_medium_risk = models.PositiveIntegerField(default=0)
    code_high_risk = models.PositiveIntegerField(default=0)
    commit_change_rate = models.IntegerField(default=0)
    development_activity_change_rate = models.IntegerField(default=0)
    open_source_medium_high_file_count = models.PositiveIntegerField(default=0)
    open_source_medium_high_package_count = models.PositiveIntegerField(default=0)
    cve_high_risk = models.PositiveIntegerField(default=0)
    cyber_security_high_risk = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.org_name


class ScoreRecord(TimestampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    date_time = models.DateTimeField()
    compliance_score = models.PositiveIntegerField(
        default=None,
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    product_score = models.PositiveIntegerField(
        default=None,
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    sema_score = models.PositiveIntegerField(
        default=None,
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )


class RepositoryGroup(PublicIdMixin, CodeAIPercentageFieldsModel, TimestampedModel):
    name = models.CharField(max_length=255)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    usage_category = models.CharField(max_length=20, choices=RepositoryGroupCategoryChoices.choices)
    rules = models.ManyToManyField(Rule, blank=True)

    not_evaluated_num_files = models.PositiveIntegerField(default=0)
    not_evaluated_num_lines = models.PositiveIntegerField(default=0)

    time_spent_coding_percentage = models.IntegerField(
        default=30,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Estimated % of time spent coding",
    )

    potential_productivity_improvement_label = models.CharField(
        max_length=100,
        choices=ProductivityImprovementChoices.choices,
        default=ProductivityImprovementChoices.UNSELECTED,
    )

    potential_productivity_improvement_percentage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Estimated % of potential productivity improvement",
    )

    max_genai_code_usage_percentage = models.IntegerField(
        default=20,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Maximum GenAI Code Usage",
    )

    num_developers = models.PositiveIntegerField(verbose_name="Number of developers", null=True, blank=True)

    class Meta:
        unique_together = ["name", "organization"]

    @property
    def roi_enabled(self):
        return (
            self.potential_productivity_improvement_label is not None
            and self.potential_productivity_improvement_label != ProductivityImprovementChoices.UNSELECTED
            and self.num_developers is not None
        )

    def repository_list(self):
        # Use pre-fetched data, avoid N+1 queries
        repositories = self.repositories.all()
        return sorted(repositories, key=lambda r: (r.owner, r.name))

    def rule_ids(self):
        # Use pre-fetched data, avoid N+1 queries
        return [rule.id for rule in self.rules.all()]

    def rule_list(self):
        # Use pre-fetched data, avoid N+1 queries
        rules = self.rules.all()
        return sorted(rules, key=lambda r: r.name)

    def get_attested_num_lines(self, num_lines_by_sha=None):
        """Get the number of attested lines of code for the repository group.

        Note: If num_lines_by_sha is not supplied then it'll be calculated from the database.
        Calculating from the db might cause N+1 queries
        """
        # done this way because repository_set is prefetched
        last_commit_shas = [repo.last_commit_sha for repo in self.repositories.all()]
        if num_lines_by_sha is not None:
            attested_num_lines = sum([num_lines_by_sha.get(sha, 0) for sha in last_commit_shas])
        else:
            attested_num_lines = sum(
                RepositoryFileChunk.objects.filter(file__commit__sha__in=last_commit_shas, attestation__isnull=False)
                .distinct()
                .values_list("code_num_lines", flat=True)
            )
        return attested_num_lines

    def __str__(self):
        return self.name


class Repository(
    PublicIdMixin,
    DecodePublicIdMixin,
    CodeAIPercentageFieldsModel,
    TimestampedModel,
    LanguageListFieldsModel,
):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)  # this is our customer
    provider = models.ForeignKey(DataProvider, on_delete=models.CASCADE)
    external_id = models.CharField(max_length=100)
    owner = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    last_commit_sha = models.CharField(max_length=40, default=None, blank=True, null=True)
    last_analysis_file = models.TextField(default=None, blank=True, null=True)
    last_analysis_num_files = models.PositiveIntegerField(default=0)
    not_evaluated_num_files = models.PositiveIntegerField(default=0)
    not_evaluated_num_lines = models.PositiveIntegerField(default=0)
    external_data = models.JSONField(default=None, blank=True, null=True)
    repository_group = models.ManyToManyField(RepositoryGroup, blank=True, related_name="repositories")

    analysis_historic_done = models.BooleanField(default=False)
    default_branch_name = models.CharField(max_length=250, default=None, blank=True, null=True)

    class Meta:
        unique_together = ["organization", "provider", "external_id"]
        verbose_name_plural = "repositories"

    def full_name(self):
        return f"{self.owner}/{self.name}"

    def has_pending_commits(self, exclude_prs=False, cutoff_date=None):
        qs = self.repositorycommit_set.filter(status=RepositoryCommitStatusChoices.PENDING)

        if exclude_prs:
            qs = qs.filter(pull_requests__isnull=True)

        if cutoff_date:
            qs = qs.filter(date_time__gte=cutoff_date)

        return qs.exists()

    def last_analysis_folder(self):
        return self.last_analysis_file[:-4] if self.last_analysis_file else None

    def total_num_lines(self):
        return self.code_num_lines + self.not_evaluated_num_lines

    def get_download_directory(self, is_pull_request=False):
        org_dir = self.organization.get_download_directory(is_pull_request)
        return os.path.join(org_dir, self.public_id())

    def is_manual_imported(self):
        return self.external_data and self.external_data.get("manual", False)

    def get_attested_num_lines(self, num_lines_by_sha=None):
        """Get the number of attested lines of code for the repository.

        Note: If num_lines_by_sha is not supplied then it'll be calculated from the database.
        calculating from the db might cause N+1 queries
        """
        if num_lines_by_sha is not None:
            attested_num_lines = num_lines_by_sha.get(self.last_commit_sha, 0)
        else:
            attested_num_lines = sum(
                RepositoryFileChunk.objects.filter(file__commit__sha=self.last_commit_sha, attestation__isnull=False)
                .distinct()
                .values_list("code_num_lines", flat=True)
            )
        return attested_num_lines

    @classmethod
    def get_prefetch_commit_before_date(cls, date, attr="until_commit", lte=True):
        date = date or datetime.now(UTC)
        filter_arg = "lte" if lte else "lt"

        qs = RepositoryCommit.objects.filter(
            status=RepositoryCommitStatusChoices.ANALYZED,
            **{f"date_time__{filter_arg}": date},
            pull_requests__isnull=True,
        ).order_by("-date_time")[:1]

        return Prefetch("repositorycommit_set", queryset=qs, to_attr=attr)

    @classmethod
    def get_attested_num_of_lines_by_sha(cls, repositories: [Self]) -> dict[str, int]:
        """Get the number of attested lines of code for the repositories as a dictionary of sha to num_lines."""
        commit_shas = {repo.last_commit_sha for repo in repositories}
        commit_shas |= {
            repo.until_commit[-1].sha
            for repo in repositories
            if hasattr(repo, "until_commit") and repo.until_commit and hasattr(repo.until_commit[-1], "sha")
        }

        attested_chunks = (
            RepositoryFileChunk.objects.filter(
                file__commit__sha__in=commit_shas,
                attestation__isnull=False,
            )
            .distinct()
            .values_list("file__commit__sha", "code_num_lines")
        )

        num_lines_by_sha = defaultdict(int)
        for sha, num_lines in attested_chunks:
            num_lines_by_sha[sha] += num_lines

        return num_lines_by_sha

    def __str__(self):
        return self.name


class RepositoryPullRequest(AttestedTimestampFieldsModel, CodeAIPercentageFieldsModel, TimestampedModel):
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)
    pr_number = models.PositiveIntegerField()
    base_commit_sha = models.CharField(max_length=40)
    head_commit_sha = models.CharField(max_length=40)

    analysis_num_files = models.PositiveIntegerField(default=0)
    not_evaluated_num_files = models.PositiveIntegerField(default=0)
    not_evaluated_num_lines = models.PositiveIntegerField(default=0)

    is_closed = models.BooleanField(default=False)

    class Meta:
        unique_together = ["repository", "pr_number"]

    def base_commit(self):
        try:
            return RepositoryCommit.objects.get(repository=self.repository, sha=self.base_commit_sha)
        except RepositoryCommit.DoesNotExist:
            return None

    def head_commit(self):
        try:
            return RepositoryCommit.objects.get(repository=self.repository, sha=self.head_commit_sha)
        except RepositoryCommit.DoesNotExist:
            return None

    def head_commit_status(self):
        head_commit = self.head_commit()
        return head_commit.status if head_commit else None

    def __str__(self):
        return f"{self.pk} - PR({self.pr_number})"


class RepositoryPullRequestStatusCheck(TimestampedModel):
    pull_request = models.ForeignKey(RepositoryPullRequest, on_delete=models.CASCADE)
    status_check_id = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=100)
    message = models.TextField(default=None, blank=True, null=True, help_text="The markdown message")
    external_data = models.JSONField(default=dict, blank=True, null=True)


class RepositoryCommit(
    AttestedTimestampFieldsModel,
    CodeAIPercentageFieldsModel,
    TimestampedModel,
    LanguageListFieldsModel,
):
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)
    sha = models.CharField(max_length=40)
    date_time = models.DateTimeField()

    analysis_file = models.TextField(default=None, blank=True, null=True)
    analysis_metadata = models.JSONField(default=None, blank=True, null=True)
    analysis_num_files = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=RepositoryCommitStatusChoices.choices,
        default=RepositoryCommitStatusChoices.PENDING,
    )
    not_evaluated_num_files = models.PositiveIntegerField(default=0)
    not_evaluated_num_lines = models.PositiveIntegerField(default=0)

    shredded = models.BooleanField(default=False, help_text="Whether the source code has been shredded")

    """
        Two PRs can be associated with the same commit
        Example:
            - Create a branch feature with commit ABC
            - Create PR 1 from branch feature to main
            - PR1 is associated to commit ABC
            - Close the PR 1
            - Create PR 2 from branch feature to main
            - PR2 is associated to commit ABC as well
    """
    pull_requests = models.ManyToManyField(RepositoryPullRequest, blank=True)

    class Meta:
        unique_together = ["repository", "sha"]

    @property
    def is_analyzed(self):
        return self.status == RepositoryCommitStatusChoices.ANALYZED

    @admin.display(boolean=True)
    def is_pull_request(self):
        # NOTE: this will fail if the folder changes, but we avoid N+1 queries
        return self.analysis_file is not None and os.path.abspath(settings.AI_CODE_PR_DIRECTORY) in self.analysis_file

    def analysis_folder(self):
        return self.analysis_file[:-4] if self.analysis_file else None

    def metadata_file(self):
        folder_path = self.analysis_folder()
        return os.path.join(folder_path, "metadata.json") if folder_path else None

    def metadata_analysis_file(self):
        return f"{self.analysis_folder()}.analysis_metadata.json"

    def reset(self):
        self.reset_ai_fields()
        self.analysis_num_files = 0
        self.not_evaluated_num_files = 0
        self.not_evaluated_num_lines = 0

    def total_num_lines(self):
        return self.code_num_lines + self.not_evaluated_num_lines

    def get_download_directory(self, is_pull_request=False):
        repo_dir = str(self.repository.get_download_directory(is_pull_request))
        return os.path.join(repo_dir, self.sha)

    def get_attested_num_lines(self, num_lines_by_sha=None):
        """Get the number of attested lines of code for the commit.

        Note: If num_lines_by_sha is not supplied then it'll be calculated from the database.
        calculating from the db might cause N+1 queries
        """
        if num_lines_by_sha is not None:
            attested_num_lines = num_lines_by_sha.get(self.sha, 0)
        else:
            attested_num_lines = sum(
                RepositoryFileChunk.objects.filter(file__commit=self, attestation__isnull=False)
                .distinct()
                .values_list("code_num_lines", flat=True)
            )
        return attested_num_lines

    def __str__(self):
        return self.sha


class RepositoryFile(
    PublicIdMixin,
    AttestedTimestampFieldsModel,
    CodeAICountFieldsModel,
    TimestampedModel,
):
    commit = models.ForeignKey(RepositoryCommit, on_delete=models.CASCADE)
    file_path = models.CharField(max_length=500)
    language = models.CharField(
        max_length=12,
        choices=RepositoryFileLanguageChoices.choices,
        default=None,
        blank=True,
        null=True,
    )
    not_evaluated = models.BooleanField(default=False)

    chunks_ai_blended = models.PositiveIntegerField(default=0)
    chunks_ai_pure = models.PositiveIntegerField(default=0)
    chunks_human = models.PositiveIntegerField(default=0)
    chunks_not_evaluated = models.PositiveIntegerField(default=0)
    chunks_attested = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ["commit", "file_path"]
        indexes = [
            models.Index(fields=["not_evaluated", "file_path"]),
        ]

    @property
    def relative_path(self):
        return self.file_path.lstrip("/")

    def chunk_list(self):
        # Use pre-fetched data, avoid N+1 queries
        chunks = self.repositoryfilechunk_set.all()
        return sorted(chunks, key=lambda r: r.code_line_start)

    def reset_ai_fields(self):
        super().reset_ai_fields()
        self.chunks_ai_blended = 0
        self.chunks_ai_pure = 0
        self.chunks_human = 0

    def __str__(self):
        return self.file_path


class RepositoryCodeAttestation(PublicIdMixin, TimestampedModel):
    # Attestation is done at the repository level because the same chunk could be found in multiple files
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)
    code_hash = models.CharField(max_length=64)
    label = models.CharField(
        max_length=20,
        choices=CodeGenerationLabelChoices.choices,
    )
    comment = models.TextField(default=None, blank=True, null=True)
    attested_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, default=None, blank=True, null=True)

    class Meta:
        unique_together = ["repository", "code_hash"]


class RepositoryFileChunk(PublicIdMixin, TimestampedModel):
    file = models.ForeignKey(RepositoryFile, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    code_hash = models.CharField(max_length=64, default=None, blank=True, null=True, db_index=True)
    code_line_start = models.PositiveIntegerField(default=0)
    code_line_end = models.PositiveIntegerField(default=0)
    code_num_lines = models.PositiveIntegerField(default=0)
    code_ai_num_lines = models.PositiveIntegerField(default=0)
    code_generation_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    code_generation_label = models.CharField(
        max_length=20,
        choices=CodeGenerationLabelChoices.choices,
        default=None,
        blank=True,
        null=True,
    )
    code_generation_model_label = models.CharField(
        max_length=20,
        choices=CodeGenerationLabelChoices.choices,
        default=None,
        blank=True,
        null=True,
    )
    attestation = models.ForeignKey(
        RepositoryCodeAttestation,
        on_delete=models.SET_NULL,
        default=None,
        blank=True,
        null=True,
    )

    @property
    def is_labeled_human(self):
        # NOTE: this doesn't take into account attestation override
        return self.code_generation_label == CodeGenerationLabelChoices.HUMAN

    @property
    def is_not_evaluated(self):
        return self.code_generation_label == CodeGenerationLabelChoices.NOT_EVALUATED

    def get_label(self):
        return self.attestation.label if self.attestation else self.code_generation_label

    def __str__(self):
        return f"{self.name}:{self.code_hash}"


class AuthorGroup(PublicIdMixin, CodeAIPercentageFieldsModel, TimestampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    team_type = models.CharField(
        max_length=255,
        default=None,
        blank=True,
        null=True,
        help_text="e.g. Inhouse, Offshore",
    )
    developer_type = models.CharField(
        max_length=255,
        default=None,
        blank=True,
        null=True,
        help_text="e.g. Junior, Senior",
    )
    rules = models.ManyToManyField(Rule, blank=True)

    class Meta:
        unique_together = ["organization", "name"]

    def author_list(self):
        # Use pre-fetched data, avoid N+1 queries
        authors = self.author_set.all()
        return sorted(authors, key=lambda r: r.name)

    def rule_ids(self):
        # Use pre-fetched data, avoid N+1 queries
        return [rule.id for rule in self.rules.all()]

    def rule_list(self):
        # Use pre-fetched data, avoid N+1 queries
        rules = self.rules.all()
        return sorted(rules, key=lambda r: r.name)

    def __str__(self):
        return self.name


class Author(PublicIdMixin, CodeAIPercentageFieldsModel, TimestampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    provider = models.ForeignKey(DataProvider, on_delete=models.CASCADE)
    external_id = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    email = models.EmailField(default=None, blank=True, null=True)
    login = models.CharField(max_length=100, default=None, blank=True, null=True)

    linked_author = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        default=None,
    )

    group = models.ForeignKey(AuthorGroup, on_delete=models.SET_NULL, default=None, blank=True, null=True)

    split = models.BooleanField(
        default=False,
        help_text="When true, means the author was manually split and will not be automatically linked",
    )

    class Meta:
        unique_together = ["organization", "provider", "external_id"]

    def save(self, *args, **kwargs):
        # TODO: recalculate group percentages
        # groups should only contain main authors
        if self.linked_author:
            self.group = None

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class RepositoryAuthor(CodeAIPercentageFieldsModel, TimestampedModel):
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)

    class Meta:
        unique_together = ["repository", "author"]


class AuthorStat(TimescaleModel):
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    commit = models.ForeignKey(RepositoryCommit, on_delete=models.CASCADE)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)

    code_num_lines = models.PositiveIntegerField(default=0)
    code_ai_num_lines = models.PositiveIntegerField(default=0)
    code_ai_blended_num_lines = models.PositiveIntegerField(default=0)
    code_ai_pure_num_lines = models.PositiveIntegerField(default=0)
    code_not_ai_num_lines = models.PositiveIntegerField(default=0)

    class Meta:
        # time is a requirement from timescale
        unique_together = ["author", "commit", "time"]

    @staticmethod
    def get_defaults():
        return {
            "code_num_lines": 0,
            "code_ai_num_lines": 0,
            "code_ai_blended_num_lines": 0,
            "code_ai_pure_num_lines": 0,
            "code_not_ai_num_lines": 0,
        }

    @classmethod
    def get_aggregated_group_stats(
        cls,
        group_id: int,
        commit: RepositoryCommit = None,
        repository: Repository = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict:
        """Retrieve aggregated statistics for a specific group's authors' contributions.

        Args:
            group_id (int): The ID of the group whose authors' contributions are to be aggregated.
            commit (RepositoryCommit, optional): A specific commit to filter results by.
                Defaults to None.
            repository (Repository, optional): A specific repository to filter results by.
                Defaults to None.
            start_date (datetime, optional): The start date for filtering contributions.
                Defaults to None.
            end_date (datetime, optional): The end date for filtering contributions.
                Defaults to None.

        Returns:
            dict: A dictionary containing aggregated statistics with the following keys:
                - `code_num_lines` (int): Total number of lines of code.
                - `code_ai_num_lines` (int): Total number of AI-generated lines of code.
                - `code_ai_blended_num_lines` (int): Total number of blended AI-human lines of code.
                - `code_ai_pure_num_lines` (int): Total number of purely AI-generated lines of code.
                - `code_not_ai_num_lines` (int): Total number of human-written lines of code.

        Notes:
            - Retrieves all authors belonging to the specified group and passes their IDs
              to the `get_aggregated_authors_stats` method.

        """
        author_ids = Author.objects.filter(
            group_id=group_id,
        ).values_list("id", flat=True)
        return cls.get_aggregated_authors_stats(
            author_ids=list(author_ids),
            commit=commit,
            repository=repository,
            start_date=start_date,
            end_date=end_date,
        )

    @classmethod
    def get_aggregated_authors_stats(
        cls,
        author_ids: list[int],
        commit: RepositoryCommit = None,
        repository: Repository = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict:
        """Retrieve aggregated statistics for authors' contributions. Authors by linked IDs are included in stats.

        Args:
            author_ids (list[int]): A list of IDs of authors to include in the query.
                The list will be extended with any linked authors' IDs.
            commit (RepositoryCommit, optional): A specific commit to filter results by.
                Defaults to None.
            repository (Repository, optional): A specific repository to filter results by.
                Defaults to None.
            start_date (datetime, optional): The start date for filtering contributions.
                Defaults to None.
            end_date (datetime, optional): The end date for filtering contributions.
                Defaults to None.

        Returns:
            dict: A dictionary containing aggregated statistics with the following keys:
                - `code_num_lines` (int): Total number of lines of code.
                - `code_ai_num_lines` (int): Total number of AI-generated lines of code.
                - `code_ai_blended_num_lines` (int): Total number of blended AI-human lines of code.
                - `code_ai_pure_num_lines` (int): Total number of purely AI-generated lines of code.
                - `code_not_ai_num_lines` (int): Total number of human-written lines of code.

        Raises:
            ValueError: If `author_ids` is empty or contains invalid values.

        """
        linked_authors = Author.objects.filter(
            linked_author__in=author_ids,
        ).values_list("id", flat=True)
        author_ids.extend(linked_authors)

        query_params = {
            "author_id__in": author_ids,
            **cls.get_query_params_for_time(start_date, end_date),
        }
        if commit:
            query_params["commit"] = commit
        if repository:
            query_params["repository"] = repository

        return (
            cls.timescale.filter(**query_params)
            .select_related("author")
            .values("author")
            .aggregate(
                code_num_lines=Sum("code_num_lines"),
                code_ai_num_lines=Sum("code_ai_num_lines"),
                code_ai_blended_num_lines=Sum("code_ai_blended_num_lines"),
                code_ai_pure_num_lines=Sum("code_ai_pure_num_lines"),
                code_not_ai_num_lines=Sum("code_not_ai_num_lines"),
            )
        )

    @classmethod
    def get_annotated_authors_stats(
        cls,
        author_ids: list[int],
        commit: RepositoryCommit = None,
        repository: Repository = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict:
        """Retrieve annotated statistics for authors' contributions, grouping contributions by either the author's ID or their linked author's ID.

        Args:
            author_ids (list[int]): A list of IDs of authors to include in the query.
                The list will be extended with any linked authors' IDs.
            commit (RepositoryCommit, optional): A specific commit to filter results by.
                Defaults to None.
            repository (Repository, optional): A specific repository to filter results by.
                Defaults to None.
            start_date (datetime, optional): The start date for filtering contributions.
                Defaults to None.
            end_date (datetime, optional): The end date for filtering contributions.
                Defaults to None.

        Returns:
            list[dict]: A list of dictionaries, each representing a grouped author's statistics,
            containing the following keys:
                - `grouping_key` (int): The author's ID or the ID of their linked author.
                - `code_num_lines` (int): Total number of lines of code.
                - `code_ai_num_lines` (int): Total number of AI-generated lines of code.
                - `code_ai_blended_num_lines` (int): Total number of blended AI-human lines of code.
                - `code_ai_pure_num_lines` (int): Total number of purely AI-generated lines of code.
                - `code_not_ai_num_lines` (int): Total number of human-written lines of code.

        """
        linked_authors = Author.objects.filter(
            linked_author__in=author_ids,
        ).values_list("id", flat=True)
        author_ids.extend(linked_authors)

        query_params = {
            "author_id__in": author_ids,
            **cls.get_query_params_for_time(start_date, end_date),
        }
        if commit:
            query_params["commit"] = commit
        if repository:
            query_params["repository"] = repository

        stats = (
            cls.timescale.filter(**query_params)
            .select_related("author")
            .values("author", "author__linked_author")
            .annotate(
                grouping_key=Case(
                    # If the author has a linked_author,
                    # use that linked_author's ID as the key
                    When(
                        author__linked_author__isnull=False,
                        then=F("author__linked_author"),
                    ),
                    # Otherwise, use the author's own ID as the key
                    default=F("author"),
                )
            )
            .values("grouping_key")
            .annotate(
                code_num_lines=Sum("code_num_lines"),
                code_ai_num_lines=Sum("code_ai_num_lines"),
                code_ai_blended_num_lines=Sum("code_ai_blended_num_lines"),
                code_ai_pure_num_lines=Sum("code_ai_pure_num_lines"),
                code_not_ai_num_lines=Sum("code_not_ai_num_lines"),
            )
        )
        return cls.parse_authors_stats(stats, "grouping_key")

    @staticmethod
    def parse_authors_stats(stats, key):
        return {stat[key]: {k: v for k, v in stat.items() if k != key} for stat in stats}

    @classmethod
    def get_aggregated_authors_stats_by_day(
        cls,
        author_ids: list,
        commit: RepositoryCommit = None,
        repository: Repository = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict:
        """Retrieve aggregated statistics for a list of authors, grouped by day.

        This method calculates daily statistics for the provided authors within the specified
        date range. It supports filtering by commit and repository and returns aggregated
        values for total lines of code and various AI-related and non-AI-related fields.

        Args:
            author_ids (list): A list of author IDs to include in the aggregation.
            commit (RepositoryCommit, optional): Filters the data to a specific commit. Defaults to None.
            repository (Repository, optional): Filters the data to a specific repository. Defaults to None.
            start_date (datetime, optional): The start date for the query range. Defaults to None.
            end_date (datetime, optional): The end date for the query range. Defaults to None.

        Returns:
            dict: A dictionary of aggregated statistics grouped by day, with the following keys:
                - "bucket": The date bucket for each day.
                - "code_num_lines": Total lines of code for the day (defaults to 0 if None).
                - "code_ai_num_lines": Total AI-generated lines of code for the day (defaults to 0 if None).
                - "code_ai_blended_num_lines": Total blended AI lines of code for the day (defaults to 0 if None).
                - "code_ai_pure_num_lines": Total purely AI-generated lines of code for the day (defaults to 0 if None).
                - "code_not_ai_num_lines": Total human-written lines of code for the day (defaults to 0 if None).

        Raises:
            ValueError: If invalid arguments are provided, such as an empty author_ids list.

        """
        query_params = {
            "author_id__in": author_ids,
            **cls.get_query_params_for_time(start_date, end_date),
        }
        if commit:
            query_params["commit"] = commit
        if repository:
            query_params["repository"] = repository

        return (
            cls.timescale.filter(**query_params)
            .time_bucket_gapfill(
                "time",
                "1 day",
                **cls.get_start_end_params_for_time_bucket_gapfill(
                    start_date,
                    end_date,
                ),
            )
            .values("bucket")
            .annotate(
                code_num_lines=Coalesce(
                    Sum("code_num_lines"),
                    Value(0),
                ),
                code_ai_num_lines=Coalesce(
                    Sum("code_ai_num_lines"),
                    Value(0),
                ),
                code_ai_blended_num_lines=Coalesce(
                    Sum("code_ai_blended_num_lines"),
                    Value(0),
                ),
                code_ai_pure_num_lines=Coalesce(
                    Sum("code_ai_pure_num_lines"),
                    Value(0),
                ),
                code_not_ai_num_lines=Coalesce(
                    Sum("code_not_ai_num_lines"),
                    Value(0),
                ),
            )
            .order_by("bucket")
        )

    @classmethod
    def get_aggregated_single_author_stats_by_day(
        cls,
        author: Author,
        commit: RepositoryCommit = None,
        repository: Repository = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict:
        """Retrieve aggregated daily statistics for a specific author.

        This method calculates daily aggregated statistics for the given author and any authors
        linked to them. It supports optional filtering by commit, repository, and date range.
        Aggregations include total lines of code, AI-generated lines, human-written lines.

        Uses the `get_aggregated_authors_stats_by_day` method to perform the query, ensuring that
        contributions from linked authors are included.
        """
        author_ids = [author.id]
        linked_authors = Author.objects.filter(
            linked_author=author,
        ).values_list("id", flat=True)
        if linked_authors:
            author_ids.extend(linked_authors)

        return cls.get_aggregated_authors_stats_by_day(
            author_ids=author_ids,
            commit=commit,
            repository=repository,
            start_date=start_date,
            end_date=end_date,
        )

    @classmethod
    def get_aggregated_group_stats_by_day(
        cls,
        group: AuthorGroup,
        commit: RepositoryCommit = None,
        repository: Repository = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict:
        """Retrieve aggregated daily statistics for a specific group.

        This method calculates daily aggregated statistics for the given group and any authors
        linked to them. It supports optional filtering by commit, repository, and date range.
        Aggregations include total lines of code, AI-generated lines, human-written lines.

        Uses the `get_aggregated_authors_stats_by_day` method to perform the query, ensuring that
        contributions from linked authors are included.
        """
        author_ids = list(group.author_set.all().values_list("id", flat=True))
        linked_authors = Author.objects.filter(
            linked_author__in=author_ids,
        ).values_list("id", flat=True)
        author_ids.extend(linked_authors)

        return cls.get_aggregated_authors_stats_by_day(
            author_ids=author_ids,
            commit=commit,
            repository=repository,
            start_date=start_date,
            end_date=end_date,
        )

    @classmethod
    def get_query_params_for_time(
        cls,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ):
        start_date = start_date or (django_timezone.now() - timedelta(days=settings.DEFAULT_TIME_WINDOW_DAYS + 1))
        if not end_date:
            return {"time__gte": normalize_start_date(start_date)}

        return {
            "time__range": (
                normalize_start_date(start_date),
                normalize_end_date(end_date),
            )
        }

    @classmethod
    def get_start_end_params_for_time_bucket_gapfill(
        cls,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ):
        start = start_date or (django_timezone.now() - timedelta(days=settings.DEFAULT_TIME_WINDOW_DAYS + 1))
        end = end_date or django_timezone.now()
        return {
            "start": start,
            "end": end,
        }


class RepositoryFileChunkBlame(TimestampedModel):
    chunk = models.ForeignKey(RepositoryFileChunk, on_delete=models.CASCADE)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    # we may not have this commit in our database, so no foreign key
    sha = models.CharField(max_length=40)
    date_time = models.DateTimeField()
    code_line_start = models.PositiveIntegerField(default=0)
    code_line_end = models.PositiveIntegerField(default=0)
    code_generation_label = models.CharField(
        max_length=20,
        choices=CodeGenerationLabelChoices.choices,
        default=None,
        blank=True,
        null=True,
    )


class SystemMessageManager(models.Manager):
    def active(self):
        now = datetime.now(UTC)
        return self.filter(starts_at__lte=now, expires_at__gte=now)


class SystemMessage(PublicIdMixin, TimestampedModel):
    starts_at = models.DateTimeField(help_text="When to start showing this message to users")
    expires_at = models.DateTimeField(help_text="When to stop showing this message to users")
    text = models.CharField(max_length=200, help_text="The message to show to users. Up to 200 characters")
    read_more_link = models.URLField(
        default=None,
        blank=True,
        null=True,
        help_text="Optional external link for more information",
    )
    is_dismissible = models.BooleanField(default=True, help_text="Whether or not users can hide this message")

    objects = SystemMessageManager()

    @admin.display(boolean=True)
    def is_showing(self):
        now = datetime.now(UTC)
        return self.starts_at <= now and (self.expires_at is None or now <= self.expires_at)


class WebhookRequest(TimestampedModel):
    provider = models.ForeignKey(DataProvider, on_delete=models.CASCADE)
    data_file_path = models.CharField(max_length=500)
    response_status_code = models.PositiveIntegerField(default=None, blank=True, null=True)
    response_message = models.TextField(default=None, blank=True, null=True)


class JiraProject(PublicIdMixin, TimestampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    key = models.CharField(max_length=255)
    external_id = models.CharField(max_length=100)
    is_selected = models.BooleanField(default=True)
    repository_group = models.ManyToManyField(RepositoryGroup, blank=True, related_name="jira_projects")

    class Meta:
        unique_together = ["organization", "external_id"]

    def __str__(self):
        return self.name


class MessageIntegration(TimestampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    data = models.JSONField(default=None, blank=True, null=True)
    service = models.CharField(
        max_length=50,
        choices=MessageIntegrationServiceChoices.choices,
        null=True,
        blank=True,
    )
    enabled = models.BooleanField(default=True)
    connected_by = models.ForeignKey(CustomUser, default=None, blank=True, null=True, on_delete=models.SET_NULL)
    connected_at = models.DateTimeField(default=None, blank=True, null=True)

    class Meta:
        unique_together = ["organization", "service"]

    def __str__(self):
        return f"MessageIntegration | {self.organization.name} | {self.service}"


auditlog.register(RepositoryCodeAttestation)
